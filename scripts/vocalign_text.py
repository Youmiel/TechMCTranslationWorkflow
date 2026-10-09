# -*- coding: utf-8 -*-
"""vocalign E0 定稿：音频侧文本的收敛与定稿（两趟式，纯标准库）

定位
    vocalign **独立前置**的核心环节（`2026-10-08_vocalign独立前置设计.md` §三 环节③）。
    把“whisper 长句”收敛为**E0 定稿文本**（`S` 号 + 定稿英文），供术语扫描 / 翻译消费。
    一经定稿，**全程只认 S 号**（禁止混入 01 的 cue 号 —— 两套编号会静默错配）。

为什么需要它
    1. **两套 ASR 各执一词**：whisper 转写与 `01`（YouTube 自动字幕 + 一轮修正）词级差异
       实测 4.96%（PRR 2），其中 43.3% 是**形态差异**（数字写法 / 缩写 / 连写 / 范围写法）可由
       规则层消除；剩余是**真仲裁点**（`redstone` ↔ `resident` 等）。
    2. **标点不全**：whisper 虽有标点，但**有停顿处未必有标点**（实测 5 视频句末标点率 0.00–0.22）
       → 探测“有停顿但无标点”的可疑边界交 LLM 补一次。
    3. **非口播注释**：上传者按讲解稿补注（实测 9 处 / 5 视频，含技术纠偏如
       `(maps are still 8 clicks to rotate not 4)`）→ 用**语速判据**检出并**并入对应长句**（方案 A）。

两层文本（**必须分离**）
    · **比对层**（canonical）：激进归一（缩写展开、数词转数字、连写/单复数容忍）—— 只为**算差异**。
    · **书写层**（surface）：E0 实际文本 = **whisper 原样** + LLM 仲裁修正 + 注释并入。
    ⚠️ 不可用比对层形态写 E0（会把 `game ticks` 写成 `gametick`、把 `four` 写成 `4` → 失真）。

产物
    `<e0>/long_lines.md`        E0 定稿（`S<n>  <英文>`；人读 / 翻译输入）
    `<e0>/long_lines.srt`       **E0 的 SRT 载体**（cue 号 ≡ S 号）—— 让依赖 cue 号的
                                现有脚本（`asr_trigger` / `glossary_lookup` / `glossary_load_plan` /
                                `text_chunk`）**零改动**直接消费；时间 = 长句**语音实测**值
    `<e0>/en_timeline/chunk_<k>.txt`  **S 长句 + 时间**（按块分装）—— 供 `task-match`
                                对照 Z 句做语义对齐（自产 `align/`，**不再依赖 reflow2**）
                                格式：`S<n>\t<start> --> <end>\t<S 号范围>\t<文本>`（与 reflow2 同构）
    `<e0>/_request/chunk_<k>.md` LLM 待办清单（三类：仲裁 / 补标点 / 注释确认）
    `<e0>/reply/chunk_<k>.txt`   LLM 作答（`<key> = <值>` 每行一条）
    `<e0>/_check_report.md`      作答校验报告
    `<e0>/report.md`             形态分级 / 规则层统计 / 差异分类

   ⚠️ **绕开的是“YouTube 自动字幕作文本源”，不是 SRT 这个容器**：
   `long_lines.srt` 的内容与时间**全部来自音频实测**（whisper + wav2vec2），
   只借用 SRT 的字段结构换取“现有脚本零改动 + cue 号 ≡ S 号（映射恒等）”。

用法（命令根 = Project_Main/）
    python scripts/vocalign_text.py emit  --skeleton <work>/vocalign --srt <work>/01_subtitle_asr_fixed.srt \\
        --e0 <work>/vocalign/e0 [--chunks <work>/vocalign/chunks]
    python scripts/vocalign_text.py check --skeleton <work>/vocalign --e0 <work>/vocalign/e0
    python scripts/vocalign_text.py apply --skeleton <work>/vocalign --e0 <work>/vocalign/e0

    `--srt` 可选（缺省 = 全新视频，跳过仲裁与注释检测，流程照常）。

退出码：0 = 成功；1 = 有失败项（作答校验失败 / 仲裁未决）。
"""
import argparse
import bisect
import difflib
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

from shared.srt_common import collect_chunk_files

# ---- 形态分级判据（`report` 用；⚠️ 括号不可单独定级——产物稿/中文稿也带括号）----
GRADE_S_END = 0.50          # 句末标点率 ≥ 此值 → S（讲解稿级）
GRADE_S_END_MID = 0.15      # S 的辅助路径：≥ 此值 **且** 括号 cue 率 ≥ GRADE_S_BR
GRADE_S_BR = 0.02
GRADE_A_END = 0.25
GRADE_B_END = 0.05

# ---- 可疑停顿（补标点候选）：净停顿 ≥ 此值且左侧词尾无标点 → 交 LLM 判定 ----
SUSPECT_PAUSE_MS = 250.0

# ---- 非口播注释判据（语速）----
SPEECH_MAX_WPS = 5.0        # 口播语速上限（词/秒；实测全片 p50 = 3.4）
SPEECH_RATIO = 0.8          # whisper 该时段词数 < 字幕词数 × 此值 → 判为含非口播内容

