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
退出码：0 = 全部块预分句完成；1 = 输入目录无块文件。
"""
import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

from srt_reflow_common import wrap_text, collect_chunk_files, strip_stitch_marks, MAX_LINE, text_width

# 机械化断句默认参数（CJK；可 CLI 覆盖——多语言适配只改这里 + 标点参数，核心算法零改动）
DEFAULT_SOFT_MIN = 15      # 目标区间下限（视觉宽度）
DEFAULT_SOFT_MAX = 22      # 目标区间上限（软；check-r03 ③ 软 22）
DEFAULT_HARD_MAX = 26      # 硬上限（check-r03 ③ 硬 26，>26 必切）
DEFAULT_MIN_UNIT = 5       # 最小单元宽度（≈1s 阅读时长 @5字/秒，防碎片）
# 切分标点层级（有序 = 优先级从高到低；标点保留段尾；层级递增式切分——先用高层切，
# 单段超 hard_max 才降级用低层；语义完整处优先、宽度兜底）：
#   L1 逗号族（，；：）主断点；L2 顿号（、）并列内部（避免切断「a、b」并列短语）；
#   L3 破折号（—）插入/解释，最后手段。可 --punct-levels 扩展/覆盖（多语言只改这里）
DEFAULT_PUNCT_LEVELS = ["，；：", "、", "—"]

# EN 句末标点（可连续：... / !?）；ZH 句末标点（含省略号）
EN_EOS_RE = re.compile(r"[.!?]+")
ZH_EOS_RE = re.compile(r"[。！？…]+")
# EN 常见缩写（缩写点不作句末）：字幕场景常用；匹配须紧邻标点（以 . 结尾）
EN_ABBR_RE = re.compile(
    r"(?i)(?<![A-Za-z])"
    r"(?:Mr|Mrs|Ms|Dr|Prof|Rev|St|Sr|Jr|vs|etc|al|Inc|Ltd|Corp|Co|Dept|"
    r"Fig|Eq|No|Vol|e\.g|i\.e|approx|min|max|hr|sec|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
    r"\.\s*$"
)
ZH_OPEN_RE = "（【「“‘"
ZH_CLOSE_RE = "）】」”’"


def is_en_sentence_end(text, start, end):
    """EN 判定 [start,end) 处标点是否为句末：字幕句首常小写——省略号（...）与缩写点为非句末，
    标点后跟空格/结束即句末（无空格直接续小写 = 异常粘连，非句末）。"""
    seg = text[start:end]
    if "..." in seg:
        return False  # 省略号 = 句内停顿（不切；agent 按语义再切）
    if EN_ABBR_RE.search(text[:end]):
        return False  # 缩写点保护（Mr./Fig./e.g. 等）
    nxt = text[end : end + 1]
    if nxt and nxt.islower():
        return False  # 标点后无空格直接续小写（异常粘连）→ 非句末
    return True


def split_en(text):
    """英文整段按句末标点 .?! 分句（先合并显示折行、剥离跨块句标记）→ [句文本]。"""
    text = re.sub(r"\s+", " ", text.strip())
    text = strip_stitch_marks(text).strip()
    sentences, buf = [], []
    i, n = 0, len(text)
    while i < n:
        m = EN_EOS_RE.search(text, i)
        if not m:
            buf.append(text[i:])
            i = n
            break
        end = m.end()
        if is_en_sentence_end(text, m.start(), end):
            sentences.append("".join(buf) + text[i:end])
            buf = []
        else:
            buf.append(text[i:end])
        i = end
    if buf:
        sentences.append("".join(buf))
    return [s.strip() for s in sentences if s.strip()]


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


def split_zh(text):
    """中文整段按句末标点 。！？… 分句（折行合并保留中英/数字空格、括号配平保护）→ [句文本]。"""
    text = _collapse_ws(text)
    sentences, buf = [], []
    i, n = 0, len(text)
    depth = 0
    while i < n:
        c = text[i]
        if c in ZH_OPEN_RE:
            depth += 1
        elif c in ZH_CLOSE_RE:
            depth = max(0, depth - 1)
        m = ZH_EOS_RE.match(text, i)
        if m and depth == 0:
            sentences.append("".join(buf) + text[i : m.end()])
            buf = []
            i = m.end()
        else:
            buf.append(c)
            i += 1
    if buf:
        sentences.append("".join(buf))
    return [s.strip() for s in sentences if s.strip()]


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


def split_by_punct(text, puncts):
    """按切分标点把整句切成候选段（标点保留在段尾，归属前段）→ [段文本]。
    无标点时返回 [text]（单段）；连续标点/空白段剔除。"""
    segs, buf = [], []
    for ch in text:
        buf.append(ch)
        if ch in puncts:
            s = "".join(buf).strip()
            if s:
                segs.append(s)
            buf = []
    if buf:
        s = "".join(buf).strip()
        if s:
            segs.append(s)
    return segs


def split_recursive(text, levels, hard_max):
    """多级切分：按 levels[0] 标点切候选段；单段超 hard_max 时递归用更细标点切。
    语义完整处优先（高层级标点先试），宽度兜底；最终每段 ≤ hard_max（切不动则保留原段，由调用方标 ❌）。"""
    if text_width(text) <= hard_max or not levels:
        return [text]
    parts = split_by_punct(text, levels[0])
    if len(parts) <= 1:
        return split_recursive(text, levels[1:], hard_max) if len(levels) > 1 else [text]
    out = []
    for p in parts:
        out.extend(split_recursive(p, levels[1:], hard_max))
    return out


def pack_candidates(segs, hard_max, min_unit):
    """贪心拼合候选段 → 子单元 [(文本, 宽度)]（保持顺序；语言无关、参数化）。

    - 从每段起点累加后续段，直到累加超过 hard_max 断开——单元尽量填满（软 soft_max 是目标、非硬约束）
    - 断开后新段重新累加；首段即超 soft_max 时单段成单元（标点边界优先，可接受）
    - 防碎片后处理：从尾向前，宽度 < min_unit 的单元并入前单元（合并后 ≤ hard_max）"""
    units = []
    i, n = 0, len(segs)
    while i < n:
        cur, cur_w = [segs[i]], text_width(segs[i])
        k = i + 1
        while k < n and cur_w + text_width(segs[k]) <= hard_max:
            cur.append(segs[k])
            cur_w += text_width(segs[k])
            k += 1
        units.append(("".join(cur), cur_w))
        i = k
    merged = []
    for u, w in units:
        if merged and w < min_unit and merged[-1][1] + w <= hard_max:
            merged[-1] = (merged[-1][0] + u, merged[-1][1] + w)
        else:
            merged.append((u, w))
    return merged


def plan_sentence(text, punct_levels, hard_max, min_unit):
    """整句机械化断句 → (状态, 子单元列表 [(段文本, 宽度)], 备注)。

    状态：ok（全部 ≤ hard_max，可采）/ warn（含 < min_unit 碎片段，已尽量合并）/ err（单段切不动仍 > hard_max）。
    优先级：punct_levels 有序层级（高层先切，超宽段才降级低层）——语义完整处优先、宽度兜底。"""
    cands = split_recursive(text, punct_levels, hard_max)
    units = pack_candidates(cands, hard_max, min_unit)
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


def render_zh_template(zh_sentences, soft_min, soft_max, hard_max, min_unit, punct_levels):
    """渲染 r03 模板骨架：每 Z 句一组（`## S?_Z<n>` 占位 + ZH 原文 + 子句段预填 + 关系预填 1:1/1:n + EN 待填）。
    分句 agent 填空（S 号/EN/子单元 EN/关系核对）后即 r03_results；ZH 行忠实铁律由结构保证。"""
    lines = [
        "# ZH 归一化·r03 模板骨架 —— 句号预分句 Z1..Zm + 句内机械切分 [%g,%g]（硬 ≤%g）" % (soft_min, soft_max, hard_max),
        "# 用法：分句 agent 以本模板填空——ZH 行已预填（忠实铁律：不得改动）",
        "#   ① S 号：`S?_Z<n>` → 块内连续 `S<号>`（删占位与默认标注）；② EN：从 r03_normalized_1 抄对应 E 整句",
        "#      （`默认 E<n>` 为按序启发式提示，须核对对应）；③ 关系：已按段数预填 1:1/1:n（多 E 对单 Z 改 n:1）",
        "#   ④ 子单元 EN：填互斥英文片段。n:1 合并、游离停顿词、跨 Z 句并入同一整句按需调整（见 task-split）",
        "# 参数：切分标点层级（高→低）%s；宽度复用 text_width（全角=1.0/拉丁=0.5/数字=0.5/空格=0.5）" % " → ".join(punct_levels),
        "",
    ]
    for i, (zn, text) in enumerate(zh_sentences, 1):
        total = text_width(text)
        status, units, notes = plan_sentence(text, punct_levels, hard_max, min_unit)
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


def main():
    ap = argparse.ArgumentParser(
        description="预分句 + ZH 机械化断句：EN（r01_results）按 .?! 分句 → r03_normalized_1/（E1..En）；ZH（r02_results）按 。！？ 分句 + 句内切分 → r03_normalized_2/（r03 模板骨架：Z 句 + 子句段预填）"
    )
    ap.add_argument("en_dir", help="EN 输入目录：reflow/r01_results/（补标点整段）")
    ap.add_argument("zh_dir", help="ZH 输入目录：reflow/r02_results/（整段译文原稿）")
    ap.add_argument("-o", "--out", required=True, help="输出基目录（生成 r03_normalized_1/ 与 r03_normalized_2/）")
    ap.add_argument("--verbose", action="store_true", help="展开打印每块句数")
    ap.add_argument("--soft-min", type=float, default=DEFAULT_SOFT_MIN, help=f"目标区间下限（默认 {DEFAULT_SOFT_MIN}）")
    ap.add_argument("--soft-max", type=float, default=DEFAULT_SOFT_MAX, help=f"目标区间上限/软（默认 {DEFAULT_SOFT_MAX}；check-r03 ③ 软 22）")
    ap.add_argument("--hard-max", type=float, default=DEFAULT_HARD_MAX, help=f"硬上限（默认 {DEFAULT_HARD_MAX}；check-r03 ③ 硬 26）")
    ap.add_argument("--min-unit", type=float, default=DEFAULT_MIN_UNIT, help=f"最小单元宽度/防碎片（默认 {DEFAULT_MIN_UNIT}，≈1s@5字/秒）")
    ap.add_argument("--punct-levels", action="append", default=None,
                    help="切分标点层级（可多次指定，先高后低；默认 %s——逗号族/顿号/破折号）" % "/".join(DEFAULT_PUNCT_LEVELS))
    args = ap.parse_args()
    punct_levels = args.punct_levels or DEFAULT_PUNCT_LEVELS

    en_blocks = collect_chunk_files(args.en_dir)
    zh_blocks = collect_chunk_files(args.zh_dir)
    if not en_blocks and not zh_blocks:
        sys.exit("❌ 输入目录无块文件")
    en_out = os.path.join(args.out, "r03_normalized_1")
    zh_out = os.path.join(args.out, "r03_normalized_2")
    os.makedirs(en_out, exist_ok=True)
    os.makedirs(zh_out, exist_ok=True)

    keys = sorted(set(en_blocks) | set(zh_blocks))
    n_en = n_zh = 0
    for k in keys:
        if k in en_blocks:
            with open(en_blocks[k], encoding="utf-8") as fh:
                sents = split_en(fh.read())
            n_en += len(sents)
            with open(os.path.join(en_out, "chunk_%03d.txt" % k), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(render("E", sents))
            if args.verbose:
                print(f"   chunk_{k:03d}（EN）: {len(sents)} 句")
        if k in zh_blocks:
            with open(zh_blocks[k], encoding="utf-8") as fh:
                sents = split_zh(fh.read())
            n_zh += len(sents)
            zh_sents = [(f"Z{i}", s) for i, s in enumerate(sents, 1)]
            with open(os.path.join(zh_out, "chunk_%03d.txt" % k), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(render_zh_template(zh_sents, args.soft_min, args.soft_max, args.hard_max,
                                            args.min_unit, punct_levels))
            if args.verbose:
                print(f"   chunk_{k:03d}（ZH）: {len(sents)} 句（r03 模板骨架）")
    print(f"✅ 预分句完成：EN {len(en_blocks)} 块 / {n_en} 句 → {en_out}；ZH {len(zh_blocks)} 块 / {n_zh} 句（r03 模板骨架）→ {zh_out}")
    print(f"   ZH 断句参数: 目标区间 [{args.soft_min:.0f},{args.soft_max:.0f}] 硬 ≤{args.hard_max:.0f} 最小单元 ≥{args.min_unit:.0f}；"
          f"切分标点层级（高→低）{' → '.join(punct_levels)}")
    return 0


if __name__ == "__main__":
    main()
