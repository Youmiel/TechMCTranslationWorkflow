# -*- coding: utf-8 -*-
"""块目录预分句标号 + ZH 机械化断句（方案 4，2026-08-20）：EN 按句末标点 .?! 预分句标号 E1..En；
ZH 按句末标点 。！？… 预分句标号 Z1..Zm，并按标点切候选段 + 贪心拼合到目标宽度区间，生成 **r03 模板骨架**
（ZH 整句原文 + 子句段已预填，EN/关系/S 号留待分句 subagent 填空）。

回填工作流（reflow-redstone）步骤 5 分句输入改造（r03 归一化系列，取代 r02 折行副本）：
- **EN 预分句**：`reflow/r01_results/`（补标点整段，衔接归位后）→ `reflow/r03_normalized_1/`
  ——按句末标点 `.?!` 分句（常见缩写 Mr./Fig./e.g. 等保护、跨块句标记剥离），编号 E1..En
- **ZH 归一化（句级 + 子句级合并产物）**：`reflow/r02_results/`（整段译文原稿）→ `reflow/r03_normalized_2/`
  ——句号 `。！？…` 预分句编号 Z1..Zm（括号配平保护）+ 句内按标点切候选段 + 贪心拼合 [soft_min, soft_max]
  （硬 ≤hard_max），输出 **r03 模板骨架**：每 Z 句一组（`## S?_Z<n>` 占位 + ZH 原文预填 + 子句段预填 +
  关系预填 1:1/1:n + EN 待填），分句 agent 填空后即 r03_results

设计：
- **机械断句替代 agent 判长短**：长短/宽度/忠实由脚本承担（task-split 实测 agent 断句不稳——
  留长句 / 断太短 / 类型不清；宽度区间与标点集合全参数化，见参数）
- **不形成中英对照**：EN/ZH 各自编号；`S?_Z<n>` 占位默认按序提示对应 E<n>（启发式，agent 须核对）
- **忠实铁律由结构保证**：子句段只在标点处切（标点保留段尾）、不增删改字符——段拼接 == Z 原文 == r02；
  模板 ZH 行 agent 不得改动，断点标点归属前段
- **多语言通用**：切分标点（--punct-levels 有序层级）、句末标点、句长区间（--soft-min/--soft-max/
  --hard-max/--min-unit）全 CLI 参数化，默认 CJK；宽度复用 srt_reflow_common.text_width（Unicode 块通用）
- 每块独立处理、互不影响；对整个输入目录一次跑完（命令只运行一次）
- 产物契约 r03（`## S<n>` 格式）不变；本脚本只生成**分句 subagent 输入**，非校验基准

用法（命令根 = Project_Main/）：
  python scripts/srt_reflow_presplit.py reflow/r01_results/ reflow/r02_results/ -o reflow/
    → reflow/r03_normalized_1/chunk_<k>.txt（EN 预分句 E1..En）
    → reflow/r03_normalized_2/chunk_<k>.txt（ZH r03 模板骨架：Z 句 + 子句段预填）
  # 可选独立产物：5-2 task-match 的整句级 Z 精简列表（省 ~80%，独立路径不复用模板骨架）
  python scripts/srt_reflow_presplit.py reflow/r01_results/ reflow/r02_results/ -o reflow/ \
      --zh-list-out reflow/r03_zslim
    → 额外生成 reflow/r03_zslim/chunk_<k>.txt（整句级 Z 列表，供 task-match 语义匹配）
退出码：0 = 全部块预分句完成；1 = 输入目录无块文件。
"""
import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

from srt_reflow_common import wrap_text, collect_chunk_files, strip_stitch_prefix, MAX_LINE, text_width
from srt_reflow_punct import (
    build_profile,
    pack_by_strength,
    split_atomic,
    split_sentences,
)

# 机械化断句默认参数（CJK；可 CLI 覆盖——多语言适配改标点角色表 + 这里，核心算法零改动）
DEFAULT_SOFT_MIN = 15      # 目标区间下限（视觉宽度）
DEFAULT_SOFT_MAX = 22      # 目标区间上限（软；check-r03 ③ 软 22）
DEFAULT_HARD_MAX = 26      # 硬上限（check-r03 ③ 硬 26，>26 必切）
DEFAULT_MIN_UNIT = 5       # 最小单元宽度（≈1s 阅读时长 @5字/秒，防碎片）
# 注：旧「有序层级切分标点」常量已删除（2026-09-22 自查）——断点强度由 srt_reflow_punct 的
# 角色表表达；旧 `--punct-levels` 仍接受，但按**字符归属**映射（见 make_profile）。