# ---- 定稿超长句告警（该断未断的信号；阈值同 reflow2 的补标点质量校验）----
LONG_COMMA_MAX = 10         # 单句逗号数上限
LONG_CHAR_MAX = 600         # 单句字符数上限

TS = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})")
SENT_END = ".?!"
BRACKET = re.compile(r"\(([^)]*)\)")
STRIP_CHARS = ".,;:!?\u2014\u2013\u2026\"')]}\u201d\u2019"
S_LINE = re.compile(r"^\s*S(\d+)\s*[ \t]\s*(.*\S)\s*$")
KV_LINE = re.compile(r"^\s*([ABC]\d+)\s*=\s*(.*\S)\s*$")

# ---- R2 缩写展开（比对层）----
CONTRACTIONS = [("n't", " not"), ("'re", " are"), ("'ve", " have"), ("'ll", " will"),
                ("'d", " would"), ("'s", " is"), ("'m", " am")]
# ---- R3 数词 → 数字（比对层）----
NUM_WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
             "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
             "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
             "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
             "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
             "hundred": 100, "thousand": 1000}
# ---- R5 拼写变体（英/美 + 常见异拼；比对层）----
VARIANT = {"behaviour": "behavior", "colour": "color", "chiselled": "chisel",
           "chiseled": "chisel", "labelled": "label", "labelled": "label",
           "grey": "gray", "modelling": "modeling", "cancelled": "canceled"}
RANGE_RE = re.compile(r"^(\d+)-(\d+)$")          # 0-5 → 0 to 5（比对层）
# 归一化产生的功能词（缩写展开 R2 / 范围写法 R5 的产物）——差集只含它们 → 形态差异（见 classify）
FILL_WORDS = {"is", "are", "have", "will", "would", "not", "am", "to"}


def split_punct(tok):
    """拆词尾标点（与 vocalign_skeleton.py 同口径）"""
    t = (tok or "").strip()
    i = len(t)
    while i > 0 and t[i - 1] in STRIP_CHARS:
        i -= 1
    return t[:i], t[i:]


def to_sec(g):
    return int(g[0]) * 3600 + int(g[1]) * 60 + int(g[2]) + int(g[3]) / 1000.0


# ---------------------------------------------------------------- 载入

def load_skeleton(path):
    """skeleton.json → (report, sentences[])"""
    with open(path, encoding="utf-8-sig") as fh:
        rep = json.load(fh)
    sents = rep.get("sentences") or []
    if not sents:
        sys.exit("❌ skeleton.json 无 sentences：%s" % path)
    return rep, sents


def load_boundaries(path):
    """boundaries.txt → {全局词号: (净停顿 ms, level)}（词号 i = toks[i] 与 toks[i+1] 之间）"""
    out = {}
    if not os.path.isfile(path):
        return out
    with open(path, encoding="utf-8-sig") as fh:
        for ln in fh:
            if ln.startswith("#") or not ln.strip():
                continue
            p = ln.rstrip("\n").split("\t")
            if len(p) < 6:
                continue
            try:
                i, net = int(p[0]), float(p[5])
            except ValueError:
                continue
            if p[2] == "interp-skip":
                continue
            out[i] = (net, p[1])
    return out


def parse_srt(path):
    """SRT → [(cue 号(int), start, end, 文本)]

    ⚠️ cue 号必须转 **int**：`parse_owned_cue_range`（分块目录）返回整数，
    类型不一致会让 `r[0] in cues` 静默失败（实测踩过：en_timeline 产出 0 句 0 块）。
    """
    raw = open(path, encoding="utf-8-sig").read()
    out = []
    for block in re.split(r"\n\s*\n", raw.strip()):
        lines = [x.strip() for x in block.split("\n") if x.strip()]
        ti = next((i for i, ln in enumerate(lines) if TS.search(ln)), None)
        if ti is None:
            continue
        g = TS.search(lines[ti]).groups()
        try:
            idx = int(lines[0])
        except ValueError:
            idx = len(out) + 1
        out.append((idx, to_sec(g[:4]), to_sec(g[4:]), " ".join(lines[ti + 1:])))
    return out


def sentence_words_removed():
    """（历史占位）"""


# ---------------------------------------------------------------- 比对层归一化

def canon_tokens(tokens):
    """书写层 token 序列 → (比对层 token 序列, 源词号映射)

    ⚠️ **必须返回源词号映射**：R2（缩写展开）/R5（范围写法）会**把 1 个原词变成多个比对词**
    → 比对层索引**不等于**原词号。直接用会在“展示上下文”与“apply 替换”时错位
    （实测踩过：`The`↔`the` 被报成差异 —— 实为索引错位取到了相邻词）。
    """
    out, src = [], []
    for i, tok in enumerate(tokens):
        t = tok.strip(STRIP_CHARS).lower()
        if not t:
            out.append("")                      # 保留位置（索引对齐）
            src.append(i)
            continue
        m = RANGE_RE.match(t)
        if m:                                    # R5：0-5 → 0 to 5
            for x in (m.group(1), "to", m.group(2)):
                out.append(x)
                src.append(i)
            continue
        pieces = [t]
        if t.endswith("n't") and len(t) > 3:
            pieces = [t[:-3], "not"]
        else:
            for suf, full in CONTRACTIONS:
                if t.endswith(suf) and len(t) > len(suf):
                    pieces = [t[:-len(suf)]] + full.split()
                    break
        for p in pieces:
            out.append(str(NUM_WORDS[p]) if p in NUM_WORDS else VARIANT.get(p, p))
            src.append(i)
    return out, src


