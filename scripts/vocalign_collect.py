# -*- coding: utf-8 -*-
"""vocalign 语音采集：音频 → 词级时轴（文本 + 标点 + 每词起止时间）

定位
    vocalign 工作流的**唯一需要重型依赖的环节**。两步走，必须**分两个进程**
    （`whisperx` 与 `ctranslate2` 同进程会触发 cuDNN 冲突）：

        ① transcribe：faster-whisper **段级**转写 → segments.srt（文本 + 标点）
           ⚠️ 必须用段级（`word_timestamps=False`、`vad_filter=False`）——
              faster-whisper 的**词级**模式标点严重退化（实测最长句 129 词、数字转单词）；
              段级模式标点正常（句末停顿 p50 847ms）。
        ② align：wav2vec2 强制对齐 → words.json（词级时间戳）
           只用 `whisperx.align`，**不用** `whisperx.transcribe`（后者拉 pyannote，同 cuDNN 报错）。

⚠️ **未对齐词必须保留占位**（本脚本的关键行为）
    whisperX 约 2.6% 词对齐失败，实测**几乎全是数字**（`15.` / `3` / `8, 8` / `20`）。
    若像探针脚本那样 `continue` 丢弃，词序列会出现“空洞”→ 前后词直接相邻 →
    跨空洞的间隙被 `vocalign_skeleton.py` 误判为停顿边界，实测伪边界：
        `values of | and`（原文 "values of 1 and 2"）
        `going from | to`（原文 "going from 1 to 15"）
    故本脚本把失败词**保留在序列里、时间置 null**，由骨架构建器按前后锚点插值补齐。

输出（`-o` 目录）
    `segments.srt`  段级转写（文本 + 标点）
    `words.json`    词级时轴（`{"meta": {...}, "words": [{"start","end","text","score"}]}`）
    `collect_report.txt`  采集报告（耗时 / 词数 / 未对齐数 / 间隙统计 / 转录口径）
    `segments.suspect.md`  转写可疑段（重复幻觉 / n-gram 循环 / 语速异常）——**只报不改**

⚠️ **重复幻觉与“只报不改”**
    whisper 在 `condition_on_previous_text=True` 下偶发**重复幻觉**（后段重复前段末句）——
    重复文本占用时间 → 段时长被压缩 → 强制对齐错位 → 骨架伪边界（长句切碎）。
    本脚本**只探测并上报**（`segments.suspect.md`），不自动删改：重复也可能是真实口播，
    删错无从发现；而内容丢失（n-gram 循环跑飞）本就该重跑而非删——交 agent / 人工决策。

⚠️ **运行环境**（本脚本依赖 torch / faster-whisper / whisperx，**不在主 requirements 内**）
    命令根 = Project_Main/；一律用 venv 的 python，**勿 activate**：
        Project_Main\\.venv\\Scripts\\python.exe scripts/vocalign_collect.py audio.mp3 -o <work>/vocalign
    依赖坑与修复见 `Project_Plan/2026-10-08_vocalign工作流设计.md` §6.2。

用法
    python scripts/vocalign_collect.py <音频> -o <work>/vocalign                    # 两步全跑
    python scripts/vocalign_collect.py <音频> -o <work>/vocalign --stage transcribe # 只转写
    python scripts/vocalign_collect.py <音频> -o <work>/vocalign --stage align \\
        --text-srt <已有文本.srt>                                                   # 只对齐（跳过转写，~10s）

退出码：0 = 成功；1 = 依赖缺失 / 步骤失败。
"""
import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

DEFAULT_MODEL = "large-v3"
DEFAULT_DEVICE = "cuda"
DEFAULT_COMPUTE = "float16"
DEFAULT_LANG = "en"
SR = 16000                 # 音频采样率（faster-whisper 要求 16k）

# ---- 幻觉探测阈值（只报不改）----
SUSPECT_CPS_LOW = 8.0      # 字符/秒 下限（正常语速 ~15）
SUSPECT_CPS_HIGH = 28.0    # 字符/秒 上限（超此值 = 时长被压缩）
SUSPECT_DUP_WORDS = 6      # 段首重复紧前段末 ≥ 此词数 → 可疑
SUSPECT_NGRAM = 8          # 循环检测的 n-gram 长度
SUSPECT_NGRAM_RUN = 3      # 连续重复 ≥ 此次数 → 内容可能已丢失
# “语速过慢”的短段免检：该下限是为**段级**（一段多词）定的；
# 可疑点重识别（`--patch-pad`）下分段变细，短句（`8.` / `this`）天然低于下限 → 全是假阳性。
# 实测（PRR2，±20s 窗口）：不免检则报 5 处假阳性（均为 <6 词的极短段）。
SUSPECT_CPS_MIN_WORDS = 6
WORD_RE = re.compile(r"[A-Za-z0-9']+")

# ---- 可疑点重识别（补丁式抑制幻觉）----
# 为何是“可疑点 ± N 秒重识别 + 拼接”而非“全片切片”：
#   · 修复率：实测 6/6 可疑点全部修好（全片切片 30s 只有 4/8）
#   · S 编号扰动：151→148（变 3 个）vs 全片切片 151→136（变 15 个）→ 下游可复用性差很多
#   · 成本：22s vs 74s；只重识别约 13% 的音频
#   · 锚点可**主动选**（可疑点两侧最近的强边界），而全片切片的接缝被固定网格锁死
# 拼接规则：替换区 [a,b] 由可疑点两侧最近的**句末标点**界定（[PATCH_EDGE_MIN_S, PATCH_EDGE_MAX_S] 内）；
# 找不到则兜底取 ±PATCH_FALLBACK_S，并在报告里标注（不静默）。
PATCH_PAD_S = 20.0         # 可疑点前后各取此秒数重识别（`--patch-pad`；0 = 关闭）——**默认启用**
PATCH_MERGE_S = 3.0        # 相邻可疑段相距近于此值 → 合并为同一个重识别窗口
PATCH_EDGE_MIN_S = 3.0     # 替换区边界距可疑点的**最小**距离（避免切在可疑点自己身上）
PATCH_EDGE_MAX_S = 16.0    # 找强边界时向两侧最远看多远（超过则兜底）
PATCH_FALLBACK_S = 8.0     # 找不到强边界时的兜底半径（报告标注为 fallback）
PATCH_PAIR_TOL_S = 0.4     # 两版段边界“配对”容差（实测两版时间戳偏差 p90 = 0.42s）
PATCH_DIFF_MIN = 1         # 差异清单最少词数（1 = 不过滤；调大可只看显著差异）
PATCH_SEAM_TAG_S = 2.0     # 距替换区边界近于此值 → 差异标注〔接缝〕（拼接副作用而非内容改变）
SENT_TERM = ".?!"          # 句末标点（拼接锚点用，与骨架同口径）

