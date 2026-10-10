# -*- coding: utf-8 -*-
"""vocalign 骨架构建：把“词级时轴 + 自带标点”变成三层骨架（长句 / 子句 / 词）

定位
    vocalign 工作流的**纯脚本核心**（零 LLM、零第三方依赖）。输入是语音识别工具直出的
    词级时轴（每个词带起止时间与词尾标点），输出带真实时间的三层结构：

        长句 = 句末标点（.?!）或 净停顿 ≥ 500ms
        子句 = 逗号/分号    或 净停顿 ≥ 250ms      ← 现行 reflow2 缺的一层
        词   = 词级时间戳（+ 词尾标点）

    时间与断句从**同一来源**获得，不再靠字符比例插值或吸附兜补。

判据（净停顿 = 原始词间间隙 − 伪间隙 baseline）
    wav2vec2 的词边界会收缩到声学核心，导致词间出现系统性 ~40ms 伪间隙（句内 p50 = 40ms）。
    不减 baseline 会把所有词间都判成停顿，故必须扣除。
    实测判别力（似然比 @500ms = 46.5）远超纯音频能量谷法（1.2–1.7）。

输入契约（`--words`，JSON）
    {"words": [{"start": 0.74, "end": 1.142, "text": "Repeaters", "score": 0.8},
               {"start": null, "end": null, "text": "15.", "score": null},  ← 未对齐词占位
               ...]}
    ⚠️ **未对齐词必须保留占位**（start/end 为 null）。whisperX 约 2.6% 词对齐失败，实测几乎
       全是数字（`15.` / `3` / `8, 8` / `20`）。若采集时丢弃，词序列出现“空洞”→ 前后词
       直接相邻 → 跨空洞的间隙被误判为停顿边界，实测伪边界：`values of | and`（原文
       "values of 1 and 2"）。本脚本对 null 词按前后锚点插值补齐。

    `--srt` 为**可选诊断**参数（补全未对齐词、用完整文本对照），设计上不依赖。

输出（`-o` 目录）
    `skeleton.json`   三层骨架（机器消费）
    `skeleton.txt`    人工抽查材料
    `boundaries.txt`  全部词间边界的判据明细（调参用）
    `long_lines.srt`  **初版 SRT 载体**（长句 + 语音实测时间；cue 号 ≡ S 号）
      —— 供 `text_chunk.py` 分块（**分块只需长句边界 + 时间，与文本内容无关**）。
      为何由骨架产：E0 的清单要按块、分块又需载体 → 循环；先出**初版**打破它：
      骨架 → 分块 → E0 定稿（按块）→ **重跑分块**（吃 E0 定稿载体，使块内文本 = 定稿文本）

用法（命令根 = Project_Main/）
    python scripts/vocalign_skeleton.py --words <work>/vocalign/words.json -o <work>/vocalign/
    python scripts/vocalign_skeleton.py --words ... --srt <诊断用 segments.srt> -o ... --expand

退出码：0 = 成功；1 = 输入缺失或空洞词过多（>10%，需复核采集结果）。
"""
import argparse
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

# ---- 判据常量（与 docs/PRODUCT_FORMATS_VOCALIGN.md 同步）----
BASELINE_MS = 40.0        # 伪间隙 baseline（wav2vec2 词边界收缩，句内 p50）
SENT_MS = 500.0           # 净停顿 ≥ 此值 → 强句界
CLAUSE_MS = 250.0         # 净停顿 ≥ 此值 → 子句界
CLAUSE_UPGRADE_MS = 0.0   # 逗号后净停顿 ≥ 此值 → 升级为句界（0 = 不升级）
HOLE_WARN_RATIO = 0.10    # 未对齐词占比超此值即告警

TERM = ".?!"                                        # 句末标点
CLAUSE = ",;:\u2014\u2013"                          # 子句标点
TRIM = set(".,;:!?\u2014\u2013\"')]")               # 词尾可剥离标点
# 句首小写判据：跳过引号/括号前缀后取首字母
FIRST_LETTER_RE = re.compile(r"[\"'(\[\u201c\u300c\u300e]*([A-Za-z])")

SRT_TIME = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})"
)


# ---------------------------------------------------------------- 基础工具

def hms(sec):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)