def classify(tag, a, b):
    """差异块分类：compound（形态差异）/ plural（单复数）/ real（真仲裁点）

    ⚠️ **缩写展开的副作用必须归形态差异**：R2 把 `you've` 展开为 `you have`，而另一侧可能就是
    `you`（未缩写）→ 差集 `{have}` 是**归一化产生的**，不是真差异（实测踩过，会白増仲裁点）。
    """
    if not a or not b:
        return "real"
    if "".join(a) == "".join(b):
        return "compound"
    if len(a) == len(b) == 1 and a[0].rstrip("s") == b[0].rstrip("s"):
        return "plural"
    from collections import Counter
    diff = (Counter(a) - Counter(b)) + (Counter(b) - Counter(a))
    if set(diff) <= FILL_WORDS:                  # 差集全是归一化功能词 → 形态差异
        return "compound"
    return "real"


def diff_blocks(w_main, w_src, w_surf, s_main, s_src, s_surf):
    """比对（canon 层）→ 差异块（**索引已映射回原词号**）

    `i1/i2` = skeleton 侧原词号（半开区间）；`j1/j2` = 01 侧原词号。
    """
    sm = difflib.SequenceMatcher(None, w_main, s_main, autojunk=False)
    out = []
    for tag, a1, a2, b1, b2 in sm.get_opcodes():
        if tag == "equal":
            continue
        i1 = w_src[a1]
        i2 = (w_src[a2 - 1] + 1) if a2 > a1 else i1
        j1 = s_src[b1]
        j2 = (s_src[b2 - 1] + 1) if b2 > b1 else j1
        out.append({"tag": tag, "cat": classify(tag, w_main[a1:a2], s_main[b1:b2]),
                    "i1": i1, "i2": i2, "j1": j1, "j2": j2,
                    "main": " ".join(w_surf[i1:i2]), "surf": " ".join(s_surf[j1:j2])})
    return out


# ---------------------------------------------------------------- 三类待办

def sent_index(sents):
    """长句 → (全局起词号 starts, 起止时间)；供词号/时间双向定位"""
    starts, pos = [], 0
    for s in sents:
        starts.append(pos)
        pos += len(s.get("text", "").split())
    return starts


def sent_of_word(starts, widx):
    """全局词号 → 长句号（1-based；widx 落在 [starts[i], starts[i+1]) → i+1）"""
    return max(1, bisect.bisect_right(starts, widx))


def sent_of_time(sents, t):
    """时间 → 长句号（按长句时间范围；落在句间空隙 → 归前一句）"""
    prev = 1
    for i, s in enumerate(sents, 1):
        if s.get("start", 0.0) <= t <= s.get("end", 0.0):
            return i
        if t < s.get("start", 0.0):
            return prev
        prev = i
    return prev


def suspect_boundaries(sents, bounds, starts):
    """可疑停顿：净停顿 ≥ 阈值、且左侧词**无任何标点** → 补标点候选"""
    out = []
    for si, ws in enumerate(sents, 1):
        toks = ws.get("text", "").split()
        base = starts[si - 1]
        for j in range(len(toks) - 1):
            rec = bounds.get(base + j)
            if not rec:
                continue
            net, _lvl = rec
            if net < SUSPECT_PAUSE_MS:
                continue
            if split_punct(toks[j])[1]:            # 已有词尾标点 → 不是“缺标点”
                continue
            out.append({"key": None, "kind": "punct", "s": si, "g": base + j,
                        "after": toks[j], "before": toks[j + 1], "net": net})
    return out


def detect_notes(cues, words, sents):
    """非口播注释：01 cue 含括号 且语速超限 且 whisper 该时段词数明显更少（判据见文件头）

    ⚠️ **所属长句用“head 词序列匹配”定位，不用时间** —— whisper 长句边界与 01 cue 边界
    不同（实测踩过：注释被挂到**前一句**句末，因为 cue 起点恰好等于前一长句终点）。
    """
    out = []
    for idx, t0, t1, text in cues:
        m = BRACKET.search(text)
        if not m:
            continue
        n_sub = len([x for x in text.split() if x.strip(STRIP_CHARS)])
        d = max(0.01, t1 - t0)
        inside = [w for w in words if w[0] >= t0 - 0.3 and w[1] <= t1 + 0.3]
        if n_sub / d <= SPEECH_MAX_WPS or len(inside) >= n_sub * SPEECH_RATIO:
            continue
        head = text[:m.start()].strip()          # 括号前的部分（定位插入点用）
        si = None
        for i, s in enumerate(sents, 1):
            if head and find_subseq(s.get("text", "").split(), head.split()) >= 0:
                si = i
                break
        if si is None:
            si = sent_of_time(sents, t0)
        out.append({"key": None, "kind": "note", "s": si,
                    "note": m.group(1).strip(), "head": head,
                    "n_sub": n_sub, "n_wsp": len(inside), "wps": round(n_sub / d, 1)})
    return out