# 差异比对的**字符归一**——先归一再比，否则下列“非差异”会淹没有效信息：
# 连字符（`right-clicking` vs `right clicking`）、数字写法（`two` vs `2`）。
_NUMWORD = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "eleven": "11", "twelve": "12", "thirteen": "13", "fourteen": "14",
    "fifteen": "15", "sixteen": "16", "seventeen": "17", "eighteen": "18",
    "nineteen": "19", "twenty": "20", "thirty": "30", "forty": "40",
    "fifty": "50", "sixty": "60", "seventy": "70", "eighty": "80", "ninety": "90",
}


def _require(mod, hint):
    try:
        return __import__(mod)
    except ImportError:
        sys.exit("❌ 缺少依赖 %s。%s\n   运行环境：%s" % (
            mod, hint, os.path.join(".venv", "Scripts", "python.exe")))


def _fmt_srt_time(sec):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)


def hms(sec):
    """HH:MM:SS（报告用，去毫秒）"""
    return _fmt_srt_time(sec)[:-4]


def _write_srt(path, segs):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for i, s in enumerate(segs, 1):
            fh.write("%d\n%s --> %s\n%s\n\n" % (
                i, _fmt_srt_time(s["start"]), _fmt_srt_time(s["end"]), s["text"]))


def _parse_srt(path):
    with open(path, encoding="utf-8-sig") as fh:
        raw = fh.read()
    time_re = re.compile(
        r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})")
    out = []
    for block in re.split(r"\n\s*\n", raw.strip()):
        lines = [x for x in block.split("\n") if x.strip()]
        ti, m = None, None
        for i, ln in enumerate(lines):
            m = time_re.search(ln)
            if m:
                ti = i
                break
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0
        end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0
        out.append({"start": start, "end": end, "text": " ".join(lines[ti + 1:]).strip()})
    return out


# ---------------------------------------------------------------- 幻觉探测

def _toks(text):
    return WORD_RE.findall(text.lower())


def _repeat_prefix_len(prev_text, cur_text, cap=40):
    """cur 段首与 prev 段尾重合的词数（condition_on_previous_text 幻觉的典型形态）。"""
    a, b = _toks(prev_text), _toks(cur_text)
    best = 0
    for k in range(1, min(len(a), len(b), cap) + 1):
        if a[-k:] == b[:k]:
            best = k
    return best


def _find_ngram_loops(segments, n=SUSPECT_NGRAM, min_run=SUSPECT_NGRAM_RUN):
    """跨段找连续重复 ≥min_run 次的 n-gram 循环（whisper 跑飞的形态）。

    **跨段是必须的**：跑飞区间常横跨多个段（每段各含 2 次重复，单段内达不到阈值）。
    返回 [(起段, 止段, 短语, 次数)]。
    """
    flat, owner = [], []
    for i, seg in enumerate(segments, 1):
        for w in _toks(seg["text"]):
            flat.append(w)
            owner.append(i)
    loops, i = [], 0
    while i + n <= len(flat):
        g = tuple(flat[i:i + n])
        cnt, j = 1, i + n
        while j + n <= len(flat) and tuple(flat[j:j + n]) == g:
            cnt += 1
            j += n
        if cnt >= min_run:
            loops.append((owner[i], owner[min(j, len(owner)) - 1], " ".join(g), cnt))
            i = j
        else:
            i += 1
    merged = []
    for a, b, g, c in loops:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b),
                          merged[-1][2] if len(merged[-1][2]) >= len(g) else g,
                          max(merged[-1][3], c))
        else:
            merged.append((a, b, g, c))
    return merged


def detect_suspects(segments):
    """探测转写幻觉（**只报不改**）。返回 (逐段清单, 循环区间)。

    为什么只报不改：重复可能是**真实口播**（刻意的重复、强调），删错了无法发现；
    而内容丢失（循环跑飞）本就该重跑而非删——故交 agent / 人工决策。
    """
    loops = _find_ngram_loops(segments)
    loop_segs = set()
    for a, b, _g, _c in loops:
        loop_segs.update(range(a, b + 1))
    rows = []
    for i, seg in enumerate(segments, 1):
        dur = max(0.2, seg["end"] - seg["start"])
        cps = len(seg["text"]) / dur
        kinds = []
        if i in loop_segs:
            kinds.append("n-gram 循环（该段内容可能已被循环挤掉）")
        if i > 1:
            k = _repeat_prefix_len(segments[i - 2]["text"], seg["text"])
            if k >= SUSPECT_DUP_WORDS:
                kinds.append("段首重复前段末 %d 词" % k)
        if cps > SUSPECT_CPS_HIGH:
            kinds.append("语速过快 %.0f 字符/秒" % cps)
        elif cps < SUSPECT_CPS_LOW and len(_toks(seg["text"])) >= SUSPECT_CPS_MIN_WORDS:
            kinds.append("语速过慢 %.0f 字符/秒" % cps)
        if kinds:
            rows.append({"i": i, "start": seg["start"], "end": seg["end"],
                         "cps": round(cps, 1), "kinds": kinds, "text": seg["text"]})
    return rows, loops


def report_suspects(segments, args, report):
    """写 `segments.suspect.md` 并打印摘要（幻觉探测，只报不改）。返回 rows 供调用方复用。"""
    rows, loops = detect_suspects(segments)
    report["suspects"] = {"n_segments": len(rows), "n_loops": len(loops),
                          "loops": [{"from": a, "to": b, "phrase": g, "count": c}
                                    for a, b, g, c in loops]}
    if not rows:
        print("幻觉探测：无异常段")
        return rows
    path = os.path.join(args.out, "segments.suspect.md")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# 转写可疑段（幻觉探测，**只报不改**）\n\n")
        fh.write("> 可疑 %d 段 / 共 %d 段；循环区间 %d 处。\n" % (len(rows), len(segments), len(loops)))
        fh.write("> whisper 在前文上下文中偶发**重复幻觉**；重复文本占用时间 → 段时长被压缩 →\n")
        fh.write("> 强制对齐错位 → 骨架在该处产生伪边界（长句被切碎）。\n\n")
        fh.write("## 逐段清单\n\n")
        for r in rows:
            fh.write("- 段 %d（%s → %s，%.0f 字符/秒）：%s\n" % (
                r["i"], hms(r["start"]), hms(r["end"]), r["cps"], "；".join(r["kinds"])))
            fh.write("  - 文本：%s\n" % r["text"][:120])
        if loops:
            fh.write("\n## 循环区间（内容可能已丢失）\n\n")
            for a, b, g, c in loops:
                fh.write("- 段 %d–%d：`%s` ×%d\n" % (a, b, g, c))
        fh.write("\n## 处置（agent / 人工决策；脚本不自动改）\n\n")
        fh.write("- **重复型**：重复文本占用了时间 → 删去重复片段（内容无损失）后重跑对齐与骨架。\n")
        fh.write("- **循环型**：该时间区间的真实内容**已被循环挤掉**，删重复无法恢复"
                 " → 取该时间区间**重跑识别**（截取音频重转写，替换对应段）。\n")
        fh.write("- **语速异常型**：多为上述两者的伴随症状；单独出现时核对音频确认。\n")
        fh.write("- 处置后必须**重跑骨架**（长句切分依赖时间，时间变了切分即变）。\n")
    print("⚠️ 幻觉探测：%d 段可疑（%d 处循环）→ %s" % (len(rows), len(loops), path))
    return rows