def make_profile(lang="zh", punct_levels=None, **kw):
    """构造标点角色 profile。

    `punct_levels=None`（**推荐/默认**）→ 直接用 `srt_reflow_punct` 的角色表默认。
    `punct_levels` 给出（旧 CLI `--punct-levels`）→ 按**字符归属**把层级映射为角色字符集：
    旧默认层级 `["，；：", "—", "、"]` 中，L1 同时含强断点（`；：`）与句内断点（`，`）——
    按层级位置整体套用会把逗号误升为 strong、破折号误降为 clause（与角色表默认冲突，
    2026-09-22 自查发现）。故按**语言默认角色的字符归属**拆分 L1：
    `；：` 归 strong、`，` 归 clause，其余层级按序补入尚未覆盖的角色。
    """
    levels = list(punct_levels) if punct_levels else []
    if not levels:
        return build_profile(lang, **kw)
    base = build_profile(lang)                      # 语言默认角色（用于判定字符归属）
    strong, clause, lst = [], [], []
    for lv in levels:
        for ch in lv:
            role = base.role_of(ch)
            if role == "strong" and ch not in strong:
                strong.append(ch)
            elif role == "clause" and ch not in clause:
                clause.append(ch)
            elif role == "list" and ch not in lst:
                lst.append(ch)
    kw.setdefault("strong", "".join(strong) or None)
    kw.setdefault("clause", "".join(clause) or None)
    kw.setdefault("list_chars", "".join(lst) or None)
    return build_profile(lang, **kw)


def split_en(text, profile=None):
    """英文整段按句末标点 .?! 分句（先合并显示折行、剥跨块句标记前缀）→ [句文本]。

    委托 `srt_reflow_punct.split_sentences`（角色表 + 例外模式 guards：缩写/小数点/省略号/
    括号配平/续小写粘连）——取代旧 `is_en_sentence_end` + `EN_ABBR_RE` 的本模块硬编码。
    """
    text = re.sub(r"\s+", " ", text.strip())
    text = strip_stitch_prefix(text).strip()
    return split_sentences(text, profile or build_profile("en"))


def _is_cjk(ch):
    """CJK/全角（含全角标点）判定——折行合并时空格保留策略用（与 srt_reflow_core/io.py FULLWIDTH_RE 一致）。"""
    return (
        "\u2e80" <= ch <= "\u9fff"
        or "\uac00" <= ch <= "\ud7af"
        or "\u3040" <= ch <= "\u30ff"
        or "\uf900" <= ch <= "\ufaff"
        or "\uff00" <= ch <= "\uffef"
    )


def _collapse_ws(text):
    """折行合并（显示性换行折叠）：空白两侧均为 CJK/全角 → 删除；否则折叠为单空格
    （保留中英/数字混排空格——`Carpet 的 fillUpdates`、`139 147 11` 不受影响）。"""
    out = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            j = i
            while j < n and text[j].isspace():
                j += 1
            prev = out[-1] if out else ""
            nxt = text[j] if j < n else ""
            if not (prev and nxt and _is_cjk(prev) and _is_cjk(nxt)):
                out.append(" ")
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out).strip()


def split_zh(text, profile=None):
    """中文整段按句末标点 。！？… 分句（折行合并保留中英/数字空格、括号配平保护；剥跨块句标记前缀）→ [句文本]。

    委托 `srt_reflow_punct.split_sentences`（角色表 + 例外模式 guards）——取代旧本模块
    硬编码 `ZH_EOS_RE` + depth 循环。
    """
    text = strip_stitch_prefix(text)
    text = _collapse_ws(text)
    return split_sentences(text, profile or build_profile("zh"))


def render(prefix, sentences):
    """渲染预分句文件：`- E1: 句文本`（ZH 用 Z 前缀）；句内 wrap_text 折行、续行顶格（显示性换行）。"""
    if not sentences:
        return f"# {prefix} 预分句（空块，无句末标点）\n"
    lines = [f"# {prefix} 预分句 — 按句末标点分句，编号 {prefix}1..{prefix}{len(sentences)}；句内显示折行按整段解析"]
    for idx, s in enumerate(sentences, 1):
        wrapped = wrap_text(s, MAX_LINE).split("\n")
        lines.append(f"- {prefix}{idx}: {wrapped[0]}")
        lines.extend(wrapped[1:])
    return "\n".join(lines) + "\n"