def build_items(sents, bounds, cues, words):
    """三类待办 + 锚点 → (items{key:dict}, stats)"""
    starts = sent_index(sents)
    w_surf = [t for s in sents for t in s.get("text", "").split()]
    w_main, w_src = canon_tokens(w_surf)
    s_surf = [t for _i, _a, _b, t in cues for t in t.split()]
    s_main, s_src = canon_tokens(s_surf)
    blocks = diff_blocks(w_main, w_src, w_surf, s_main, s_src, s_surf) if cues else []
    # 含括号的差异块 → **归注释类处理**（不算仲裁点，否则同一处会在两节重复列出）
    real = [b for b in blocks if b["cat"] == "real" and not BRACKET.search(b["surf"])]
    n_note_like = sum(1 for b in blocks if b["cat"] == "real" and BRACKET.search(b["surf"]))

    items = {}
    for n, b in enumerate(real, 1):
        k = "A%d" % n
        items[k] = {"key": k, "kind": "arb", "s": sent_of_word(starts, b["i1"]),
                    "i1": b["i1"], "i2": b["i2"], "main": b["main"], "surf": b["surf"],
                    "ctx_main": ctx_words(w_surf, b["i1"]),
                    "ctx_01": ctx_words(s_surf, b["j1"])}
    for n, x in enumerate(suspect_boundaries(sents, bounds, starts), 1):
        x["key"] = "B%d" % n
        items[x["key"]] = x
    for n, nt in enumerate(detect_notes(cues, words, sents) if cues else [], 1):
        nt["key"] = "C%d" % n
        items[nt["key"]] = nt

    stats = {"n_blocks": len(blocks), "n_real": len(real), "n_note_like": n_note_like,
             "n_comp": len(blocks) - len(real) - n_note_like,
             "n_sus": sum(1 for v in items.values() if v["kind"] == "punct"),
             "n_note": sum(1 for v in items.values() if v["kind"] == "note"),
             "grade": grade([t for _i, _a, _b, t in cues]) if cues else ("-", 0.0, 0)}
    return items, stats


def ctx_words(toks, pos, k=4):
    """某位置之前 k 词（清单展示用；pos 为 0 → 句首）"""
    return ("\u2026" + " ".join(toks[max(0, pos - k):pos])) if pos > 0 else "（句首）"


def render_request(items, sents, k, sis):
    """清单文本（LLM 读）"""
    body = ["# e0/chunk_%03d" % k, "",
            "> 三类待办，逐项作答（每项一行 `<key> = <值>`）。**只改被指出的位置**，不动其它词。", ""]
    mine = [v for v in items.values() if v["s"] in sis]
    for kind, title, hint in (
            ("arb", "一、文本仲裁（两套 ASR 不一致处；选一个或另写）",
             "`A# = whisper` / `A# = 01` / `A# = <你的文本>`"),
            ("punct", "二、可疑停顿补标点（有停顿但词尾无标点；补上应有标点或判为无）",
             "`B# = ,` / `B# = .` / `B# = ?` / `B# = 无`"),
            ("note", "三、非口播注释确认（字幕含无语音对应内容，确认保留并入长句）",
             "`C# = 保留` / `C# = 删`")):
        rows = sorted([v for v in mine if v["kind"] == kind], key=lambda v: (v["s"], v["key"]))
        if not rows:
            continue
        body += ["## " + title, ""]
        for v in rows:
            if kind == "arb":
                body += ["%s  S%d" % (v["key"], v["s"]),
                         "  01      : %s **[%s]**" % (v.get("ctx_01", ""), v["surf"]),
                         "  whisper : %s **[%s]**" % (v.get("ctx_main", ""), v["main"])]
            elif kind == "punct":
                toks = sents[v["s"] - 1].get("text", "").split()
                base = sum(len(s.get("text", "").split()) for s in sents[:v["s"] - 1])
                j = v["g"] - base
                left = " ".join(toks[max(0, j - 8):j + 1])
                right = " ".join(toks[j + 1:j + 9])
                body += ["%s  S%d  （该句第 %d/%d 词后）" % (v["key"], v["s"], j + 1, len(toks)),
                         "  %s \u27e8此处无标点，%.0fms 停顿\u27e9 %s" % (left, v["net"], right),
                         "  （**不确定就判 `无`**；此处只是有停顿，不等于该断）"]
            else:
                body += ["%s  S%d  注释：`%s`（%.1f 词/秒，whisper 该时段仅 %d 词）"
                         % (v["key"], v["s"], v["note"], v["wps"], v["n_wsp"]),
                         "  所在句：%s" % sents[v["s"] - 1].get("text", "")[:110]]
            body += ["  \u2192 作答：%s" % hint, ""]
    return body


