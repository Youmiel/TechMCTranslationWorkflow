# -*- coding: utf-8 -*-
"""术语表加载集判定：常驻集 + 命中数驱动的领域表候选 + 用户门禁。

## 常驻集

无条件加载 `RESIDENT` 列出的表：L1 项目库 5 张（`engineering` / `_uncategorized` /
`community` / `proper_nouns` 及红石专属）+ L2 的 `general`。其中前 5 张由表价值排名得出：

    V = √(无条件份额) × √(次/词) ÷ 表词数
      无条件份额 = share × hit_ratio
      （share 是条件平均，只对命中的视频取平均，会漏掉广度，故乘广度修正）

`proper_nouns` 为特例常驻：人名/社区名几乎每个视频都会出现，按需加载收益低；
而模式触发会漏检（宽模式几乎全触发、等价常驻；紧模式漏掉大半）——勿再尝试模式触发。
实际表清单与词数用 `--list-resident` 查，勿在文档里写死。

## 领域表：命中数阈值 → 候选 → 用户门禁

用字幕全文扫全部非 L1.5 表，命中的词条数达阈值者列为候选：

    非常驻表若“命中词条数 ≥ 阈值”→ 候选
    → 报用户门禁确认（用户剔除非必要表）→ 裁定后即最终加载集
    → 探测范围与用户决策记入门禁日志

**为何用阈值而非算法挑表**：子代理上下文远未用满，宁可多纳候选、由用户在门禁处剔除，
不用算法替代人的判断。阈值不合适用 `--threshold` 调整，日志的“未达阈值”列是依据。

**计数用“命中词条数”而非总次数**：总次数被长视频与重复词支配——一个噪声词反复出现即可刷高。
条数单位是表内词条（`;` 同义词与 `(aka X)` 别名已展开为独立词条），不折叠形态变体。

**为何逐表扫而非扫合并索引**：`glossary_lookup.build_term_index` 同词多源只留层级最高者，
合并后某表的独占词会归到别的表名下 → 命中数被低估、表会漏出候选。

**只扫 L1 与 L2**：L1.5 按设计不注入 ASR 通道，扫了无用；其通用词形还会产生大量噪声命中。

**不用 `glossary_categories.yaml` 的 keywords 判领域**：keywords 覆盖面与字幕实际用语脱节，
判不出领域的视频占比高。改以字幕实际命中为准。

## 输出（默认 `_work/<视频>/`）

| 文件 | 内容 |
|---|---|
| `glossary_load_plan.md` | 常驻集 + 领域表候选（含命中数）+ 门禁问题 + 探测全貌 |
| `glossary_gate_log.md` | 门禁日志（追加式）：探测范围（含未达阈值表）→ 用户决策 |

**日志为何记“未达阈值”的表**：只记候选则看不到“差一点就进的”，
日后无法判断阈值定高还是定低。

用法（命令根 = Project_Main/）：
  python scripts/glossary_load_plan.py <字幕.srt> [--threshold N] [--out <报告>]
  python scripts/glossary_load_plan.py <字幕.srt> --record "<用户剔除的表，逗号分隔>"
  python scripts/glossary_load_plan.py <字幕.srt> --record           # 候选全保留
  python scripts/glossary_load_plan.py <字幕.srt> --json
  python scripts/glossary_load_plan.py --list-resident
"""
import argparse
import json
import os
import re
import sys
from datetime import date

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shared.glossary_sources import iter_terms      # noqa: E402
import glossary_hit_rate as GH                      # noqa: E402
import glossary_lookup as GL                        # noqa: E402

# ---- 常驻集（表价值排名前 5 + `proper_nouns` 特例）----
# 注意：`.cache/` 下的表在报告里显示为无前缀形式（`mojang/redstone.csv`），
# 但实际路径在 `.cache/` 下 —— 由 `resolve()` 统一处理，勿直接拼路径。
RESIDENT = (
    "knowledge/01_terminology/engineering.csv",
    "mojang/redstone.csv",
    "knowledge/01_terminology/_uncategorized.csv",
    "glossary/general.csv",
    "knowledge/01_terminology/community.csv",
    # 特例：专有名词表常驻（见模块 docstring 的“常驻集”节）
    "knowledge/01_terminology/proper_nouns.csv",
)

# 候选阈值：非常驻表的“命中词条数”≥ 此值 → 纳入候选
DEFAULT_THRESHOLD = 3

# 不参与候选的表：`_example` 是模板；`people`（1 词）与 `proper_nouns` 重叠
EXCLUDE_FROM_CANDIDATE = ("_example.csv", "glossary/people.csv")