def pack_candidates(segs, hard_max, min_unit, soft_min=None, soft_max=None, profile=None):
    """拼合候选段 → 显示单元 [(文本, 宽度)]。

    **兼容包装**：接受旧式 `[段文本]` 或新式 `[(段文本, 段尾角色)]`；
    内部委托 `srt_reflow_punct.pack_by_strength`（**代价最小化** DP，取代旧的贪心填满）。

    旧贪心会吞掉强断点、保留弱断点（实例：`…回答一下：第一，`(17) + `怎么搭…？`(12)，
    断点落在逗号而非冒号）；DP 版本让断点强度参与决策（结果 `…回答一下：`(14) + `第一，…？`(15)）。

    - 旧式输入（纯字符串）→ 段尾角色按段文本末尾字符反查 profile（未传 profile 用 zh）
    - 旧调用不传 soft_min/soft_max → 退化为「仅防碎片 + 约束 ≤ hard_max」（保持旧语义的宽度部分）
    """
    if not segs:
        return []
    prof = profile or build_profile("zh")
    first = segs[0]
    if isinstance(first, tuple):
        typed = list(segs)          # 已是 (文本, 角色[, 括号内]) 形态，直接透传
    else:
        # 旧式输入（纯字符串）→ 段尾角色按段文本末尾字符反查 profile；
        # 括号内标记无法从字符串还原（旧调用点不涉及），按 False 处理
        typed = []
        for s in segs:
            tail = s.rstrip()[-1:] if s.rstrip() else ""
            typed.append((s, prof.role_of(tail) if tail else None, False))
    return pack_by_strength(typed, hard_max, min_unit, soft_min, soft_max, prof)


def plan_sentence(text, punct_levels, hard_max, min_unit, soft_min=None, soft_max=None,
                  lang="zh", profile=None):
    """整句机械化断句 → (状态, 子单元列表 [(段文本, 宽度)], 备注)。

    **算法（2026-09-21 起）**：标点角色表切原子段（`srt_reflow_punct.split_atomic`，
    含小数点/序号/缩写/省略号/括号配平等例外模式）→ **代价最小化拼合**
    （`pack_by_strength`：断点强度 + 段宽偏离 + 碎片罚）。
    取代旧的「有序层级递归切分 + 贪心填满 hard_max」——后者会吞掉强断点
    （实例：`…回答一下：第一，`(17) + `怎么搭…？`(12)，断点落在逗号而非冒号）。

    状态：ok（全部 ≤ hard_max 且无碎片）/ warn（含 < min_unit 碎片段）/ err（单段切不动仍 > hard_max）。
    `punct_levels`（旧 CLI）经 `make_profile` 映射为角色字符集，保持旧命令可用。
    """
    prof = profile or make_profile(lang, punct_levels)
    typed = split_atomic(text, prof)
    units = pack_by_strength(typed, hard_max, min_unit, soft_min, soft_max, prof)
    status = "ok"
    notes = []
    for u, w in units:
        if w > hard_max:
            status = "err"
            notes.append(f"段宽 {w:.1f} > {hard_max}（多级切分后仍超，需 agent 手工再切或回 r02 改写）")
    if status == "ok":
        for u, w in units:
            if w < min_unit:
                status = "warn"
                notes.append(f"段宽 {w:.1f} < {min_unit}（碎片候选，已尽量并入邻段；仍短则 agent 复核语义再并）")
                break
    return status, units, notes