def do_emit(args, sents, bounds, cues, words, e0_dir):
    items, stats = build_items(sents, bounds, cues, words)
    if args.chunks and args.srt:
        rngs = chunk_ranges(args.chunks, args.srt)
    else:
        rngs = [(1, float("-inf"), float("inf"))]
    groups = {}
    for si, s in enumerate(sents, 1):
        t, prev, k = s.get("start", 0.0), 1, None
        for kk, t0, t1 in rngs:
            if t0 <= t < t1:
                k = kk
                break
            if t < t0:
                k = prev
                break
            prev = kk
        groups.setdefault(k if k is not None else prev, []).append(si)

    os.makedirs(os.path.join(e0_dir, "_request"), exist_ok=True)
    os.makedirs(os.path.join(e0_dir, "reply"), exist_ok=True)
    n_arb = 0
    for k in sorted(groups):
        if args.chunk and k != args.chunk:
            continue
        body = render_request(items, sents, k, set(groups[k]))
        if len(body) > 4:
            write(os.path.join(e0_dir, "_request", "chunk_%03d.md" % k), body)
            n_arb += 1
    # 机器可读锚点（apply 精确定位用）——一次全量写，不随块拆分
    write(os.path.join(e0_dir, "_items.json"),
          [json.dumps(items, ensure_ascii=False, indent=1)])

    write(os.path.join(e0_dir, "long_lines.md"),
          render_long_lines(sents, [v["note"] for v in items.values() if v["kind"] == "note"]))
    g, g_end, g_br = stats["grade"]
    rep = ["# E0 定稿报告（emit）", "",
           "- 长句 %d / 词 %d" % (len(sents), stats_sum_words(sents)),
           "- 01 形态分级：**%s**（句末标点率 %.3f / 括号 cue %d）" % (g, g_end, g_br),
           "- 比对：差异块 %d（**真仲裁点 %d** / 形态差异 %d）" % (
               stats["n_blocks"], stats["n_real"], stats["n_comp"]),
           "- 可疑停顿（补标点候选）：%d 处" % stats["n_sus"],
           "- 非口播注释：%d 处" % stats["n_note"],
           "- 清单块数：%d" % n_arb, ""]
    if not cues:
        rep += ["> ⚠️ 未提供 `--srt` → 跳过仲裁与注释检测（**全新视频的常态**；流程照常）", ""]
    write(os.path.join(e0_dir, "report.md"), rep)

    print("E0 emit：长句 %d / 仲裁点 %d / 可疑停顿 %d / 注释 %d（01 分级 %s）" % (
        len(sents), stats["n_real"], stats["n_sus"], stats["n_note"], g))
    print("清单目录：%s" % os.path.abspath(os.path.join(e0_dir, "_request")))
    print("初版 E0：%s" % os.path.abspath(os.path.join(e0_dir, "long_lines.md")))
    return 0


def stats_sum_words(sents):
    return sum(len(s.get("text", "").split()) for s in sents)


def grade(texts):
    """01 形态分级（判据见文件头）"""
    if not texts:
        return "?", 0.0, 0
    n = len(texts)
    n_end = sum(1 for t in texts if t.rstrip().endswith(tuple(SENT_END)))
    n_br = sum(1 for t in texts if BRACKET.search(t))
    r = n_end / n
    if r >= GRADE_S_END or (r >= GRADE_S_END_MID and n_br / n >= GRADE_S_BR):
        return "S", r, n_br
    if r >= GRADE_A_END:
        return "A", r, n_br
    if r >= GRADE_B_END:
        return "B", r, n_br
    return "C", r, n_br


# ---------------------------------------------------------------- 渲染

def fmt_srt(sec):
    """秒 → `HH:MM:SS,mmm`"""
    ms = max(0, int(round(sec * 1000)))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)


def render_long_lines_srt(sents):
    """E0 的 SRT 载体（cue 号 ≡ S 号；时间 = 长句语音实测值）

    ⚠️ 文本 **不折行**：下游解析（`text_chunk`）遇多行 body 会插 ` | ` 连接符、
    `asr_trigger` 会拼空格 → 折行会引入噪声。单行最安全。
    ⚠️ 极短句（<1s）照写：SRT 允许；vocalign 不走 `srt_mech_fix` 的异常时长门禁。
    """
    out = []
    for i, s in enumerate(sents, 1):
        out.append(str(i))
        out.append("%s --> %s" % (fmt_srt(s.get("start", 0.0)), fmt_srt(s.get("end", 0.0))))
        out.append(s.get("text", ""))
        out.append("")
    return out


def chunk_cue_ranges(chunks_dir):
    """分块目录 → [(块号, 首 cue 号, 末 cue 号)]

    ⚠️ **必须用 cue 号范围**（不是时间范围）：`en_timeline` 按 S 号分装，
    而 **cue 号 ≡ S 号** —— 实测踩过：误用 `chunk_ranges`（返回时间）会让
    `range(int(t0), int(t1))` 变成空/巨大区间 → chunk_002 产出为空。
    """
    from shared.srt_common import parse_owned_cue_range
    out = []
    for k, p in sorted(collect_chunk_files(chunks_dir).items()):
        r = parse_owned_cue_range(p)
        if r:
            out.append((k, r[0], r[1]))
    return out