# ---------------------------------------------------------------- 可疑点重识别

def suspect_windows(rows, merge_s=PATCH_MERGE_S):
    """可疑段清单 → 重识别窗口中心（相邻者合并）

    合并为何必须：两段相距极近时（实测 534.9s / 535.4s）各自开窗口会重复解码
    同一段音频，且拼接时两个替换区互相干扰。
    """
    if not rows:
        return []
    centers, cur = [], [rows[0]]
    for r in rows[1:]:
        if r["start"] - cur[-1]["end"] <= merge_s:
            cur.append(r)
        else:
            centers.append(sum((x["start"] + x["end"]) / 2 for x in cur) / len(cur))
            cur = [r]
    centers.append(sum((x["start"] + x["end"]) / 2 for x in cur) / len(cur))
    return centers


def patch_region(full, center, pad, alt=None):
    """可疑点 → 替换区 [a, b]（两侧最近的**句末标点**边界）

    为何必须落在句界：否则会把一句话劈成两半（前半来自全片版、后半来自重识别版），
    接缝处措辞 / 标点会突变。句末标点处两版都有完整句子 —— 实测窗口内强边界句
    可对应 13/17（76%），故拼接可靠。

    边界选取优先级：
      1. `paired` 全片版句末标点 **且** 重识别版在该处也有段边界——**为何最优**：
         两版时间戳有偏差（p90 0.42s），若只取一版边界，另一版的段会跨过接缝
         → 接缝两侧各取一个同时段的段 → 同一句出现两遍（实测不配对时 3 处重复）
      2. `strong` 仅全片版句末标点（再吸附到全片段界）
      3. `alt` 仅重识别版句末标点——幻觉区常伴随全片版标点缺失（实测 5/12 边界）
      4. `fallback` 固定 ±PATCH_FALLBACK_S（最后退路，报告标注）
    """
    lo = max(center - pad, center - PATCH_EDGE_MAX_S)
    hi = min(center + pad, center + PATCH_EDGE_MAX_S)
    alt_edges = sorted({x["start"] for x in alt} | {x["end"] for x in alt}) if alt else []

    def strong(is_left):
        if is_left:
            c = [x["end"] for x in full if lo <= x["end"] <= center - PATCH_EDGE_MIN_S
                 and x["text"].rstrip()[-1:] in SENT_TERM]
            return max(c) if c else None
        c = [x["end"] for x in full if center + PATCH_EDGE_MIN_S <= x["end"] <= hi
             and x["text"].rstrip()[-1:] in SENT_TERM]
        return min(c) if c else None

    def pick(is_left):
        fc = strong(is_left)
        if fc is None:
            ac = [x["end"] for x in alt if ((center - PATCH_EDGE_MIN_S >= x["end"] >= lo)
                                            if is_left else
                                            (center + PATCH_EDGE_MIN_S <= x["end"] <= hi))
                  and x["text"].rstrip()[-1:] in SENT_TERM] if alt else []
            if ac:
                return (max(ac) if is_left else min(ac)), "alt"
            return (center - PATCH_FALLBACK_S if is_left else center + PATCH_FALLBACK_S), "fallback"
        # 有全片强边界：若重识别版在该处也有段边界 → paired；否则 strong（后续吸附）
        if alt_edges and any(abs(fc - e) <= PATCH_PAIR_TOL_S for e in alt_edges):
            return fc, "paired"
        return fc, "strong"

    a, a_src = pick(True)
    b, b_src = pick(False)
    return {"a": a, "b": b, "a_src": a_src, "b_src": b_src}


def _snap_edges(t, edges, tol=PATCH_EDGE_MIN_S):
    """把时间点吸附到最近的段边界（容差内）；超容差则原样返回

    为何必须：拼接点若不是全片版段边界，就会有**跨接缝的段**两侧各取一个
    → 同一句话出现两遍（实测：不吸附时 6 个窗口产生 5 处“段首重复前段末”）。
    `strong` 边界本已是全片段边界，无需吸附。
    """
    if not edges:
        return t, False
    best = min(edges, key=lambda e: abs(e - t))
    return (best, True) if abs(best - t) <= tol else (t, False)


def _norm_word(w):
    """词的比对归一形：小写、去一切非字母数字、数字词归阿拉伯数字

    为何必须归一：否则下列**非差异**会淹没差异清单——
    连字符（`right-clicking` 对 `right clicking`）、数字写法（`two` 对 `2`）。
    """
    t = re.sub(r"[^a-z0-9]", "", w.lower())
    return _NUMWORD.get(t, t)


def _words_of(segs):
    """段列表 → [(归一词, 原词, 所属段起始秒)]（差异定位用）

    ⚠️ **按分隔符拆词**：`right-clicking` → `right` + `clicking`，
    否则它会与另一版的 `right clicking`（两个词）比不中（实测这是最大一类假差异）。
    """
    out = []
    for s in segs:
        for w in s["text"].split():
            for part in re.split(r"[^A-Za-z0-9]+", w):
                if not part:
                    continue
                out.append((_NUMWORD.get(part.lower(), part.lower()), w, s["start"]))
    return out


