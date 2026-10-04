# -*- coding: utf-8 -*-
"""ASR 触发清单覆盖率校验闸门（可执行方案 §五 5.4）。

## 判定三级（全部纯字符串 + 结构，零语义判断）

| 级 | 判据 | 处置 |
|---|---|---|
| **已决策** | 同 cue 存在决策行，且原词列与变体**互为包含**（容忍 subagent 写上下文片段，如 `a compar` ↔ `compar`） | 通过 |
| **改后未登记** | 无匹配决策行，但该 cue **输出 SRT 文本已不含变体**（确实改了、只是没登记） | 提示（不拦） |
| **未处理** | 无匹配决策行，且变体**仍在输出 SRT 中**（没改也没登记） | **打回** |

    `[ASR 推测]` / `[待审核]` 等**不合规**来源单独报，不与“未处理”混淆。
`.asr.tsv` 的 `c<idx>` 是**全局 cue 号**，而块 SRT 片段（`chunk_<k>.srt`）的段号
是**块内从 1 连续**的 → 不能按段号对位。故按**起始时间码**定位：先由
`_en_chunks/chunk_<k>.txt` 建立 `cue → (start, 块号)`，再在输出 SRT 里按时间码取值。

## 用法（命令根 = Project_Main/）

  python scripts/asr_check_trigger.py --video <工作目录> [--chunk <k>] [--expand]

默认只报未处理项数量（按块统计）；`--expand` 展开明细；`--chunk <k>` 单块
（单块模式默认展开该块详情）。

**退出码只由“未处理”决定**——来源口径不符与“改后未登记”均为**提示级**：
前者说明该项实际已被消化（只是没按 `[ASR]`/`[放行]` 登记），后者说明确实改了、
只是漏登清单行。二者都不该触发整块重派，混为一谈会误伤已完成的工作。

## ⚡ 若发现“误纠”→ 这是重议 Y 层的触发信号

本闸门**只查清单是否被消化，不判改动对错**。但若在人工审核中发现**真实误纠**
（定稿里本身正确的词被改坏，尤其**同形异义**类如 `note`→node / `minecraft`→minecart）：

- 这构成重议 Y 层（S 层加“需语境”标注）的**触发条件**——Y 层当初被否定正是因为
  **误纠实例 = 0**（223 条决策 / 7 视频），无收益可赚
- 处置：先重跑第 0 步探针确认（`References/ASR修正-实测资料/pre-implementation/`
  的 `_y_layer_step0_misrefix.py`，在 `Project_Main/` 下执行），
  确有实例再开 A/B（`scripts/_dev/asr_bench_b.py gen` 基础设施已具备）
- 完整判据与背景见：`References/ASR修正-实测资料/pre-implementation/Y_LAYER_VERIFICATION.md`
"""
import argparse
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from shared.asr_common import normalize  # noqa: E402

TRIGGERS_NAME = os.path.join("asr_trigger", "triggers.tsv")
RESULTS_DIR = "_en_results"
CHUNKS_DIR = "_en_chunks"

# 合规决策来源（任务文件 `## 输出` 节的来源枚举）
DECIDED = ("[ASR]", "[放行]")
# 已知来源枚举（用于区分“写错口径”与“莫名来源”）
KNOWN_SOURCES = ("[ASR]", "[ASR 推测]", "[待审核]", "[放行]")

# 判定状态
STATE_DECIDED = "decided"      # 有合规决策行
STATE_UNLOGGED = "unlogged"    # 无决策行，但输出已改（提示，不拦）
STATE_WRONG_SRC = "wrong-src"  # 有决策行但来源不合规
STATE_PENDING = "pending"      # 无决策行且输出仍含变体（打回）


def read(path):
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def parse_triggers(path):
    """清单 tsv → `[(cue, timestamp, layer, variant, corrects)]`（跳过 `#` 注释）。"""
    items = []
    for ln in read(path).splitlines():
        s = ln.rstrip()
        if not s or s.startswith("#"):
            continue
        if "\t" in s:
            cue_s, rest = s.split("\t", 1)
        else:
            cue_s, rest = s.split(None, 1)
        m = re.match(r"^c(\d+)$", cue_s.strip())
        if not m:
            continue
        parts = [p.strip() for p in rest.split(" | ")]
        if len(parts) < 4:
            continue
        items.append((int(m.group(1)), parts[0], parts[1], parts[2], parts[3]))
    return items


def parse_asr_tsv(path):
    """`.asr.tsv` → `[(cue, orig, source)]`。

    格式：`c<idx>\t<时间码>\t<原词>\t<新词>\t<来源>`。
    来源列按 **`[...]` 形态**识别（取最后一个方括号列）——兼容历史产物中
    缺来源列的 4 列行，也不会把“新词”误当来源。
    """
    out = []
    for ln in read(path).splitlines():
        if not ln.strip():
            continue
        cols = [c.strip() for c in ln.rstrip("\n").split("\t")]
        if len(cols) < 3:
            continue
        m = re.match(r"^c(\d+)$", cols[0])
        if not m:
            continue
        source = next((c for c in reversed(cols[3:]) if re.fullmatch(r"\[[^\]]*\]", c)), "")
        out.append((int(m.group(1)), cols[2], source))
    return out