def split_punct(tok):
    """拆词尾标点：`comparators,` → ('comparators', ',')"""
    t = tok.strip()
    i = len(t)
    while i > 0 and t[i - 1] in TRIM:
        i -= 1
    return t[:i], t[i:]


def render(words):
    """按原样拼回文本：标点紧贴前词，词间单空格"""
    out = ""
    for w in words:
        piece = w["stem"] + w["punct"]
        out = piece if not out else out + " " + piece
    return out


def pct(values, p):
    if not values:
        return None
    xs = sorted(values)
    k = (len(xs) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (k - lo), 1)


def dist(values):
    if not values:
        return {}
    return {"n": len(values), "min": min(values), "p25": pct(values, 25), "p50": pct(values, 50),
            "p75": pct(values, 75), "p90": pct(values, 90), "max": max(values),
            "mean": round(sum(values) / len(values), 1)}


# ---------------------------------------------------------------- 输入

def load_words(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    words = data.get("words") if isinstance(data, dict) else data
    if not words:
        sys.exit("❌ 词级时轴为空或无 words 字段：%s" % path)
    return data.get("meta", {}) if isinstance(data, dict) else {}, words


def read_srt_tokens(path):
    """读 SRT → 完整词序列（保留标点原样），诊断模式用"""
    with open(path, encoding="utf-8-sig") as fh:
        raw = fh.read()
    toks = []
    for block in re.split(r"\n\s*\n", raw.strip()):
        lines = [x for x in block.split("\n") if x.strip()]
        ti = None
        for i, ln in enumerate(lines):
            if SRT_TIME.search(ln):
                ti = i
                break
        if ti is not None:
            toks.extend(" ".join(lines[ti + 1:]).strip().split())
    return toks


def words_to_tokens(words):
    """words 直转 token（主路径）。未对齐词（start 为 None）留在序列里待插值"""
    out = []
    for i, w in enumerate(words):
        stem, punct = split_punct(w["text"])
        st, en = w.get("start"), w.get("end")
        out.append({"i": i, "stem": stem, "punct": punct,
                    "start": None if st is None else float(st),
                    "end": None if en is None else float(en),
                    "score": w.get("score"), "src": "aligned" if st is not None else "hole"})
    return out


def fill_missing_times(toks):
    """未对齐词（时间为 None）按前后锚点插值补齐

    这是抑制“空洞伪边界”的关键：不插值则前后词直接相邻，跨空洞间隙被当成停顿。
    连续 None 段在左右锚点之间均匀分配；无左/右锚点时按 120ms 推定。
    返回统计 dict（原地修改 toks）。
    """
    n = len(toks)
    i = 0
    n_fill = n_synth = 0
    while i < n:
        if toks[i]["start"] is not None:
            i += 1
            continue
        j = i
        while j < n and toks[j]["start"] is None:
            j += 1
        k = j - i
        left = toks[i - 1]["end"] if i > 0 and toks[i - 1]["end"] is not None else None
        right = toks[j]["start"] if j < n and toks[j]["start"] is not None else None
        if left is not None and right is not None and right > left:
            step = (right - left) / k
            for m in range(k):
                toks[i + m]["start"] = round(left + step * m, 3)
                toks[i + m]["end"] = round(left + step * (m + 1), 3)
                toks[i + m]["src"] = "interp"
            n_fill += k
        elif left is not None:
            for m in range(k):
                toks[i + m]["start"] = round(left + 0.12 * m, 3)
                toks[i + m]["end"] = round(left + 0.12 * (m + 1), 3)
                toks[i + m]["src"] = "interp"
            n_fill += k
        elif right is not None:
            for m in range(k):
                toks[i + m]["start"] = round(right - 0.12 * (k - m), 3)
                toks[i + m]["end"] = round(right - 0.12 * (k - m - 1), 3)
                toks[i + m]["src"] = "interp"
            n_fill += k
        else:
            for m in range(k):
                toks[i + m]["start"] = 0.0
                toks[i + m]["end"] = 0.0
                toks[i + m]["src"] = "synth"
            n_synth += k
        i = j
    return {"interp": n_fill, "synth": n_synth, "hole_total": n_fill + n_synth}


def align_times(srt_tokens, words):
    """诊断模式：文本以 srt 为准、时间以 words 为准（缺失词插值）"""
    import difflib
    s_stems = [split_punct(t)[0].casefold() for t in srt_tokens]
    w_stems = [split_punct(w["text"])[0].casefold() for w in words]
    sm = difflib.SequenceMatcher(None, s_stems, w_stems, autojunk=False)
    times = [None] * len(srt_tokens)
    n_aligned = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("equal", "replace"):
            for k in range(min(i2 - i1, j2 - j1)):
                w = words[j1 + k]
                if w.get("start") is None:
                    continue
                times[i1 + k] = (float(w["start"]), float(w["end"]), "aligned")
                n_aligned += 1
    toks = []
    for i, t in enumerate(srt_tokens):
        stem, punct = split_punct(t)
        v = times[i]
        toks.append({"i": i, "stem": stem, "punct": punct,
                     "start": None if v is None else v[0],
                     "end": None if v is None else v[1],
                     "score": None, "src": "aligned" if v else "hole"})
    stats = fill_missing_times(toks)
    stats["aligned"] = n_aligned
    stats["similarity"] = round(sm.ratio(), 4)
    return toks, stats


# ---------------------------------------------------------------- 边界判定

def classify(punct, net_ms, sent_ms, clause_ms, clause_upgrade_ms):
    """返回 (level, why)，level ∈ sent/clause/none"""
    if punct and punct[-1] in TERM:
        return "sent", "punct"
    if punct and any(c in CLAUSE for c in punct):
        if clause_upgrade_ms and net_ms >= clause_upgrade_ms:
            return "sent", "punct+longpause"
        return "clause", "punct"
    if net_ms >= sent_ms:
        return "sent", "pause"
    if net_ms >= clause_ms:
        return "clause", "pause"
    return "none", "none"


def compute_bounds(toks, baseline_ms, sent_ms, clause_ms, clause_upgrade_ms):
    bounds = []
    for i in range(len(toks) - 1):
        a, b = toks[i], toks[i + 1]
        gap = (b["start"] - a["end"]) * 1000.0
        net = gap - baseline_ms
        lvl, why = classify(a["punct"], net, sent_ms, clause_ms, clause_upgrade_ms)
        # 插值/合成词的时间是估算的 → 不作停顿证据
        if why == "pause" and a.get("src") in ("interp", "synth"):
            lvl, why = "none", "interp-skip"
        if a["punct"]:
            conf = "high"
        elif why == "pause" and gap >= sent_ms + baseline_ms:
            conf = "med"
        elif why == "pause":
            conf = "low"
        else:
            conf = None
        bounds.append({"i": i, "after": a["stem"] + a["punct"], "before": b["stem"] + b["punct"],
                       "gap_ms": round(gap, 1), "net_ms": round(net, 1),
                       "level": lvl, "why": why, "conf": conf})
    return bounds


def build(toks, bounds):
    """按边界等级组装长句 / 子句"""
    sentences, clauses, bucket = [], [], []

    def flush_clause():
        if bucket:
            clauses.append({"start": round(bucket[0]["start"], 3), "end": round(bucket[-1]["end"], 3),
                            "nwords": len(bucket), "text": render(bucket)})

    def flush_sentence():
        if clauses:
            sentences.append({"start": clauses[0]["start"], "end": clauses[-1]["end"],
                              "nclauses": len(clauses),
                              "nwords": sum(c["nwords"] for c in clauses),
                              "text": " ".join(c["text"] for c in clauses),
                              "clauses": clauses[:]})

    for i, t in enumerate(toks):
        bucket.append(t)
        lvl = bounds[i]["level"] if i < len(bounds) else "sent"
        if lvl == "sent":
            flush_clause()
            flush_sentence()
            clauses, bucket = [], []
        elif lvl == "clause":
            flush_clause()
            bucket = []
    flush_clause()
    flush_sentence()
    return sentences


def _ends_term(text):
    t = text.rstrip()
    return bool(t) and t[-1] in TERM


def _starts_lower(text):
    """首字母为小写（跳过引号 / 括号前缀）。"""
    m = FIRST_LETTER_RE.match(text.strip())
    return bool(m) and m.group(1).islower()


def stitch_sentences(sentences):
    """碎片归位：前句末尾无句末标点 **且** 后句首字母小写 → 合并为一个长句。

    为什么需要：whisper 是**段级**输出（按静音窗口切段），段边界**不保证与句界一致**——
    段边界落在句中时，本脚本会把它当句界 → 长句被切碎（`… the comparison` | `feature.`）。

    判据复用 reflow2 的**源切分缺陷**同款（前句末尾无句末标点 + 后句首字母小写）：
    英文句首必大写，故“后句小写”是强证据；两条件同时成立才合并，不会误合
    “合法无标点结尾 + 后句大写”的真句界。

    返回 (合并后长句, 合并明细)。
    """
    out, log = [], []
    for s in sentences:
        if out and not _ends_term(out[-1]["text"]) and _starts_lower(s["text"]):
            prev = out.pop()
            log.append({"end": prev["end"], "left": prev["text"][-60:], "right": s["text"][:60]})
            out.append({
                "start": prev["start"], "end": s["end"],
                "nclauses": prev["nclauses"] + s["nclauses"],
                "nwords": prev["nwords"] + s["nwords"],
                "text": prev["text"] + " " + s["text"],
                "clauses": prev["clauses"] + s["clauses"],
                "stitched": True,
            })
        else:
            out.append(dict(s))
    return out, log


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(description="vocalign 骨架构建：词级时轴 + 标点 → 三层骨架")
    ap.add_argument("--words", required=True, help="词级时轴 JSON（vocalign_collect.py 产物）")
    ap.add_argument("--srt", default=None, help="可选诊断：完整文本对照（设计上不依赖）")
    ap.add_argument("-o", "--out", required=True, help="输出目录（vocalign/）")
    ap.add_argument("--baseline-ms", type=float, default=BASELINE_MS, help="伪间隙 baseline（默认 40）")
    ap.add_argument("--sent-ms", type=float, default=SENT_MS, help="净停顿 ≥ 此值 → 强句界（默认 500）")
    ap.add_argument("--clause-ms", type=float, default=CLAUSE_MS, help="净停顿 ≥ 此值 → 子句界（默认 250）")
    ap.add_argument("--clause-upgrade-ms", type=float, default=CLAUSE_UPGRADE_MS,
                    help="逗号后净停顿 ≥ 此值 → 升级为句界（0 = 不升级）")
    ap.add_argument("--no-stitch", action="store_true",
                    help="关闭碎片归位（默认开：前句末尾无句末标点 + 后句首字母小写 → 合并）")
    ap.add_argument("--expand", action="store_true", help="展开打印低置信边界清单")
    args = ap.parse_args()

    meta, words = load_words(args.words)
    if args.srt:
        toks, stats = align_times(read_srt_tokens(args.srt), words)
        stats.setdefault("text_source", "srt")
    else:
        toks = words_to_tokens(words)
        n_hole = sum(1 for t in toks if t["start"] is None)
        stats = fill_missing_times(toks)
        stats["aligned"] = len(toks) - n_hole
        stats["text_source"] = "words"

    n_word = len(toks)
    hole_ratio = stats.get("hole_total", 0) / max(1, n_word)
    bounds = compute_bounds(toks, args.baseline_ms, args.sent_ms, args.clause_ms,
                            args.clause_upgrade_ms)
    sentences = build(toks, bounds)
    n_raw_sentences = len(sentences)
    stitch_log = []
    if not args.no_stitch:
        sentences, stitch_log = stitch_sentences(sentences)

    clause_words = [c["nwords"] for s in sentences for c in s["clauses"]]
    why_count = {}
    for b in bounds:
        if b["level"] != "none":
            k = "%s/%s" % (b["level"], b["why"])
            why_count[k] = why_count.get(k, 0) + 1
    low_conf = [b for b in bounds if b["level"] in ("sent", "clause") and b["conf"] == "low"]

    report = {
        "source": {"words": os.path.basename(args.words),
                   "srt": os.path.basename(args.srt) if args.srt else ""},
        "params": {"baseline_ms": args.baseline_ms, "sent_ms": args.sent_ms,
                   "clause_ms": args.clause_ms, "clause_upgrade_ms": args.clause_upgrade_ms},
        "align": stats,
        "n_words": n_word,
        "n_sentences": len(sentences),
        "n_sentences_raw": n_raw_sentences,
        "n_stitched": len(stitch_log),
        "stitches": stitch_log,
        "n_clauses": len(clause_words),
        "boundary_sources": why_count,
        "clause_words": dist(clause_words),
        "sentence_clauses": dist([s["nclauses"] for s in sentences]),
        "sentence_words": dist([s["nwords"] for s in sentences]),
        "low_conf_bounds": low_conf,
        "sentences": sentences,
    }

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "skeleton.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)

    with open(os.path.join(args.out, "boundaries.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# 词间边界判据明细（净停顿 = 原始间隙 − baseline %.0fms）\n" % args.baseline_ms)
        fh.write("# i\tlevel\twhy\tconf\tgap_ms\tnet_ms\tafter | before\n")
        for b in bounds:
            fh.write("%d\t%s\t%s\t%s\t%.1f\t%.1f\t%s | %s\n" % (
                b["i"], b["level"], b["why"], b["conf"] or "-", b["gap_ms"], b["net_ms"],
                b["after"], b["before"]))

    # ---- 初版 **SRT 载体**（长句 + 语音实测时间；cue 号 ≡ S 号）----
    # 为何由骨架产：**分块只需“长句边界 + 时间”，与文本内容无关** ——
    # 而 E0 的清单要按块（需 chunks）、分块又需载体 → 循环。骨架先产**初版**载体打破循环：
    #   骨架 → 分块 → E0 定稿（按块）→ **重跑分块**（吃定稿载体，使块内文本 = 定稿文本）
    srt_lines = []
    for si, s in enumerate(sentences, 1):
        srt_lines.append(str(si))
        srt_lines.append("%s --> %s" % (hms(s["start"]), hms(s["end"])))
        srt_lines.append(s["text"])
        srt_lines.append("")
    with open(os.path.join(args.out, "long_lines.srt"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(srt_lines) + "\n")

    with open(os.path.join(args.out, "stitches.txt"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write("# 碎片归位明细（前句末尾无句末标点 + 后句首字母小写 → 合并）\n")
        fh.write("# 长句 %d → %d（合并 %d 处）\n\n" % (
            n_raw_sentences, len(sentences), len(stitch_log)))
        for i, r in enumerate(stitch_log, 1):
            fh.write("%d. %s\n   left：…%s\n   right：%s…\n" % (i, hms(r["end"]), r["left"], r["right"]))
        if not stitch_log:
            fh.write("（无）——源段边界均落在句界\n")

    with open(os.path.join(args.out, "skeleton.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# vocalign 骨架（长句 → 子句 → 词）\n")
        fh.write("# 参数：baseline=%.0fms 句界=%.0fms 子句界=%.0fms 升级=%.0fms\n" % (
            args.baseline_ms, args.sent_ms, args.clause_ms, args.clause_upgrade_ms))
        fh.write("# 规模：长句 %d / 子句 %d / 词 %d（碎片归位 %d 处）\n" % (
            len(sentences), len(clause_words), n_word, len(stitch_log)))
        fh.write("# 边界来源：%s\n\n" % json.dumps(why_count, ensure_ascii=False))
        for si, s in enumerate(sentences, 1):
            fh.write("S%d  %s → %s  (%d 子句 / %d 词)\n" % (
                si, hms(s["start"]), hms(s["end"]), s["nclauses"], s["nwords"]))
            for ci, c in enumerate(s["clauses"], 1):
                fh.write("   C%d  %-12s | %s\n" % (ci, hms(c["start"]), c["text"]))
            fh.write("\n")

    print("vocalign 骨架：长句 %d / 子句 %d / 词 %d（文本源 %s）" % (
        len(sentences), len(clause_words), n_word, stats["text_source"]))
    print("对齐：成功 %d / 插值补齐 %d / 无锚 %d" % (
        stats.get("aligned", 0), stats.get("interp", 0), stats.get("synth", 0)))
    print("边界来源 %s" % json.dumps(why_count, ensure_ascii=False))
    print("子句词数 %s" % json.dumps(report["clause_words"], ensure_ascii=False))
    if low_conf:
        print("低置信边界 %d 处（无标点 + 短停顿，待补标点环节复核）" % len(low_conf))
        if args.expand:
            for b in low_conf:
                print("   %8.1fms  %-4s  %s | %s" % (b["gap_ms"], b["level"], b["after"], b["before"]))
        else:
            print("   （加 --expand 展开）")
    print("产物：%s" % os.path.abspath(args.out))

    if hole_ratio > HOLE_WARN_RATIO:
        print("❌ 未对齐词占比 %.1f%% > %.0f%% —— 复核采集结果（对齐模型/语言设置）" % (
            100.0 * hole_ratio, 100.0 * HOLE_WARN_RATIO))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