def window_diff(full_segs, used_segs):
    """两版词级差异（**只列不同处**，一致的不列）

    返回 [{"kind": "del"/"add"/"chg", "t": 秒, "text": 原文, "new": 新文（仅 chg）}]。
    为何分三态而非“哪版有”：用户要判断的是**改动对不对**——
    把同一处的删与增配成一条 `改「旧」→「新」` 比并列两条好读得多。
    """
    fa, pb = _words_of(full_segs), _words_of(used_segs)
    sm = difflib.SequenceMatcher(None, [x[0] for x in fa], [x[0] for x in pb], autojunk=False)
    rows = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        old = " ".join(x[1] for x in fa[i1:i2])
        new = " ".join(x[1] for x in pb[j1:j2])
        t = fa[i1][2] if i2 > i1 else pb[j1][2]
        if tag == "delete":
            rows.append({"kind": "del", "t": t, "text": old})
        elif tag == "insert":
            rows.append({"kind": "add", "t": t, "text": new})
        else:
            rows.append({"kind": "chg", "t": t, "text": old, "new": new})
    return [r for r in rows if len(r["text"].split()) >= PATCH_DIFF_MIN
            or len((r.get("new") or "").split()) >= PATCH_DIFF_MIN]


def _overlap_majority(segs, a, b):
    """与 [a, b] 重叠**过半**的段（**比对范围**用）

    为何与拼接的“相交”判据分开：拼接必须用“相交”（否则两侧都没人要 → 丢内容），
    但那会让“同一句因两版归属不同段”进入比对 → 报成假差异。
    比对只看**主体在区内**的段，边界归属噪声即消失（实测降噪 29 → 15 处）。
    """
    out = []
    for x in segs:
        ov = min(x["end"], b) - max(x["start"], a)
        if ov > 0.5 * max(x["end"] - x["start"], 1e-6):
            out.append(x)
    return out


def _diff_line(d, seam=False):
    """差异 → 报告行（`删/增/改` 三态；接缝处另标注）"""
    tag = {"del": "删", "add": "增", "chg": "改"}[d["kind"]]
    body = ("%s「%s」" % (tag, d["text"]) if d["kind"] != "chg"
            else "改「%s」→「%s」" % (d["text"], d["new"]))
    return "%s%s" % ("【接缝】" if seam else "", body)


def _cache_read(path, pad):
    """读窗口转写缓存（`--patch-decisions` 反复裁决时免去重复转写）"""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except (ValueError, OSError):
        return None
    return d.get("segs") if d.get("pad") == pad else None


def _cache_write(path, pad, segs):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"pad": pad, "segs": segs}, fh, ensure_ascii=False)


def load_decisions(path, n_windows):
    """读人工裁决 tsv → {窗口号(1-based): "revert"}；只记非 keep 项

    格式（与 `_fix_splits.tsv` / `r00_gaps_active.tsv` 同惯例：制表符分隔、`#` 注释）：
        # 窗口号	裁决
        2	revert
    裁决语义：`revert` = 该窗口**回退为全片版**（补丁内容丢弃）；`keep` = 保留补丁（默认）。
    """
    if not path:
        return {}
    if not os.path.isfile(path):
        sys.exit("❌ --patch-decisions 文件不存在：%s" % path)
    out = {}
    with open(path, encoding="utf-8-sig") as fh:
        for ln in fh:
            if ln.startswith("#") or not ln.strip():
                continue
            p = ln.rstrip("\n").split("\t")
            if len(p) < 2 or not p[0].strip().isdigit():
                sys.exit("❌ 裁决行格式错（应 `<窗口号>\\t<keep|revert>`）：%s" % ln.strip()[:60])
            k, v = int(p[0].strip()), p[1].strip().lower()
            if v not in ("keep", "revert"):
                sys.exit("❌ 裁决值应为 `keep` / `revert`，实为 `%s`：%s" % (v, ln.strip()[:60]))
            if not 1 <= k <= n_windows:
                sys.exit("❌ 窗口号 %d 越界（当前共 %d 个窗口）" % (k, n_windows))
            if v == "revert":
                out[k] = v
    return out


def _transcribe_slice(model, audio, sr, a_s, b_s, args):
    """重识别 [a_s, b_s) 音频 → 分段（时间戳为**相对真实音频的绝对时间**）

    口径与主转写完全一致（段级、无 VAD、同 model/语言/前文上下文/n-gram 限制）——
    否则两版不可比，拼接后会出现风格断层。
    """
    a = int(max(0.0, a_s) * sr)
    b = int(min(len(audio), b_s * sr))
    it, _info = model.transcribe(
        audio[a:b], language=args.language, word_timestamps=False, vad_filter=False,
        condition_on_previous_text=not args.no_cond_prev,
        no_repeat_ngram_size=args.no_repeat_ngram or None)
    off = a / float(sr)
    return [{"start": off + float(s.start), "end": off + float(s.end),
             "text": str(s.text).strip()} for s in it]