def parse_srt_by_start(path):
    """输出 SRT → `{起始时间码: 文本}`（块内段号不可靠，故按时间码定位）。"""
    out = {}
    if not os.path.exists(path):
        return out
    text = read(path).replace("\r\n", "\n")
    for blk in re.split(r"\n\s*\n", text):
        lines = [x for x in blk.split("\n") if x.strip()]
        ti = next((i for i, x in enumerate(lines) if "-->" in x), None)
        if ti is None:
            continue
        start = lines[ti].split("-->")[0].strip()
        out[start] = " ".join(lines[ti + 1:]).strip()
    return out


def cue_index(chunks_dir):
    """`_en_chunks/` → `({cue: (start, 块号)}, {块号: (min_cue, max_cue)})`。

    只取 **OWNED** 段——CONTEXT 段的 cue 不属该块产出，登记与归属都不在它。
    """
    by_cue, ranges = {}, {}
    if not os.path.isdir(chunks_dir):
        return by_cue, ranges
    for fn in sorted(os.listdir(chunks_dir)):
        m = re.fullmatch(r"chunk_(\d+)\.txt", fn)
        if not m:
            continue
        k = int(m.group(1))
        in_owned, cids = False, []
        for ln in read(os.path.join(chunks_dir, fn)).splitlines():
            if ln.startswith("## "):
                in_owned = ln.startswith("## OWNED")
                continue
            if not in_owned:
                continue
            mm = re.match(r"^c(\d+)\t([^ \t]+)", ln)
            if not mm:
                continue
            cue, start = int(mm.group(1)), mm.group(2)
            by_cue[cue] = (start, k)
            cids.append(cue)
        if cids:
            ranges[k] = (min(cids), max(cids))
    return by_cue, ranges


def mutual_contain(a, b):
    """归一化后互为包含（按词边界）——容忍 `a compar` ↔ `compar` 这类上下文片段。"""
    if a == b:
        return True
    return re.search(r"(?<![a-z0-9])" + re.escape(b) + r"(?![a-z0-9])", a) is not None \
        or re.search(r"(?<![a-z0-9])" + re.escape(a) + r"(?![a-z0-9])", b) is not None


def still_present(by_start_text, start, variant):
    """该 cue 的输出文本是否仍含变体（归一化整串，词边界）。

    定位不到该时间码时**保守判为仍在**——宁可多报一次提示，不放过真漏判。
    """
    body = by_start_text.get(start)
    if body is None:
        return True
    return re.search(r"(?<![a-z0-9])" + re.escape(normalize(variant)) + r"(?![a-z0-9])",
                     normalize(body)) is not None


def scan(video_dir, chunk_filter):
    """→ `(records, stats)`。

    `records` = `[(状态, cue, ts, layer, variant, corrects, 块号, 备注)]`。
    状态四值见模块 docstring 与 `STATE_*` 常量；`wrong-src` 表示
    “有决策行但来源口径不合规”。
    """
    tpath = os.path.join(video_dir, TRIGGERS_NAME)
    if not os.path.exists(tpath):
        return None, {"error": "清单不存在：%s（先跑 asr_trigger.py scan）" % tpath}

    items = parse_triggers(tpath)
    rdir = os.path.join(video_dir, RESULTS_DIR)
    if not os.path.isdir(rdir):
        return None, {"error": "结果目录不存在：%s" % rdir}

    by_cue, ranges = cue_index(os.path.join(video_dir, CHUNKS_DIR))

    # cue 号 → [(归一化原词, 原词, 来源)]；一个 cue 可有多条决策行
    decisions, sources_seen = {}, set()
    files = sorted(f for f in os.listdir(rdir) if f.endswith(".asr.tsv"))
    for fn in files:
        mk = re.fullmatch(r"chunk_(\d+)\.asr\.tsv", fn)
        if not mk:
            continue
        for cue, orig, source in parse_asr_tsv(os.path.join(rdir, fn)):
            decisions.setdefault(cue, []).append((normalize(orig), orig, source))
            if source:
                sources_seen.add(source)

    # 输出 SRT 文本（判“确实改了但没登记”用）；缺文件的块单独提示
    out_text, missing_srt = {}, []
    for k in sorted(ranges):
        p = os.path.join(rdir, "chunk_%03d.srt" % k)
        if not os.path.exists(p):
            missing_srt.append(k)
        out_text.update(parse_srt_by_start(p))

    records = []
    for cue, ts, layer, variant, corrects in items:
        start, k = by_cue.get(cue, (None, None))
        if chunk_filter and k != chunk_filter:
            continue
        vn = normalize(variant)
        hit = next((r for r in decisions.get(cue, []) if mutual_contain(r[0], vn)), None)
        if hit:
            if hit[2] in DECIDED:
                records.append((STATE_DECIDED, cue, ts, layer, variant, corrects,
                                k, hit[2]))
            else:
                records.append((STATE_WRONG_SRC, cue, ts, layer, variant, corrects,
                                k, hit[2] or "（来源空）"))
        elif start is not None and not still_present(out_text, start, variant):
            records.append((STATE_UNLOGGED, cue, ts, layer, variant, corrects,
                            k, "输出文本已无该变体"))
        elif decisions.get(cue):
            # 该 cue 有决策行，但都没匹配上变体（决策漏项 / 原词列写法不兼容）
            records.append((STATE_PENDING, cue, ts, layer, variant, corrects,
                            k, "同 cue 有决策行但不含该变体"))
        else:
            records.append((STATE_PENDING, cue, ts, layer, variant, corrects, k, ""))

    stats = {
        "items": len(items),
        "files": files,
        "ranges": ranges,
        "missing_srt": missing_srt,
        "unknown_sources": sorted(s for s in sources_seen if s not in KNOWN_SOURCES),
    }
    return records, stats