def render_en_timeline(sents, e0_dir, chunks_dir, srt_path):
    """产出 `en_timeline/chunk_<k>.txt`（S 长句 + 时间，按块分装）

    格式与 reflow2 的 `en_timeline/` 同构（`S<n>\t<start> --> <end>\t<范围>\t<文本>`），
    使 `task-match` 模板与派发链可**直接复用**（只把 E 号换成 S 号）。

    ⚠️ **S 号是全局的**（不像 reflow2 的 E 号为块内局部）—— 但为让 task-match 逐块对照，
    仍**按块分装**文件；块划分由 `--chunks` 的 OWNED cue 范围给出（**cue 号 ≡ S 号**，直接对应）。
    未给 `--chunks` 时单块全量。
    """
    if chunks_dir and os.path.isdir(chunks_dir):
        rngs = chunk_cue_ranges(chunks_dir)
    else:
        rngs = [(1, 1, len(sents))]
    out_root = os.path.join(e0_dir, "en_timeline")
    lines_by_k = {}
    for k, a, b in rngs:
        rows = []
        for si in range(max(1, int(a)), min(len(sents), int(b)) + 1):
            s = sents[si - 1]
            rows.append("S%d\t%s --> %s\tS%d\t%s" % (
                si, fmt_srt(s.get("start", 0.0)), fmt_srt(s.get("end", 0.0)), si,
                s.get("text", "")))
        lines_by_k[k] = rows
    for k, rows in lines_by_k.items():
        write(os.path.join(out_root, "chunk_%03d.txt" % k), rows)
    return sum(len(v) for v in lines_by_k.values()), len(lines_by_k)


def render_long_lines(sents, notes=None):
    """E0 定稿文本（`S<n>  <英文>`；头部注明非口播注释数，提示翻译环节）"""
    out = ["# E0 定稿长句（%d 句）" % len(sents)]
    if notes:
        out.append("# ⚠️ 含非口播注释 %d 处（括号内容无语音对应，属讲解稿补注）：%s" % (
            len(notes), "；".join("(%s)" % n for n in notes)))
    out.append("")
    for i, s in enumerate(sents, 1):
        out.append("S%d  %s" % (i, s.get("text", "")))
    return out


def write(path, lines):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


def chunk_ranges(chunks_dir, srt_path):
    """分块目录 + 01 srt → [(块号, 起, 止)]"""
    from shared.srt_common import parse_owned_cue_range
    cues = {c[0]: (c[1], c[2]) for c in parse_srt(srt_path)}
    out = []
    for k, p in sorted(collect_chunk_files(chunks_dir).items()):
        r = parse_owned_cue_range(p)
        if r and r[0] in cues and r[1] in cues:
            out.append((k, cues[r[0]][0], cues[r[1]][1]))
    return out


# ---------------------------------------------------------------- check / apply

def load_reply(path):
    """读作答 → {key: 值}"""
    out = {}
    if not os.path.isfile(path):
        return out
    with open(path, encoding="utf-8-sig") as fh:
        for ln in fh:
            if ln.lstrip().startswith("#") or not ln.strip():
                continue
            m = KV_LINE.match(ln)
            if m:
                out[m.group(1)] = m.group(2).strip()
    return out


def expected_keys(e0_dir, k):
    """清单里的 key 集合 + 每 key 的期望值域"""
    path = os.path.join(e0_dir, "_request", "chunk_%03d.md" % k)
    if not os.path.isfile(path):
        return {}
    txt = open(path, encoding="utf-8-sig").read()
    sec, out = None, {}
    for ln in txt.split("\n"):
        if ln.startswith("## 一"):
            sec = "A"
        elif ln.startswith("## 二"):
            sec = "B"
        elif ln.startswith("## 三"):
            sec = "C"
        m = re.match(r"^([ABC]\d+)\s{2}S(\d+)", ln)
        if m and sec:
            out[m.group(1)] = (sec, int(m.group(2)))
    return out