def stage_patch(args, report, full=None, rows=None, model=None, decisions_path=None):
    """可疑点 ±`--patch-pad` 重识别 → 与全片版**拼接**（抑制前文污染幻觉）

    产出：
      `segments_patched.srt`  拼接稿（`--stage align` 会自动优先取它）
      `patch_report.md`       **差异清单（待裁决）** + 逐窗口对照
      `patch_decisions.tsv`   人工裁决表（首次产模板，**不覆盖已有裁决**）
      `patch_windows/`        各窗口转写缓存（裁决后重拼免重转写，秒级）

    `model` 可由调用方传入（转写阶段已加载实例）——**必须复用**：
    第二个 large-v3 实例会把显存占满、慢 4 倍（实测 22s → 95s）。
    """
    _require("faster_whisper", "安装：pip install faster-whisper")
    from faster_whisper import WhisperModel
    from faster_whisper.audio import decode_audio

    out_path = os.path.join(args.out, "segments_patched.srt")
    rep_path = os.path.join(args.out, "patch_report.md")
    dec_path = os.path.join(args.out, "patch_decisions.tsv")
    # 裁决表：显式指定优先；否则用产物目录下的同名文件（存在即用，否则视为无裁决）
    if decisions_path is None:
        decisions_path = dec_path if os.path.isfile(dec_path) else None
    if full is None:
        src = os.path.join(args.out, "segments.srt")
        if not os.path.isfile(src):
            sys.exit("❌ 找不到 %s（请先跑 --stage transcribe）" % src)
        full = _parse_srt(src)
    if rows is None:
        rows, _loops = detect_suspects(full)
    centers = suspect_windows(rows)

    if not centers:
        _write_srt(out_path, full)
        with open(rep_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# 可疑点重识别报告\n\n- 可疑段 0 处 → **未重识别**；"
                     "`segments_patched.srt` = 原样拷贝。\n")
        report["patch"] = {"n_windows": 0, "note": "无可疑段"}
        print("可疑点重识别：无可疑段，跳过（patched 稿 = 原样）")
        return out_path

    decisions = load_decisions(decisions_path, len(centers))
    edges = sorted({x["start"] for x in full} | {x["end"] for x in full})
    cache_dir = os.path.join(args.out, "patch_windows")

    # ---- 转写（缓存优先：裁决来回改时免重复转写）----
    t0 = time.perf_counter()
    wins, n_new = [], 0
    for wi, c in enumerate(centers, 1):
        cp = os.path.join(cache_dir, "win%02d.json" % wi)
        wins.append({"wi": wi, "center": c, "cache": cp,
                     "segs": _cache_read(cp, args.patch_pad)})
    todo = [w for w in wins if w["segs"] is None]
    if todo:
        if model is None:
            model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)
        audio = decode_audio(args.audio, sampling_rate=SR)
        for w in todo:
            w["segs"] = _transcribe_slice(model, audio, SR, w["center"] - args.patch_pad,
                                          w["center"] + args.patch_pad, args)
            _cache_write(w["cache"], args.patch_pad, w["segs"])
            n_new += 1
    audio_s = None
    if n_new == 0:                       # 全命中缓存：不必解码音频，用末段时间估时长
        audio_s = max(x["end"] for x in full)
    else:
        audio_s = len(audio) / float(SR)
    dur = time.perf_counter() - t0

    # ---- 边界、采用段、差异（每个窗口）----
    for w in wins:
        reg = patch_region(full, w["center"], args.patch_pad, alt=w["segs"])
        # 非 paired/strong 边界 → 吸附到全片段界（否则接缝处会出重叠）
        reg["a_snap"] = reg["b_snap"] = True
        if reg["a_src"] not in ("strong", "paired"):
            reg["a"], reg["a_snap"] = _snap_edges(reg["a"], edges)
        if reg["b_src"] not in ("strong", "paired"):
            reg["b"], reg["b_snap"] = _snap_edges(reg["b"], edges)
        w.update(reg)
        # 补丁段取**与替换区相交**者（含“跨接缝”的段）——
        # 为何不取 `a <= start < b`（严格）：补丁版与全片版的段边界不可能完全重合，
        # 严格判据会把跨接缝的补丁段丢弃，而全片版相对应的段又已被替换区剔除
        # → **两侧都不要** → 内容丢失（实测丢了 `when the main input is 6 or more.`）。
        # 重叠由后面的“接缝去重”处理（代价可控：实测均为冗余重复）。
        w["used"] = [x for x in w["segs"] if x["start"] < w["b"] and x["end"] > w["a"]]
        w["region_full"] = [x for x in full if x["start"] < w["b"] and x["end"] > w["a"]]
        w["decision"] = decisions.get(w["wi"], "keep")
        # 差异**始终按补丁内容算**（即便本窗口已回退），便于复核裁决是否正确
        # 比对用“重叠过半”判据（非“相交”）——后者会把边界归属差当成内容差异
        w["diff"] = window_diff(_overlap_majority(full, w["a"], w["b"]),
                                 _overlap_majority(w["segs"], w["a"], w["b"]))
        # 接缝（替换区两端）附近的差异多为拼接副作用（去重/边界不重合），打标区分
        for d in w["diff"]:
            d["seam"] = min(abs(d["t"] - w["a"]), abs(d["t"] - w["b"])) <= PATCH_SEAM_TAG_S

    keep = [w for w in wins if w["decision"] == "keep"]
    out = [x for x in full
           if not any(x["start"] < w["b"] and x["end"] > w["a"] for w in keep)]
    out += [x for w in keep for x in w["used"]]
    out.sort(key=lambda x: x["start"])

    # ---- 接缝去重（**定向**，只动窗口边界 ±2s 内；只对保留补丁的窗口）----
    # 为何需要：两版段边界不可能完全重合（时间戳偏差 p90 0.42s），取任一边界都会让
    # 另一版的段跨过接缝 → 接缝两侧各有一段覆盖同一句话 → 该句出现两遍（实测 3 处）。
    # 与其追求“边界完全对齐”（做不到），不如**删掉后段的重复开头**（重复的词本就是冗余）。
    # 定向 + 阈值 3 + 逐条入报告，避免误删真实口播的刻意重复。
    dedup = []
    bounds = [t for w in keep for t in (w["a"], w["b"])]
    for i in range(1, len(out)):
        if not any(abs(out[i]["start"] - t) <= 2.0 or abs(out[i - 1]["end"] - t) <= 2.0
                   for t in bounds):
            continue
        k = _repeat_prefix_len(out[i - 1]["text"], out[i]["text"], cap=24)
        if k >= 3:
            wds = out[i]["text"].split()
            dedup.append({"t": out[i]["start"], "k": k,
                          "removed": " ".join(wds[:k]), "rest": " ".join(wds[k:])})
            out[i]["text"] = " ".join(wds[k:])
            out[i]["start"] = out[i - 1]["end"]          # 时间接到前段末尾
    if dedup:
        out = [x for x in out if x["text"].strip()]      # 去重后剩空文本的段删除

    # 自检：时间不得倒挂（拼接点处两版时间基不同，实测 0 倒挂；有则告警不静默）
    inv = ["%.2fs" % out[i - 1]["end"] for i in range(1, len(out))
           if out[i]["start"] < out[i - 1]["start"] - 0.001]
    n_fb = sum(1 for w in wins if w["a_src"] == "fallback") + \
        sum(1 for w in wins if w["b_src"] == "fallback")
    n_rev = len(wins) - len(keep)
    # 自检：拼接后不得出现“段首重复前段末”（接缝重叠的症状，实测不吸附时 5 处）
    sus = detect_suspects(out)[0]
    dup = [r for r in sus if any("重复" in k for k in r["kinds"])]
    fast = [r for r in sus if any("过快" in k for k in r["kinds"])]
    _write_srt(out_path, out)

    # 裁决模板（**不覆盖已有裁决**：用户的判断优先于脚本）
    if not os.path.exists(dec_path):
        with open(dec_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# 可疑点重识别裁决\n")
            fh.write("# 格式：<窗口号>\\t<keep|revert>（制表符分隔；`#` 开头为注释）\n")
            fh.write("# 语义：revert = 该窗口**回退为全片版**（丢弃补丁内容）；keep = 保留补丁\n")
            fh.write("# 未列出的窗口默认 keep。窗口号与差异见 patch_report.md 的差异清单。\n")
            fh.write("# 改后重跑：--stage patch --patch-decisions \"<本文件路径>\"（窗口转写有缓存，仅需秒级重拼）\n")
            for w in wins:
                fh.write("%d\tkeep\n" % w["wi"])

    n_diff_all = sum(len([d for d in w["diff"] if not d.get("seam")]) for w in keep)
    with open(rep_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# 可疑点重识别报告\n\n")
        fh.write("- 可疑段 %d → 重识别窗口 **%d** 个（相邻段相距 ≤%.0fs 合并）\n"
                 % (len(rows), len(wins), PATCH_MERGE_S))
        fh.write("- 重识别半径 ±%.0fs（共约 %.0fs 音频，占全片 %.0f%%）；耗时 %.1fs%s\n"
                 % (args.patch_pad, 2 * args.patch_pad * len(wins),
                    100.0 * 2 * args.patch_pad * len(wins) / max(audio_s, 1.0), dur,
                    "（%d 个窗口命中缓存）" % (len(wins) - n_new) if n_new < len(wins) else ""))
        fh.write("- 拼接：全片版 %d 段 − 替换 %d 段 + 补丁 %d 段 = **%d 段**（原 %d）\n"
                 % (len(full), len(full) - len(out) + sum(len(w["used"]) for w in keep),
                    sum(len(w["used"]) for w in keep), len(out), len(full)))
        fh.write("- 裁决：保留补丁 %d 个窗口 / **回退全片版 %d 个**%s\n"
                 % (len(keep), n_rev,
                    "（`%s`）" % os.path.basename(dec_path) if n_rev else ""))
        fh.write("- 时间倒挂：%s\n" % ("⛔ **%d 处**（%s）" % (len(inv), ", ".join(inv[:5]))
                                        if inv else "0 处 ✓"))
        fh.write("- 拼接后自检：可疑段 **%d** 处（过快 %d / 段首重复 %d）——全片稿为 %d 处\n"
                 % (len(sus), len(fast), len(dup), len(rows)))
        if dedup:
            fh.write("- 接缝去重：**%d 处**（两版段边界不重合，接缝两侧各取一段所致；"
                     "已删后段重复开头）\n" % len(dedup))
        if n_fb:
            fh.write("- ⚠️ 兜底边界 %d 处（未找到句子末标点锚点，按 ±%.0fs 取）——该处拼接可能落在句中\n"
                     % (n_fb, PATCH_FALLBACK_S))
        if any(not w["a_snap"] or not w["b_snap"] for w in keep):
            fh.write("- ⚠️ 有边界未能吸附到全片段界（容差 ±%.0fs）——该处可能出重叠\n"
                     % PATCH_EDGE_MIN_S)

        # ---- 差异清单（**待裁决**；用户只看这里，不必读全文）----
        fh.write("\n## 差异清单（**待裁决**）\n\n")
        fh.write("> 只列两版**文本不同**处（已归一分词与数字写法：`right-clicking` = `right clicking`、`two` = `2`）；"
                 "**未列出的内容两版一致**，不必核对。\n")
        fh.write("> 标〔接缝〕者为替换区两端附近的差异，多为拼接副作用（去重 / 两版边界不重合），**不是内容改动**。\n")
        fh.write("> 但“一致”不等于“都正确”——两版可能同样听错（本机制只能消前文污染型幻觉，不能纠误听）。\n\n")
        fh.write("| 窗口 | 可疑点 | 差异 | 状态 | 摘要 |\n|---|---|---|---|---|\n")
        for w in wins:
            st = "已回退全片版" if w["decision"] != "keep" else "保留补丁"
            if not w["diff"]:
                st = "两版一致" if w["decision"] == "keep" else "两版一致（已回退）"
            core = [d for d in w["diff"] if not d.get("seam")]
            smry = "；".join(_diff_line(d)[:46] for d in core[:2]) or \
                ("（仅接缝副作用）" if w["diff"] else "—")
            fh.write("| %d | %s | %d%s | %s | %s |\n"
                     % (w["wi"], hms(w["center"]), len(core),
                        "（+%d 接缝）" % (len(w["diff"]) - len(core))
                        if len(core) < len(w["diff"]) else "", st, smry))
        fh.write("\n**裁决方法**：把要回退为全片版的窗口写入 `%s`（`<窗口号>\\trevert`），"
                 "再重跑本阶段：\n\n```\n%s scripts/%s <音频> --stage patch --patch-pad %.0f "
                 "-o \"<W>/vocalign\" --patch-decisions \"<W>/vocalign/%s\"\n```\n\n"
                 "窗口转写有缓存（`patch_windows/`），改裁决后**只需秒级重拼**。\n"
                 % (os.path.basename(dec_path), os.path.join(".venv", "Scripts", "python.exe"),
                    os.path.basename(__file__), args.patch_pad, os.path.basename(dec_path)))

        # ---- 逐窗口（差异明细在前，全文对照折叠）----
        fh.write("\n## 逐窗口\n\n")
        for w in wins:
            core_w = [d for d in w["diff"] if not d.get("seam")]
            fh.write("### 窗口 %d：可疑点 %s（差异 %d 处；%s）\n\n"
                     % (w["wi"], hms(w["center"]), len(core_w),
                        "已回退全片版" if w["decision"] != "keep" else "保留补丁"))
            fh.write("- 替换区 %s → %s（宽 %.1fs；左界 %s / 右界 %s）；重识别 %d 段 → 采用 %d 段\n"
                     % (hms(w["a"]), hms(w["b"]), w["b"] - w["a"],
                        w["a_src"], w["b_src"], len(w["segs"]), len(w["used"])))
            if not w["diff"]:
                fh.write("- **两版文本一致**（无需裁决）\n\n")
            else:
                fh.write("\n**改动明细**（`删 / 增 / 改` 均为“补丁版相对全片版”的改动）\n\n")
                for d in w["diff"]:
                    fh.write("- [%s] %s\n" % (hms(d["t"]), _diff_line(d, d.get("seam"))))
                fh.write("\n")
            fh.write("<details><summary>两版全文对照（仅供参考）</summary>\n\n")
            for kind, segs in (("全片版原内容（被替换）", w["region_full"]),
                               ("重识别内容", w["used"])):
                fh.write("**%s**\n\n" % kind)
                for x in segs:
                    cps = len(x["text"]) / max(x["end"] - x["start"], 0.01)
                    fh.write("- `%s` %s（%.1fs / %.0f 字符每秒）：%s\n"
                             % (hms(x["start"]), hms(x["end"]), x["end"] - x["start"],
                                cps, x["text"]))
                fh.write("\n")
            fh.write("</details>\n\n")
        if dedup:
            fh.write("## 接缝去重明细\n\n")
            for d in dedup:
                fh.write("- %s：删 %d 词「%s」→ 余「%s」\n"
                         % (hms(d["t"]), d["k"], d["removed"], d["rest"] or "（空，整段删除）"))
            fh.write("\n")
        fh.write("## 处置\n\n")
        fh.write("- 拼接稿供后续 `--stage align` 使用（`--stage align` 会自动优先取本稿）。\n")
        fh.write("- 仍有可疑段时：加大 `--patch-pad` 重跑 `--stage transcribe`"
                 "（旧缓存按 pad 值自动失效）。\n")
        fh.write("- 若某窗口两版差异极大（非重复幻觉），人工核对音频后再决定采信哪版。\n")

    report["patch"] = {"n_windows": len(wins), "seconds": round(dur, 1),
                       "n_cached": len(wins) - n_new, "n_reverted": n_rev,
                       "n_replaced": len(full) - len(out) + sum(len(w["used"]) for w in keep),
                       "n_used": sum(len(w["used"]) for w in keep),
                       "n_out": len(out), "n_inverted": len(inv), "n_fallback_edge": n_fb,
                       "n_dup_after": len(dup), "n_fast_after": len(fast),
                       "n_dedup": len(dedup), "n_diff": n_diff_all,
                       "pad_s": args.patch_pad,
                       "regions": [{"wi": w["wi"], "center": round(w["center"], 2),
                                    "a": round(w["a"], 2), "b": round(w["b"], 2),
                                    "a_src": w["a_src"], "b_src": w["b_src"],
                                    "decision": w["decision"],
                                    "n_diff": len([d for d in w["diff"] if not d.get("seam")]),
                                    "n_seam": len([d for d in w["diff"] if d.get("seam")]),
                                    "used": len(w["used"])} for w in wins]}
    print("可疑点重识别：%d 窗口 / ±%.0fs / %.1fs%s → 拼接稿 %d 段（原 %d）%s"
          % (len(wins), args.patch_pad, dur,
             "（%d 命中缓存）" % (len(wins) - n_new) if n_new < len(wins) else "",
             len(out), len(full), "  ⛔ 时间倒挂 %d 处" % len(inv) if inv else ""))
    print("  实质差异 %d 处（保留补丁 %d 窗口 / 回退 %d）；拼接后可疑段 %d 处（全片稿 %d 处）"
          % (n_diff_all, len(keep), n_rev, len(sus), len(rows)))
    if n_fb:
        print("  ⚠️ 兜底边界 %d 处（未找到句末标点锚点）" % n_fb)
    if dup:
        print("  ⚠️ 接缝重叠（段首重复）%d 处——详见报告" % len(dup))
    print("  报告：%s（**差异清单待裁决**）" % rep_path)
    return out_path


def stage_transcribe(args, report):
    """faster-whisper 段级转写 → segments.srt"""
    _require("faster_whisper", "安装：pip install faster-whisper")
    from faster_whisper import WhisperModel
    srt_path = os.path.join(args.out, "segments.srt")
    t0 = time.perf_counter()
    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)
    # 注：`WhisperModel.transcribe` 无 batch_size（批处理属 BatchedInferencePipeline，
    # 会默认开启 VAD 分块，破坏本工作流要求的“段级 + 无 VAD”口径）→ 走原生串行调用
    # 注：`condition_on_previous_text` 开启时有标点优势，但 whisper 在前文条件下偶发
    # **段级重复幻觉**（后段重复前段末句）→ 重复段时距被压缩 → 强制对齐错位 → 骨架伪边界；
    # 可用 `--no-repeat-ngram` 抑制、或 `--no-cond-prev` 关闭前文上下文（实测标点会退化）
    segments, info = model.transcribe(
        args.audio, language=args.language, word_timestamps=False, vad_filter=False,
        condition_on_previous_text=not args.no_cond_prev,
        no_repeat_ngram_size=args.no_repeat_ngram or None)
    segs = list(segments)
    with open(srt_path, "w", encoding="utf-8", newline="\n") as fh:
        for i, s in enumerate(segs, 1):
            fh.write("%d\n%s --> %s\n%s\n\n" % (
                i, _fmt_srt_time(s.start), _fmt_srt_time(s.end), str(s.text).strip()))
    dur = time.perf_counter() - t0
    report["transcribe"] = {"seconds": round(dur, 1), "segments": len(segs),
                            "audio_seconds": round(getattr(info, "duration", 0.0), 1),
                            "rtf": round(dur / max(1e-6, getattr(info, "duration", 1.0)), 4)}
    print("转写：%d 段 / %.1fs（RTF %.3f）→ %s" % (
        len(segs), dur, report["transcribe"]["rtf"], srt_path))
    seg_dicts = [{"start": float(s.start), "end": float(s.end),
                  "text": str(s.text).strip()} for s in segs]
    # 幻觉探测（只报不改）——必须在**对齐前**可见，否则错位会静默传到下游
    rows = report_suspects(seg_dicts, args, report)
    # 可疑点重识别（默认开；`--patch-pad 0` 关闭）——同进程 + **复用模型实例**（省加载、避免显存翻倍）
    if args.patch_pad > 0:
        stage_patch(args, report, seg_dicts, rows, model=model,
                    decisions_path=args.patch_decisions)
    return srt_path


def stage_align(args, report, srt_path):
    """wav2vec2 强制对齐 → words.json（保留未对齐词占位）"""
    _require("whisperx", "安装见设计文档 §6.2（含 ctranslate2 --no-deps 升版与 transformers<5）")
    import whisperx
    import torch

    if not srt_path or not os.path.exists(srt_path):
        sys.exit("❌ 对齐需要 segments.srt（先跑 --stage transcribe，或用 --text-srt 指定）")
    segments = _parse_srt(srt_path)
    for s in segments:
        s["text"] = s["text"].strip()

    t0 = time.perf_counter()
    wav = whisperx.load_audio(args.audio)
    model_a, metadata = whisperx.load_align_model(language_code=args.language, device=args.device)
    load_s = time.perf_counter() - t0
    t1 = time.perf_counter()
    aligned = whisperx.align(segments, model_a, metadata, wav, args.device,
                             return_char_alignments=False)
    align_s = time.perf_counter() - t1
    del model_a
    if args.device == "cuda":
        torch.cuda.empty_cache()

    words, n_total, n_unaligned = [], 0, 0
    for seg in aligned["segments"]:
        for w in seg.get("words") or []:
            n_total += 1
            st, en = w.get("start"), w.get("end")
            if st is None or en is None:
                # ⚠️ 保留占位（不丢弃！）——由骨架构建器插值补齐，防“空洞伪边界”
                words.append({"start": None, "end": None, "text": w.get("word", ""), "score": None})
                n_unaligned += 1
            else:
                words.append({"start": round(float(st), 3), "end": round(float(en), 3),
                              "text": w.get("word", ""),
                              "score": None if w.get("score") is None else round(float(w["score"]), 3)})

    gaps = [round((b["start"] - a["end"]) * 1000, 1)
            for a, b in zip(words, words[1:])
            if a["end"] is not None and b["start"] is not None]
    payload = {"meta": {
        "audio": os.path.basename(args.audio),
        "model": args.model, "device": args.device, "compute_type": args.compute_type,
        "language": args.language,
        "segments": len(segments), "n_words": len(words),
        "n_unaligned": n_unaligned,
        "timing_s": {"load_and_extract": round(load_s, 2), "align": round(align_s, 2)},
    }, "words": words}
    out_path = os.path.join(args.out, "words.json")
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)

    report["align"] = payload["meta"]
    print("对齐：%d 词（未对齐 %d，已保留占位）/ %.1fs（含音频解码 %.1fs）→ %s" % (
        len(words), n_unaligned, load_s + align_s, load_s, out_path))
    if gaps:
        gs = sorted(gaps)
        report["gap_ms_p50"] = gs[len(gs) // 2]
        print("词间间隙 p50 = %.0fms（伪间隙 baseline 取 40ms）" % gs[len(gs) // 2])
    return out_path


def main():
    ap = argparse.ArgumentParser(description="vocalign 语音采集：音频 → 词级时轴")
    ap.add_argument("audio", help="音频或视频文件（mp4/mkv 可直接解码）")
    ap.add_argument("-o", "--out", required=True, help="输出目录（<work>/vocalign/）")
    ap.add_argument("--stage", choices=("all", "transcribe", "patch", "align"), default="all",
                    help="分阶段执行（all = 转写包含 patch，再跑对齐；必须分两进程）")
    ap.add_argument("--patch-pad", type=float, default=PATCH_PAD_S,
                    help="可疑点重识别半径（秒；0 = 关闭）。实测：可疑点 6/6 全修好、"
                         "S 编号只变 3 个（全片切片变 15 个）、成本 22s；**非万灵药**"
                         "（窗口内是全新解码，可能在非可疑处引入新错）→ 必预复核 patch_report.md")
    ap.add_argument("--patch-decisions", default=None,
                    help="人工裁决表（`<窗口号>\\t<keep|revert>`；revert = 该窗口回退为全片版）。"
                         "缺省时读产物目录下的 patch_decisions.tsv（存在即用）；"
                         "窗口转写有缓存，改裁决后重跑本阶段仅需秒级重拼")
    ap.add_argument("--text-srt", default=None,
                    help="已有文本（跳过转写直接对齐；文本仍建议用 --stage transcribe 的直出）")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--device", default=DEFAULT_DEVICE)
    ap.add_argument("--compute-type", default=DEFAULT_COMPUTE)
    ap.add_argument("--language", default=DEFAULT_LANG)
    ap.add_argument("--no-cond-prev", action="store_true",
                    help="关闭前文上下文（默认开；开启时 whisper 偶发段级重复幻觉）")
    ap.add_argument("--no-repeat-ngram", type=int, default=5,
                    help="禁止重复的 n-gram 长度（默认 5，抑制 whisper 重复幻觉；0=关）")
    ap.add_argument("--hf-endpoint", default=None, help="HF 镜像（如 https://hf-mirror.com）")
    args = ap.parse_args()

    if not os.path.exists(args.audio):
        sys.exit("❌ 音频不存在：%s" % args.audio)
    os.makedirs(args.out, exist_ok=True)
    if args.hf_endpoint:
        os.environ["HF_ENDPOINT"] = args.hf_endpoint
    if not shutil.which("ffmpeg"):
        print("⚠️ PATH 中未找到 ffmpeg —— 音频解码可能失败（阶段〇 同款缺口）")

    report = {"audio": os.path.basename(args.audio), "params": {
        "model": args.model, "device": args.device, "compute_type": args.compute_type,
        "language": args.language,
        # 转录口径入报告：重复幻觉归因必须先知道当时开没开这两项（否则无法复现）
        "condition_on_previous_text": not args.no_cond_prev,
        "no_repeat_ngram_size": args.no_repeat_ngram,
        "patch_pad_s": args.patch_pad}}

    def _align_text():
        """对齐用哪份文本：显式指定 > 拼接稿（存在即用，并明示）> 全片稿"""
        if args.text_srt:
            return args.text_srt
        patched = os.path.join(args.out, "segments_patched.srt")
        if os.path.isfile(patched):
            print("ℹ️ 检测到 %s（可疑点重识别产出）→ 用它对齐；"
                  "如需全片稿：--text-srt %s"
                  % (os.path.basename(patched), os.path.join(args.out, "segments.srt")))
            return patched
        return os.path.join(args.out, "segments.srt")

    if args.stage == "transcribe":
        stage_transcribe(args, report)
    elif args.stage == "patch":
        stage_patch(args, report, decisions_path=args.patch_decisions)
    elif args.stage == "align":
        stage_align(args, report, _align_text())
    else:
        # all：**必须分两个进程**（whisperx + ctranslate2 同进程触发 cuDNN 冲突）
        base = [sys.executable, os.path.abspath(__file__), args.audio, "-o", args.out,
                "--model", args.model, "--device", args.device,
                "--compute-type", args.compute_type, "--language", args.language]
        if args.no_cond_prev:
            base += ["--no-cond-prev"]
        base += ["--no-repeat-ngram", str(args.no_repeat_ngram)]
        if args.patch_pad > 0:
            base += ["--patch-pad", str(args.patch_pad)]
        if args.patch_decisions:
            base += ["--patch-decisions", args.patch_decisions]
        if args.hf_endpoint:
            base += ["--hf-endpoint", args.hf_endpoint]
        r1 = subprocess.run(base + ["--stage", "transcribe"], env=os.environ.copy())
        if r1.returncode != 0:
            sys.exit("❌ 转写阶段失败（退出码 %d）" % r1.returncode)
        align_args = base + ["--stage", "align"]
        if args.text_srt:
            align_args += ["--text-srt", args.text_srt]
        r2 = subprocess.run(align_args, env=os.environ.copy())
        if r2.returncode != 0:
            sys.exit("❌ 对齐阶段失败（退出码 %d）" % r2.returncode)
        # 汇总两阶段的报告
        for name in ("segments.srt", "words.json"):
            p = os.path.join(args.out, name)
            if not os.path.exists(p):
                sys.exit("❌ 预期产物缺失：%s" % p)
        print("采集完成：%s" % os.path.abspath(args.out))
        return 0

    with open(os.path.join(args.out, "collect_report.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(report, ensure_ascii=False, indent=1) + "\n")
    print("报告：%s" % os.path.join(args.out, "collect_report.txt"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