def resolve(rel):
    """报告用的简名 → 实际绝对路径（自动补 `.cache/`）。找不到返回 None。"""
    for cand in (rel, os.path.join(".cache", rel),
                 os.path.join(".cache", "mojang", os.path.basename(rel)),
                 os.path.join(".cache", "glossary", os.path.basename(rel))):
        p = os.path.join(BASE, cand)
        if os.path.exists(p):
            return p
    return None


def all_sources():
    """现存词表：[(层, 相对路径, 绝对路径)]。"""
    out = []
    for lv, sub in (("L1", "knowledge/01_terminology"),
                    ("L2", ".cache/glossary"),
                    ("L1.5", ".cache/mojang")):
        d = os.path.join(BASE, sub)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".csv") or fn.startswith("_"):
                continue
            rel = f"{sub}/{fn}".replace(".cache/", "")
            out.append((lv, rel, os.path.join(d, fn)))
    return out


def word_count(path):
    """表内词条数（含缩写展开）。"""
    if not path or not os.path.exists(path):
        return 0
    return sum(len(t) + len(s) for t, _z, s in iter_terms(path))


def read_srt_text(path):
    """SRT → 全文（拼所有 cue 文本）。"""
    with open(path, encoding="utf-8-sig") as f:
        text = f.read()
    bodies = []
    for block in re.split(r"\n\s*\n", text):
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) >= 3 and "-->" in lines[1]:
            bodies.append(" ".join(lines[2:]))
    return " ".join(bodies)


def abs_path(p):
    """绝对且规范化（Windows 大小写不敏感，故小写化以便比较）。"""
    return os.path.normcase(os.path.normpath(os.path.abspath(p)))


def scan_all(sub_text, excluded_abs):
    """用字幕全文**逐表**扫非 L1.5 表 → 每表命中词条数（**不设阈值**）。

    **为何逐表扫而不是扫合并索引**：`build_term_index` 同词多源只留层级最高者，
    合并后某表的独占词会归到别的表名下 → 命中数被低估、表可能漏出候选。
    逐表建索引需对每表各做一次全文字符串扫描，比合并扫描慢，但**计数准确**。

    只扫 L1 与 L2：L1.5（Mojang 通用词）按设计不注入（见 `use-glossary` skill），
    扫了也无用；且其词形（`water`/`sand`）会产生大量噪声命中。

    返回 `{表名: (命中词条数, 命中词列表, 层)}`（**含常驻表**，由调用方筛）。
    """
    hard, soft = GH.load_stopwords(None)
    out = {}
    for lv, rel, p in all_sources():
        if lv == "L1.5":
            continue
        if rel in EXCLUDE_FROM_CANDIDATE or abs_path(p) in excluded_abs:
            continue
        idx = GL.build_term_index([(lv, p)])
        rx = GL.make_matcher(idx)
        if rx is None:
            continue
        hits = set()
        for m in rx.finditer(sub_text):
            w = m.group(0)
            if GH.word_class(w, hard, soft) == "hard":
                continue
            hits.add(w.strip().lower())
        if hits:
            out[rel] = (len(hits), sorted(hits), lv)
    return out


def write_gate_log(video_dir, srt, threshold, scanned, resident_set, removed, note=""):
    """追加一条门禁日志：**探测范围**（含未达阈值的表）→ 用户决策。

    故意把“未达阈值”也记入：否则日后无法判断阈值定高还是定低
    （只记候选 → 看不到“差一点就进了”的表）。
    """
    p = os.path.join(video_dir, "glossary_gate_log.md")
    new = not os.path.exists(p)

    cand = sorted(((t, n) for t, (n, _w, _lv) in scanned.items()
                   if t not in resident_set and n >= threshold),
                  key=lambda x: (-x[1], x[0]))
    below = sorted(((t, n) for t, (n, _w, _lv) in scanned.items()
                    if t not in resident_set and n < threshold),
                   key=lambda x: (-x[1], x[0]))
    res_hit = sorted(((t, n) for t, (n, _w, _lv) in scanned.items()
                      if t in resident_set), key=lambda x: (-x[1], x[0]))
    keep_txt = "、".join(t for t, _n in cand if t not in removed) or "（无）"

    def short(p):
        """表路径 → 短名（去目录、去 .csv）——供压缩日志宽度。"""
        return os.path.splitext(os.path.basename(p))[0]

    with open(p, "a", encoding="utf-8") as f:
        if new:
            f.write("# 术语表门禁日志\n\n")
            f.write("> 追加式。每行 = 一次门禁：**探测范围**（含差一点就进的）→ **用户决策**。\n")
            f.write("> 用途：事后判断阈值定高/定低、哪些表用户总剔、哪些表反复出现却总未达阈值。\n\n")
            f.write("| 日期 | 视频 | 阈值 | 候选（表:命中） | 未达阈值（表:命中） | 用户剔除 | 最终增载 | 备注 |\n")
            f.write("|---|---|---|---|---|---|---|---|\n")
        def fmt(rows):
            return "、".join(f"{short(t)}:{n}" for t, n in rows) or "（无）"
        # 视频名优先取字幕所在目录名（比字幕文件名更有辨识度）
        vname = os.path.basename(os.path.dirname(os.path.abspath(srt))) or os.path.basename(srt)
        f.write(f"| {date.today().isoformat()} | {vname[:40]} | ≥{threshold} | "
                f"{fmt(cand)} | {fmt(below)} | "
                f"{'、'.join(short(r) for r in removed) if removed else '（未剔除）'} | "
                f"{'、'.join(short(t) for t, _n in cand if t not in removed) or '（无）'} | "
                f"{note or ('常驻命中 ' + fmt(res_hit) if res_hit else '')} |\n")
    return p