def do_check(args, sents, e0_dir):
    ks = sorted({k for k in (int(m.group(1)) for fn in os.listdir(os.path.join(e0_dir, "_request"))
                             for m in [re.fullmatch(r"chunk_(\d{3})\.md", fn)] if m)})
    if args.chunk:
        ks = [k for k in ks if k == args.chunk]
    bad, n_rows = [], 0
    for k in ks:
        want = expected_keys(e0_dir, k)
        got = load_reply(os.path.join(e0_dir, "reply", "chunk_%03d.txt" % k))
        n_rows += len(got)
        for key, (sec, sno) in want.items():
            v = got.get(key)
            if v is None:
                bad.append("chunk_%03d %s（S%d）：缺失作答" % (k, key, sno))
                continue
            if sec == "A" and v not in ("whisper", "01") and not v.strip():
                bad.append("chunk_%03d %s：空仲裁结果" % (k, key))
            if sec == "B" and v not in (",", ".", "?", "!", ";", ":", "无"):
                bad.append("chunk_%03d %s：应填标点或 `无`，实为 `%s`" % (k, key, v))
            if sec == "C" and v not in ("保留", "删"):
                bad.append("chunk_%03d %s：应填 `保留` / `删`，实为 `%s`" % (k, key, v))
        for key in got:
            if key not in want:
                bad.append("chunk_%03d %s：key 不在清单内" % (k, key))
    body = ["# vocalign E0 作答校验报告", "",
            "- 块 %d；作答行 %d；失败 %d" % (len(ks), n_rows, len(bad)), ""]
    if bad:
        body += ["## 失败明细", ""] + ["- %s" % b for b in bad]
    write(os.path.join(e0_dir, "_check_report.md"), body)
    print("E0 check：块 %d / 行 %d / 失败 %d" % (len(ks), n_rows, len(bad)))
    return 1 if bad else 0


def find_subseq(toks, need):
    """在词序列中定位子序列（**归一化词形**比较；-1 = 未找到）

    注释的 head 来自 01（可能带标点 / 缩写形态不同）→ 必须按归一形匹配。
    """
    if not need:
        return -1
    n = [canon_one(t) for t in need]
    seq = [canon_one(t) for t in toks]
    for i in range(0, len(seq) - len(n) + 1):
        if seq[i:i + len(n)] == n:
            return i
    return -1


def canon_one(tok):
    """单 token 的比对形（供 find_subseq 用）"""
    r, _s = canon_tokens([tok])
    return r[0] if r else ""


def do_apply(args, sents, e0_dir, cues, words):
    """应用作答 → E0 定稿（仲裁替换 / 补标点 / 注释并入）

    锚点全部来自 `emit` 写的 `_items.json`（**机器可读**）—— 清单 `chunk_<k>.md` 只给人看，
    apply 不解析它（避免文本模糊匹配）。同一长句的多处修改按**词号降序**应用（先大后小，
    不因前面的改动而错位）。
    """
    ipath = os.path.join(e0_dir, "_items.json")
    if not os.path.isfile(ipath):
        sys.exit("❌ 找不到 %s（请先跑 emit）" % ipath)
    with open(ipath, encoding="utf-8") as fh:
        items = json.load(fh)

    replies = {}
    for fn in sorted(os.listdir(os.path.join(e0_dir, "reply"))):
        m = re.fullmatch(r"chunk_(\d{3})\.txt", fn)
        if not m:
            continue
        k = int(m.group(1))
        if args.chunk and k != args.chunk:
            continue
        replies.update(load_reply(os.path.join(e0_dir, "reply", fn)))

    starts = sent_index(sents)
    mods, unknown = {}, []
    n_arb = n_punct = n_note = 0
    for key, v in sorted(replies.items()):
        it = items.get(key)
        if not it:
            unknown.append(key)
            continue
        si = it["s"]
        if it["kind"] == "arb":
            if v == "whisper":
                continue
            text = it["surf"] if v == "01" else v      # 自定文本直接用
            mods.setdefault(si, []).append((it["i1"], it["i2"], "replace", text.split()))
            n_arb += 1
        elif it["kind"] == "punct":
            if v == "无":
                continue
            mods.setdefault(si, []).append((it["g"], it["g"], "punct", v))
            n_punct += 1
        elif it["kind"] == "note":
            if v != "保留":
                n_note += 0
                continue
            mods.setdefault(si, []).append((None, None, "note", it))
            n_note += 1

    orig = {si: sents[si - 1].get("text", "") for si in mods}   # 改动前原文（审计用）
    for si, ms in mods.items():
        toks = sents[si - 1].get("text", "").split()
        base = starts[si - 1]
        # 词号类修改降序应用（先大索引，避免位移）
        wordops = sorted([(a - base, b - base, kd, p) for a, b, kd, p in ms if a is not None],
                         key=lambda x: -x[0])
        for a, b, kd, payload in wordops:
            if kd == "replace":
                toks[a:b] = payload
            else:
                toks[a] = toks[a] + payload
        for a, b, kd, payload in ms:
            if kd != "note":
                continue
            head = payload.get("head", "").split()
            pos = find_subseq(toks, head)
            ins = (pos + len(head)) if pos >= 0 else len(toks)
            toks.insert(ins, "(%s)" % payload["note"])
        sents[si - 1]["text"] = " ".join(toks)

    # ---- 改动审计：逐条列出定稿相对骨架原文的改动（供人工复核，对照 reflow2 的措辞校验）
    chg = ["# S号\t改动类型\t骨架原文\t定稿"]
    for si in sorted(orig):
        new = sents[si - 1].get("text", "")
        if new != orig[si]:
            kinds = "+".join(sorted({kd for _a, _b, kd, _p in mods[si]}))
            chg.append("%d\t%s\t%s\t%s" % (si, kinds, orig[si], new))
    write(os.path.join(e0_dir, "_changes.tsv"), chg)

    # ---- 超长句告警：定稿后仍超长的长句 = “该断未断”的信号（B 类判“无”过多的后果）
    longs = []
    for si, s in enumerate(sents, 1):
        t = s.get("text", "")
        n_comma = t.count(",")
        if n_comma > LONG_COMMA_MAX or len(t) > LONG_CHAR_MAX:
            longs.append("S%d：%d 逗号 / %d 字符" % (si, n_comma, len(t)))

    write(os.path.join(e0_dir, "long_lines.md"),
          render_long_lines(sents, [it["note"] for it in items.values()
                                    if it.get("kind") == "note" and it.get("s") in mods]))
    write(os.path.join(e0_dir, "long_lines.srt"), render_long_lines_srt(sents))
    n_et, n_ck = render_en_timeline(sents, e0_dir, args.chunks, args.srt)
    rep = ["# E0 定稿报告（apply）", "",
           "- 仲裁修正 %d / 补标点 %d / 注释并入 %d" % (n_arb, n_punct, n_note),
           "- 未改动的长句 %d" % (len(sents) - len(mods)),
           "- 改动审计：`_changes.tsv`（%d 处）" % (len(chg) - 1),
           "- en_timeline：%d 句 / %d 块（供 task-match 自产 align）" % (n_et, n_ck), ""]
    if longs:
        rep += ["## 超长句告警（%d 处；逗号 >%d 或字符 >%d，视为该断未断的信号）"
                % (len(longs), LONG_COMMA_MAX, LONG_CHAR_MAX), ""]
        rep += ["- %s" % x for x in longs[:40]]
        rep += [""]
    if unknown:
        rep += ["## 未归属的 key（`_items.json` 里找不到）", ""] + ["- %s" % x for x in unknown]
    write(os.path.join(e0_dir, "report.md"), rep)
    print("E0 apply：仲裁 %d / 补标点 %d / 注释并入 %d" % (n_arb, n_punct, n_note))
    if longs:
        print("⚠️ 超长句 %d 处（该断未断的信号；详见 report.md）" % len(longs))
    print("E0 定稿：%s" % os.path.abspath(os.path.join(e0_dir, "long_lines.md")))
    print("SRT 载体：%s" % os.path.abspath(os.path.join(e0_dir, "long_lines.srt")))
    print("en_timeline：%d 句 / %d 块（供 task-match）" % (n_et, n_ck))
    return 0