def counts_by_chunk(rows):
    """按块归类 → `{块号: 条数}`（无法归属记为 None）。"""
    counts = {}
    for rec in rows:
        counts[rec[6]] = counts.get(rec[6], 0) + 1
    return counts


def label(k):
    return "未归属块" if k is None else "块 %03d" % k


def print_rows(rows, title):
    print("%s %d 项：" % (title, len(rows)))
    counts = counts_by_chunk(rows)
    for k in sorted(counts, key=lambda x: (x is None, x if x is not None else 0)):
        print("  - %s：%d 项" % (label(k), counts[k]))
    for rec in rows:
        _state, cue, ts, layer, variant, corrects, k, note = rec
        extra = "（%s）" % note if note else ""
        print("    · %s c%d %s | %s | %s → %s%s"
              % (label(k), cue, ts, layer, variant, corrects, extra))


def main():
    ap = argparse.ArgumentParser(description="ASR 触发清单覆盖率校验闸门（只读）")
    ap.add_argument("--video", required=True, help="视频工作目录（相对 Project_Main，如 _work/<视频名>）")
    ap.add_argument("--chunk", type=int, help="只校验该块")
    ap.add_argument("--expand", action="store_true", help="展开问题项明细")
    args = ap.parse_args()

    video_dir = args.video if os.path.isabs(args.video) \
        else os.path.join(BASE, args.video)
    records, stats = scan(video_dir, args.chunk)
    if records is None:
        print("错误：%s" % stats["error"], file=sys.stderr)
        return 1

    expand = args.expand or args.chunk is not None  # 单块模式默认展开
    print("ASR 触发清单校验（%s）：清单 %d 项；决策文件 %s"
          % ("块 %03d" % args.chunk if args.chunk else "全部块",
             stats["items"], "、".join(stats["files"]) or "无"))
    if stats["missing_srt"]:
        print("提示：缺输出 SRT（无法判“已改未登记”）——块 %s"
              % "、".join("%03d" % k for k in stats["missing_srt"]))
    if stats["unknown_sources"]:
        print("警告：`.asr.tsv` 出现未知来源口径 %s（枚举见任务文件 `## 输出` 节）"
              % "、".join(stats["unknown_sources"]), file=sys.stderr)

    pending = [r for r in records if r[0] == STATE_PENDING]
    wrong = [r for r in records if r[0] == STATE_WRONG_SRC]
    unlogged = [r for r in records if r[0] == STATE_UNLOGGED]
    decided = len(records) - len(pending) - len(wrong) - len(unlogged)

    if not pending:
        print("通过：清单 %d 项均已被消化（%d 项匹配决策行；%d 项改后未登记；"
              "%d 项用了其他来源口径）。"
              % (len(records), decided, len(unlogged), len(wrong)))
        if wrong and expand:
            print_rows(wrong, "来源口径提示（已消化，但建议统一为 [ASR] / [放行]）")
        if unlogged and expand:
            print_rows(unlogged, "改后未登记（建议补 `[ASR]` 行）")
        return 0

    print_rows(pending, "未处理（打回：既未修正也未放行）")
    if wrong:
        print("另有 %d 项用了其他来源口径（已消化，提示级，不计入打回）——`--expand` 看明细。"
              % len(wrong))
    if unlogged:
        print("另有 %d 项改后未登记（提示级，不计入打回）——`--expand` 看明细。" % len(unlogged))
    if expand:
        if wrong:
            print_rows(wrong, "来源口径提示（已消化，但建议统一为 [ASR] / [放行]）")
        if unlogged:
            print_rows(unlogged, "改后未登记（建议补 `[ASR]` 行）")
    return 1


if __name__ == "__main__":
    sys.exit(main())