def main():
    ap = argparse.ArgumentParser(description="术语表加载集判定 + 用户门禁")
    ap.add_argument("srt", nargs="?", help="字幕（原始 ASR 或 00）；--list-resident 时可省略")
    ap.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                    help=f"候选阈值：命中词条数 ≥ 此值（默认 {DEFAULT_THRESHOLD}）")
    ap.add_argument("--out", help="报告输出路径（默认 <字幕目录>/glossary_load_plan.md）")
    # nargs="?" + const：允许 `--record` 单独出现 = “候选全保留”（PowerShell
    # 会把裸 `""` 吃掉，故不能用空串传参）
    ap.add_argument("--record", nargs="?", const="", default=None,
                    help="记录用户决策：逗号分隔的**被剔除表名**（写入门禁日志）。"
                         "省略参数值（`--record`）= 候选全保留")
    ap.add_argument("--note", default="", help="门禁日志的备注（可选）")
    ap.add_argument("--json", action="store_true", help="输出 JSON（供程序消费）")
    ap.add_argument("--list-resident", action="store_true", help="只打印常驻集")
    args = ap.parse_args()

    # 常驻集：读词数
    resident = []
    for rel in RESIDENT:
        p = resolve(rel)
        resident.append({"table": rel,
                         "path": os.path.relpath(p, BASE).replace("\\", "/") if p else None,
                         "words": word_count(p), "exists": bool(p)})
    res_words = sum(r["words"] for r in resident)

    if args.list_resident:
        for r in resident:
            print(f"{r['table']:52s} {r['words']:5d} 词  {r['path'] or '（缺失）'}")
        print(f"{'小计':52s} {res_words:5d} 词")
        return
    if not args.srt:
        sys.exit("需要字幕路径（或 --list-resident）")

    excluded = {abs_path(resolve(x)) for x in EXCLUDE_FROM_CANDIDATE if resolve(x)}
    resident_rel = set(RESIDENT)
    # 无论是否记录决策，都重新扫描：门禁日志需要**完整探测范围**
    # （含未达阈值的表）——否则日后无法判断阈值定高/定低。
    scanned = scan_all(read_srt_text(args.srt), excluded)

    # 候选 = 非常驻 & 命中 ≥ 阈值；below = 非常驻 & 命中 < 阈值（供判断阈值是否合适）
    cand = sorted(((t, n, w, lv) for t, (n, w, lv) in scanned.items()
                   if t not in resident_rel and n >= args.threshold),
                  key=lambda x: (-x[1], x[0]))
    below = sorted(((t, n, w, lv) for t, (n, w, lv) in scanned.items()
                    if t not in resident_rel and n < args.threshold),
                   key=lambda x: (-x[1], x[0]))
    res_hit = sorted(((t, n) for t, (n, _w, _lv) in scanned.items()
                      if t in resident_rel), key=lambda x: (-x[1], x[0]))
    candidates = cand
    removed = [x.strip() for x in (args.record or "").split(",") if x.strip()]
    # 剔除项允许用简名（`tree_farm`）或全名，统一成报告里的全名
    for i, r in enumerate(removed):
        if r in scanned:
            continue
        for t in scanned:
            if os.path.basename(t) == r or t.endswith("/" + r):
                removed[i] = t
                break

    plan = {
        "srt": args.srt,
        "threshold": args.threshold,
        "resident": resident,
        "resident_words": res_words,
        "candidates": [{"table": t, "hits": n, "sample": s, "level": lv}
                       for t, n, s, lv in candidates],
        "below_threshold": [{"table": t, "hits": n, "level": lv}
                            for t, n, _s, lv in below],
        "resident_hits": [{"table": t, "hits": n} for t, n in res_hit],
        "removed": removed,
    }

    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return

    # ---- 报告 ----
    L = []
    L.append("# 术语表加载集判定（含用户门禁）")
    L.append("")
    L.append(f"- 字幕：`{os.path.relpath(args.srt, BASE)}`")
    L.append(f"- 候选阈值：命中词条数 ≥ **{args.threshold}**")
    L.append("")
    L.append("## 一、常驻集（无条件加载，共 {} 词）".format(res_words))
    L.append("")
    L.append("| 表 | 词数 | 实际路径 |")
    L.append("|---|---|---|")
    for r in resident:
        mark = "" if r["exists"] else " **（缺失）**"
        L.append(f"| `{r['table']}`{mark} | {r['words']:,} | `{r['path'] or '—'}` |")
    L.append("")
    L.append("> 排名前 5 由表价值公式得出；`proper_nouns` 为**特例**"
             "（人名/社区名几乎每个视频都出现，按需加载会在漏检中丢失）。")
    L.append("")

    L.append(f"## 二、领域表候选（命中 ≥ {args.threshold} 条）")
    L.append("")
    if not candidates:
        L.append("**（无候选）**——字幕未触及任何阈值以上的领域表。")
        L.append("")
        L.append("> 可考虑：`--threshold` 降低，或确认字幕是否过短。")
    else:
        L.append("| 表 | 层 | **命中条数** | 命中样例 |")
        L.append("|---|---|---|---|")
        for t, n, s, lv in candidates:
            samp = "、".join(f"`{w}`" for w in s[:4]) if s else "—"
            L.append(f"| `{t}` | {lv} | **{n}** | {samp} |")
        L.append("")

    L.append("## 三、★ 门禁确认（请用户裁定）")
    L.append("")
    L.append(f"拟加载 = **常驻 {len(resident)} 表（{res_words} 词）** + "
             f"**候选 {len(candidates)} 表**")
    L.append("")
    if candidates:
        L.append("请从候选中**剔除本视频用不到的表**（其余视为加载）。")
        L.append("")
        L.append("剔除方式（二选一）：")
        L.append("")
        L.append("1. 直接回复要剔除的表名（逗号分隔）")
        L.append("2. 或运行：`python scripts/glossary_load_plan.py <字幕> "
                 f"--record \"表1,表2\"`")
        L.append("")
        L.append("> 无论哪种，均会写入门禁日志 `glossary_gate_log.md`"
                 "（探测范围 → 用户决策）。")
    else:
        L.append("**无候选需裁定**——直接用常驻集即可。")
    L.append("")

    # 全貌：供判断阈值是否合适（否则只看到候选，不知有没有“差一点就进的”）
    L.append("## 四、探测全貌（阈值校准用）")
    L.append("")
    if below:
        L.append(f"未达阈值（命中 < {args.threshold}）的非常驻表，按命中降序：")
        L.append("")
        L.append("| 表 | 命中条数 |")
        L.append("|---|---|")
        for t, n, _w, _lv in below:
            L.append(f"| `{t}` | {n} |")
        L.append("")
    else:
        L.append(f"未达阈值：**无**（所有命中的非常驻表均 ≥ {args.threshold}）——"
                 f"阈值可能定低了。")
        L.append("")
    if res_hit:
        L.append("常驻表命中情况（仅作对照，不影响加载）：")
        L.append("")
        L.append("| 表 | 命中条数 |")
        L.append("|---|---|")
        for t, n in res_hit:
            L.append(f"| `{t}` | {n} |")
        L.append("")
    L.append("未列出的表 = 命中 **0**。")
    L.append("")

    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.srt)),
                                   "glossary_load_plan.md")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"已写入 {out}")
    print(f"  常驻 {len(resident)} 表 / {res_words} 词；候选 {len(candidates)} 表"
          f"（阈值 ≥{args.threshold}）")

    # ---- 门禁日志 ----
    if args.record is not None:
        vd = os.path.dirname(os.path.abspath(args.srt))
        lp = write_gate_log(vd, args.srt, args.threshold, scanned, resident_rel,
                            removed, args.note)
        print(f"  已追加门禁日志：{lp}（剔除 {len(removed)} 表）")


if __name__ == "__main__":
    main()