def render_zh_template(zh_sentences, soft_min, soft_max, hard_max, min_unit, punct_levels,
                       lang="zh"):
    """渲染 r03 模板骨架：每 Z 句一组（`## S?_Z<n>` 占位 + ZH 原文 + 子句段预填 + 关系预填 1:1/1:n + EN 待填）。
    分句 agent 填空（S 号/EN/子单元 EN/关系核对）后即 r03_results；ZH 行忠实铁律由结构保证。"""
    lines = [
        "# ZH 归一化·r03 模板骨架 —— 句号预分句 Z1..Zm + 句内机械切分 [%g,%g]（硬 ≤%g）" % (soft_min, soft_max, hard_max),
        "# 用法：分句 agent 以本模板填空——ZH 行已预填（忠实铁律：不得改动）",
        "#   ① S 号：`S?_Z<n>` → 块内连续 `S<号>`（删占位与默认标注）；② EN：从 r03_normalized_1 抄对应 E 整句",
        "#      （`默认 E<n>` 为按序启发式提示，须核对对应）；③ 关系：已按段数预填 1:1/1:n（多 E 对单 Z 改 n:1）",
        "#   ④ 子单元 EN：填互斥英文片段。n:1 合并、游离停顿词、跨 Z 句并入同一整句按需调整（见 task-split）",
        "# 参数：切分标点层级（高→低）%s（映射为断点角色强度）；宽度复用 text_width（全角=1.0/拉丁=0.5/数字=0.5/空格=0.5）"
        % " → ".join(punct_levels),
        "",
    ]
    prof = make_profile(lang, punct_levels)
    for i, (zn, text) in enumerate(zh_sentences, 1):
        total = text_width(text)
        status, units, notes = plan_sentence(text, punct_levels, hard_max, min_unit,
                                             soft_min, soft_max, lang, prof)
        if len(units) == 1:
            lines.append(f"## S?_Z{i}（默认 E{i}）")
            lines.append("- EN: <待填>")
            lines.append(f"- ZH: {text}")
            lines.append("- 关系: 1:1")
        else:
            lines.append(f"## S?_Z{i}（默认 E{i}，切 {len(units)} 段）")
            lines.append("- EN: <待填>")
            lines.append(f"- ZH: {text}")
            lines.append("- 关系: 1:n")
            widths = " / ".join("%.1f" % w for _, w in units)
            lines.append(f"> 段宽（视觉）: {widths}；整句宽 {total:.1f}")
            for j, (u, w) in enumerate(units, 1):
                lines.append(f"### S?_Z{i}{chr(96 + j)}")
                lines.append("- EN: <待填>")
                lines.append(f"- ZH: {u}")
        if notes:
            lines.append("> ⚠️ " + "；".join(notes))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_zslim(zh_sentences):
    """渲染整句级 Z 精简列表（task-match 输入，独立产物路径 r03_zslim/）。

    只含 `Z<n> <整句文本>` 每句一行——无 `## S?_Z<n>` 标题、`- EN: <待填>` 占位、`- 关系:`、
    `> 段宽/⚠️` 注释等脚手架（那些是 r03_normalized_2 模板骨架给 5-1 task-split 填空用的，
    对只做整句语义对应的 5-2 task-match 是纯噪音——实证 m5SvZsN 整句级信息仅占模板 20%）。
    Z 号与 r03_normalized_2 的 Z1..Zm 一一对应（同源 split_zh），build-r03 仍读模板骨架做子句段填回。
    """
    if not zh_sentences:
        return "# Z 精简列表（空块）\n"
    lines = [f"# Z 整句列表 — 与 r03_normalized_2 的 Z1..Z{len(zh_sentences)} 一一对应；每行一个整句，供语义匹配"]
    for i, (zn, s) in enumerate(zh_sentences, 1):
        # 整句文本可能因显示折行被 wrap 成多行，但列表本身逐句一行；文本不折行（≤1000 由消费端 read 处理）
        lines.append(f"Z{i} {s}")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(
        description="预分句 + ZH 机械化断句：EN（r01_results）按 .?! 分句 → r03_normalized_1/（E1..En）；ZH（r02_results）按 。！？ 分句 + 句内切分 → r03_normalized_2/（r03 模板骨架：Z 句 + 子句段预填）"
    )
    ap.add_argument("en_dir", help="EN 输入目录：reflow/r01_results/（补标点整段）")
    ap.add_argument("zh_dir", help="ZH 输入目录：reflow/r02_results/（整段译文原稿）")
    ap.add_argument("-o", "--out", required=True, help="输出基目录（生成 r03_normalized_1/ 与 r03_normalized_2/）")
    ap.add_argument("--zh-list-out", default=None,
                    help="可选：额外输出整句级 Z 精简列表目录（生成 <此目录>/ 下 chunk_<k>.txt，供 5-2 task-match "
                         "语义匹配输入——独立产物路径，不替代 r03_normalized_2 模板骨架；不传则仅生成模板骨架）")
    ap.add_argument("--verbose", action="store_true", help="展开打印每块句数")
    ap.add_argument("--soft-min", type=float, default=DEFAULT_SOFT_MIN, help=f"目标区间下限（默认 {DEFAULT_SOFT_MIN}）")
    ap.add_argument("--soft-max", type=float, default=DEFAULT_SOFT_MAX, help=f"目标区间上限/软（默认 {DEFAULT_SOFT_MAX}；check-r03 ③ 软 22）")
    ap.add_argument("--hard-max", type=float, default=DEFAULT_HARD_MAX, help=f"硬上限（默认 {DEFAULT_HARD_MAX}；check-r03 ③ 硬 26）")
    ap.add_argument("--min-unit", type=float, default=DEFAULT_MIN_UNIT, help=f"最小单元宽度/防碎片（默认 {DEFAULT_MIN_UNIT}，≈1s@5字/秒）")
    ap.add_argument("--punct-levels", action="append", default=None,
                    help="【兼容保留·不推荐】旧式有序层级切分标点（可多次指定，先高后低）。"
                         "**不给则用角色表默认**（推荐，见 srt_reflow_punct）；"
                         "给了则按各字符在旧默认层级中的归属映射到 strong/clause/list"
                         "（旧 L1 `，；：` 中：`；：` 为 strong、`，` 为 clause）")
    # 标点角色表细粒度覆盖（srt_reflow_punct；不传 = 语言默认，保持既有行为）
    ap.add_argument("--punct-terminators", default=None,
                    help="句界字符集（默认 zh 。！？… / en .?!）——扩它会改变 Z 句数、使 align/ 失效，谨慎")
    ap.add_argument("--punct-strong", default=None, help="强断点字符集（默认 zh ；：— / en ;:—）")
    ap.add_argument("--punct-clause", default=None, help="句内断点字符集（默认 zh ， / en ,）")
    ap.add_argument("--punct-list", dest="punct_list", default=None, help="并列内部断点字符集（默认 zh 、 / en 空）")
    args = ap.parse_args()

    en_prof = make_profile("en", args.punct_levels, terminators=args.punct_terminators,
                           strong=args.punct_strong, clause=args.punct_clause,
                           list_chars=args.punct_list)
    zh_prof = make_profile("zh", args.punct_levels, terminators=args.punct_terminators,
                           strong=args.punct_strong, clause=args.punct_clause,
                           list_chars=args.punct_list)

    en_blocks = collect_chunk_files(args.en_dir)
    zh_blocks = collect_chunk_files(args.zh_dir)
    if not en_blocks and not zh_blocks:
        sys.exit("❌ 输入目录无块文件")
    en_out = os.path.join(args.out, "r03_normalized_1")
    zh_out = os.path.join(args.out, "r03_normalized_2")
    os.makedirs(en_out, exist_ok=True)
    os.makedirs(zh_out, exist_ok=True)
    zh_list_out = os.path.join(args.zh_list_out, "") if args.zh_list_out else None
    if zh_list_out:
        os.makedirs(zh_list_out, exist_ok=True)

    keys = sorted(set(en_blocks) | set(zh_blocks))
    n_en = n_zh = n_zl = 0
    for k in keys:
        if k in en_blocks:
            with open(en_blocks[k], encoding="utf-8") as fh:
                sents = split_en(fh.read(), en_prof)
            n_en += len(sents)
            with open(os.path.join(en_out, "chunk_%03d.txt" % k), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(render("E", sents))
            if args.verbose:
                print(f"   chunk_{k:03d}（EN）: {len(sents)} 句")
        if k in zh_blocks:
            with open(zh_blocks[k], encoding="utf-8") as fh:
                sents = split_zh(fh.read(), zh_prof)
            n_zh += len(sents)
            zh_sents = [(f"Z{i}", s) for i, s in enumerate(sents, 1)]
            with open(os.path.join(zh_out, "chunk_%03d.txt" % k), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(render_zh_template(zh_sents, args.soft_min, args.soft_max, args.hard_max,
                                            args.min_unit, punct_levels))
            if zh_list_out:
                with open(os.path.join(zh_list_out, "chunk_%03d.txt" % k), "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(render_zslim(zh_sents))
                n_zl += len(sents)
            if args.verbose:
                print(f"   chunk_{k:03d}（ZH）: {len(sents)} 句（r03 模板骨架"
                      + (" + 精简 Z 列表" if zh_list_out else "") + "）")
    print(f"✅ 预分句完成：EN {len(en_blocks)} 块 / {n_en} 句 → {en_out}；ZH {len(zh_blocks)} 块 / {n_zh} 句（r03 模板骨架）→ {zh_out}")
    if zh_list_out:
        print(f"   ZH 整句级精简列表 {len(zh_blocks)} 块 / {n_zl} 句 → {zh_list_out}")
    print(f"   ZH 断句参数: 目标区间 [{args.soft_min:.0f},{args.soft_max:.0f}] 硬 ≤{args.hard_max:.0f} 最小单元 ≥{args.min_unit:.0f}；"
          f"切分标点层级（高→低）{' → '.join(punct_levels)}")
    print(f"   标点角色表: 句界 `{args.punct_terminators or '语言默认'}`；强断点 `{args.punct_strong or '语言默认'}`；"
          f"句内 `{args.punct_clause or '语言默认'}`；并列 `{args.punct_list if args.punct_list is not None else '语言默认'}`"
          f"（拼合 = 断点强度 + 段宽偏离 + 碎片 的代价最小化）")
    return 0


if __name__ == "__main__":
    main()