def main():
    ap = argparse.ArgumentParser(description="vocalign E0 定稿（仲裁 / 补标点 / 注释，两趟式）")
    ap.add_argument("action", choices=("emit", "check", "apply"))
    ap.add_argument("--skeleton", required=True, help="vocalign 工作目录（含 skeleton.json）或该文件")
    ap.add_argument("--e0", default=None, help="E0 输出目录（默认 <skeleton 目录>/e0）")
    ap.add_argument("--srt", default=None, help="01_subtitle_asr_fixed.srt（可选；缺省 = 跳过仲裁/注释）")
    ap.add_argument("--words", default=None, help="words.json（默认 = 同目录；注释检测用）")
    ap.add_argument("--chunks", default=None,
                    help="分块目录（清单与 en_timeline 按块导出；默认自动探测 <vocalign 目录>/chunks）")
    ap.add_argument("--chunk", type=int, default=None, help="仅处理该块号")
    ap.add_argument("--expand", action="store_true")
    args = ap.parse_args()

    sk = args.skeleton if os.path.isfile(args.skeleton) else os.path.join(args.skeleton, "skeleton.json")
    if not os.path.isfile(sk):
        sys.exit("❌ 找不到 skeleton.json：%s" % sk)
    base = os.path.dirname(os.path.abspath(sk))
    e0_dir = args.e0 or os.path.join(base, "e0")
    wd = args.words or os.path.join(base, "words.json")
    # ⚠️ **必须定位到分块目录**：不传则 `en_timeline` 只出单块，与后续 `chunks/`（多块）不一致
    # → `task-match` 会缺块。故未显式给 `--chunks` 时**自动探测** `<base>/chunks`。
    if not args.chunks and os.path.isdir(os.path.join(base, "chunks")):
        args.chunks = os.path.join(base, "chunks")
    if not args.chunks:
        print("⚠️ 未找到分块目录（%s/chunks）→ en_timeline 将只出单块；"
              "请先跑 text_chunk 分块，或用 --chunks 指定" % base)

    _rep, sents = load_skeleton(sk)
    bounds = load_boundaries(os.path.join(base, "boundaries.txt"))
    cues = parse_srt(args.srt) if args.srt and os.path.isfile(args.srt) else []
    words = []
    if os.path.isfile(wd):
        with open(wd, encoding="utf-8") as fh:
            words = [(float(w["start"]), float(w["end"]), w.get("text", ""))
                     for w in json.load(fh)["words"] if w.get("start") is not None]

    if args.action == "emit":
        return do_emit(args, sents, bounds, cues, words, e0_dir)
    if args.action == "check":
        return do_check(args, sents, e0_dir)
    return do_apply(args, sents, e0_dir, cues, words)


if __name__ == "__main__":
    sys.exit(main())
