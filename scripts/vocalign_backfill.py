# -*- coding: utf-8 -*-
"""vocalign 回填组装：中文分段 + 英文按“词边界候选 + 语音权重”切分 → 双语交付稿

定位
    vocalign 工作流阶段三的**收尾环节**（纯脚本，零 LLM）。把四样东西合成交付稿：
        ① 词级时轴（`words.json`）→ 词级真实时间（切点权重的来源）
        ② 整段中文译文（`r02_results/`，整段翻译、不吃时间）
        ③ 对应关系（`align/`：`Z<n> = E<m>`，复用 reflow2 的 task-match 产物）
        ④ E 句时间（`en_timeline/`）

设计（2026-10-08 用户裁定，取代 v1 的“骨架子句边界 DP 分组”）
    v1 的候选集只有**骨架子句边界**（标点 + 净停顿 ≥250ms）→ 太窄：
      · 单子句长句（内部无标点、无 250ms 停顿）必须切时无候选可用
        （实例 `What do you think happens | when I input a pulse that's shorter...`）
      · 骨架过粗的单元（实测 10–20%）只能降级到无权重词边界
    故 v2 把候选集**放宽为全部词边界**，用两维信息选点：
      · **语音权重** —— 该词边界处的净停顿（有停顿 = 更像真实断点）
      · **标点** —— 词尾标点（天然断点）
    再按**中文段宽占比**在候选中选，使英文片长度与中文段相称。
    与 reflow2 的 `split_secondary`（全词边界 + 标点/连接词奖励）同思路，
    但奖励依据换成**语音停顿证据**（reflow2 拿不到语音）。

    v3（2026-10-08）接入 **LLM 语义候选点**（`vocalign_candidates.py` 的 norm 产物）：
      候选集放宽为全词边界后，仍有“子句内部无标点、无停顿”但**必须切**的位置
      （实例 S32：单子句 18 词 `What do you think happens | when I input a pulse …`）——
      这类位置只能靠语义判断 → 候选点进惩罚阶梯（**位于标点/长停顿之下、短停顿之上**）。
      ⚠️ 实测教训：候选点**不可与标点同级**——候选是“宁多勿少”的集合，同级时 DP 会用它
      挤掉标点（实测标点结尾率 43.5%→38.0%、停顿证据率 58.1%→51.2%，全线下滑）。

中文分段（v1 的两个 bug 已修）
    v1 的贪心合并会“跨句合并”（把下一句开头吸进本段，实测 7% 段内含句号）
    且超软限率偏高（34.3% vs reflow2 的 25.9%）。v2 改为 **只拆不合**（与 reflow2 同模型）：
      · 按句末标点切 Z 句 → 每句为一段
      · 超硬限的 Z 句用 `srt_reflow_core.punct.split_units`（断点强度代价 DP）拆子段

输入 / 输出
    --words      词级时轴（words.json）
    --r02        整段中文译文目录（r02_results/）
    --align      `Z<n> = E<m>` 对应文件目录（task-match 产物）
    --etimeline  E 句时间目录
    --chunks     分块目录（含 OWNED cue 范围）
    --srt        01_subtitle_asr_fixed.srt
    --candidates 语义候选点目录（`vocalign_candidates.py norm` 产物；缺省 = 纯语音权重）
    -o           输出 r04_draft.srt / r04_bilingual.srt / r04_alerts.md

用法（命令根 = Project_Main/）
    python scripts/vocalign_backfill.py --words <work>/vocalign/words.json \\
        --r02 <work>/vocalign/r02_results --align <align> --etimeline <en_timeline> \\
        --chunks <work>/vocalign/chunks --srt <work>/01_subtitle_asr_fixed.srt \\
        --candidates <work>/vocalign/candidates -o <work>/vocalign

退出码：0 = 完成；1 = 有校验失败（片数 / 拼接 / 时间倒挂）。
"""
import argparse
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

from shared.srt_common import (text_width, SOFT_MIN, SOFT_MAX, HARD_MAX, MIN_UNIT,
                               collect_chunk_files, fmt)

PM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PM not in sys.path:
    sys.path.insert(0, PM)
from scripts.srt_reflow_core.punct import (split_units, build_profile,  # noqa: E402
                                          DANGLING_AFTER, DANGLING_PULLBACK)

# ---- 切点权重（vocalign 特有：语音停顿作惩罚基线，与 reflow2 的标点/连接词奖励同量级）----
BASELINE_MS = 40.0            # 伪间隙 baseline（与 vocalign_skeleton 同源）
SENT_PAUSE_MS = 500.0         # 长停顿 → 强切点（无惩罚）
CLAUSE_PAUSE_MS = 250.0       # 短停顿 → 弱切点（轻罚）
PENALTY_CANDIDATE = 60.0      # LLM 语义候选点切点惩罚（**参数扫描甜点**，见下方注释）
PENALTY_SHORT_PAUSE = 20.0    # 短停顿切点惩罚
PENALTY_NO_EVIDENCE = 200.0   # 无标点且无停顿的切点惩罚（语义优先、比例次要）
MIN_PIECE_CHARS = 15.0        # 英文片目标宽下限（防极短段：段时长过短）
MIN_PIECE_MS = 1000.0         # 英文片**最短时长**（与 reflow2 的 MIN_FRAG_MS 同值；防 0.1s 极短段）
PENALTY_SHORT_PIECE = 50.0    # 片时长短于下限的惩罚（软约束：可违但不可取）

TRIM = set(".,;:!?\u2014\u2013\"')]")
SRT_TIME = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})")
Z_KEY = re.compile(r"Z(\d+)")
S_KEY = re.compile(r"S(\d+)")


def split_punct(tok):
    t = tok.strip()
    i = len(t)
    while i > 0 and t[i - 1] in TRIM:
        i -= 1
    return t[:i], t[i:]


def render(words):
    """词序列 → 文本（标点紧贴前词，词间单空格）"""
    out = ""
    for w in words:
        piece = w["stem"] + w["punct"]
        out = piece if not out else out + " " + piece
    return out


def to_sec(g):
    return int(g[0]) * 3600 + int(g[1]) * 60 + int(g[2]) + int(g[3].ljust(3, "0")) / 1000.0


# ---------------------------------------------------------------- 中文分段

def segment_zh(zh_text, hard_max=HARD_MAX, soft_min=SOFT_MIN, soft_max=SOFT_MAX,
               min_unit=MIN_UNIT, profile=None):
    """中文分段 = **只拆不合**：按句末标点切 Z 句，超硬限的句用断点强度 DP 拆子段

    返回 [(文本, 宽度)]。不跨句合并 —— v1 的贪心合并会把下一句开头吸进本段，
    使句号落在段中（实测 7%），且超软限率偏高。
    """
    from srt_reflow_presplit import split_zh
    prof = profile or build_profile("zh")
    out = []
    for z in split_zh(zh_text.strip(), prof):
        if not z:
            continue
        wid = text_width(z)
        if wid <= hard_max:
            out.append((z, wid))
        else:
            for t, w in split_units(z, lang="zh", hard_max=hard_max, min_unit=min_unit,
                                    soft_min=soft_min, soft_max=soft_max, profile=prof):
                out.append((t, w))
    return out


# ---------------------------------------------------------------- 英文切分

def load_words_index(words_path):
    """词级时轴 → 词序列

    ⚠️ **必须保留未对齐词**（时间不详但文本不能丢）：whisperX 约 2.6% 词对齐失败，
    实测几乎全是数字（`15.` / `3` / `8, 8`）。若丢弃，英文行会出现缺词
    （实测 `going from 1 to 15` → 显示 "going from to"）。
    未对齐词的时间按前后锚点插值 —— 仅影响切点位置候选，不影响文本完整性。
    """
    with open(words_path, encoding="utf-8") as fh:
        data = json.load(fh)
    raw = []
    for w in data["words"]:
        stem, punct = split_punct(w["text"])
        if not stem and not punct:
            continue
        st, en = w.get("start"), w.get("end")
        raw.append({"stem": stem, "punct": punct,
                    "start": None if st is None else float(st),
                    "end": None if en is None else float(en)})
    n, i = len(raw), 0
    while i < n:
        if raw[i]["start"] is not None:
            i += 1
            continue
        j = i
        while j < n and raw[j]["start"] is None:
            j += 1
        k = j - i
        left = raw[i - 1]["end"] if i > 0 and raw[i - 1]["end"] is not None else None
        right = raw[j]["start"] if j < n and raw[j]["start"] is not None else None
        if left is not None and right is not None and right > left:
            step = (right - left) / k
        elif left is not None:
            step = 0.12
        elif right is not None:
            left, step = right - 0.12 * k, 0.12
        else:
            left, step = 0.0, 0.12
        for m in range(k):
            raw[i + m]["start"] = round(left + step * m, 3)
            raw[i + m]["end"] = round(left + step * (m + 1), 3)
        i = j
    return raw


def words_in_range(toks, t0, t1, tol=0.15):
    """取时间范围内的词区间 [i, j)

    容差宜小（默认 0.15s）：E 句时间是 cue 时间（01 字幕），与词级时间基本同基
    （实测 reflow2 切点离词边界中位仅 6ms）；容差过大会把相邻 E 句的词一并取入
    （实测 0.6s 时英文行多出上句尾巴 `they exist.`）。
    """
    idx = [k for k, t in enumerate(toks) if t0 - tol <= t["start"] <= t1 + tol]
    return (idx[0], idx[-1] + 1) if idx else None


def cut_reason(words, i, cand=None):
    """切点的**证据来源**：punct / sent-pause / candidate / clause-pause / none

    既供 `cut_cost` 定惩罚，也是**验收统计口径**（两稿对照必须同一口径 —— 踩坑清单 §7.3 第 10 条）。
    `cand` = 候选点集合，键为**切点左侧词的索引**（与 `vocalign_candidates.py` norm 产物同口径）。
    """
    if i <= 0 or i >= len(words):
        return "edge"
    a, b = words[i - 1], words[i]
    if a["punct"]:
        return "punct"                      # 词尾标点：天然断点
    net = (b["start"] - a["end"]) * 1000.0 - BASELINE_MS
    if net >= SENT_PAUSE_MS:
        return "sent-pause"                 # 长停顿（净 ≥500ms）：强语音证据
    if cand and (i - 1) in cand:
        return "candidate"                  # LLM 语义候选点（语义证据，弱于标点/长停顿）
    if net >= CLAUSE_PAUSE_MS:
        return "clause-pause"               # 短停顿（250–500ms）：弱语音证据，轻罚
    return "none"                           # 无任何证据：重罚


# 惩罚阶梯（**值越小越优先**）：标点 0 = 长停顿 0 ＜ 短停顿 20 ＜ 候选点 60 ＜ 无证据 200
# （**必须用惩罚不用奖励**：奖励 10 会被宽度偏差代价淹没 —— 实测停顿证据率 92%→17%）
# ⚠️ 候选点的值 = **权衡旋钮**（`--penalty-candidate`）——参数扫描（PRR 2，模拟候选 164 个）：
#     无候选    punct 51 / none 16 / 标点结尾率 43.5% / 停顿证据率 58.1%
#     0（同级）  punct 39 / none  8 / 38.0% / 51.2%   ← 候选点挤掉标点，全线下滑
#     15        punct 43 / none  8 / 39.8% / 52.6%
#     60 ★甜点   punct 51 / none  6 / 43.5% / 57.2%   ← 标点零损失 + 乱切减 62.5%
#     150       punct 56 / none  8 / 45.8% / 57.7%
#   故默认 60：**标点不受损**、乱切大幅减少。
COST_BY_REASON = {"punct": 0.0, "sent-pause": 0.0, "clause-pause": PENALTY_SHORT_PAUSE,
                  "none": PENALTY_NO_EVIDENCE}


def cut_cost(words, i, cand=None, pen_cand=None):
    """在第 i 个词之后切（i ∈ 1..m-1；i = 切点**右侧**词索引 → 左侧词索引 = i-1）的惩罚

    用惩罚而非奖励（2026-10-08 实测教训）：奖励（10）远小于宽度偏差代价（可达几十）
    → DP 会选“宽度精确但无语音证据”的切点（实测停顿证据率从 92% 掉到 17%）。
    改为惩罚后，无证据切点只在“宽度偏差 > 40 字符”时才值得。
    """
    r = cut_reason(words, i, cand)
    if r == "candidate":
        return PENALTY_CANDIDATE if pen_cand is None else pen_cand
    return COST_BY_REASON.get(r, 0.0)


def pullback_dangling(words, groups, max_pull=DANGLING_PULLBACK):
    """悬空回拉：切点前一词若为功能词（介词/冠词/连词/助动词），把该词归**后**片

    复用 reflow2 的句法原则（`srt_reflow_core.punct.DANGLING_AFTER`）——“功能词与其依赖
    成分同侧”。reflow2 把它做成 `split_secondary` 层的**统一后处理**（实测悬空切点
    13.2% → 3.1%）；vocalign 的切点由 DP 给出，同样需要这层后处理。

    必须做成后处理而非 DP 内的软惩罚：切点变化会改变后续切点的可行域。
    """
    if len(groups) < 2:
        return groups
    bounds = [b for _a, b in groups[:-1]]
    for _ in range(max_pull):
        changed = False
        for gi in range(len(bounds)):
            b = bounds[gi]
            a = groups[gi][0] if gi == 0 else bounds[gi - 1]
            prev = words[b - 1]
            w = re.sub(r"[^A-Za-z']", "", prev["stem"]).lower()
            if w in DANGLING_AFTER and b - a > 1:      # 前片至少留 1 词
                bounds[gi] -= 1
                changed = True
        if not changed:
            break
    out, prev = [], 0
    for b in bounds:
        out.append((prev, b))
        prev = b
    out.append((prev, len(words)))
    return out


def dp_split_words(words, targets, cand=None, pen_cand=None,
                   min_ms=MIN_PIECE_MS, pen_short=PENALTY_SHORT_PIECE):
    """词序列 → len(targets) 组：最小化“片宽偏差 + 切点惩罚 + 极短片惩罚”

    代价 = Σ|片宽 − 目标宽| + Σ切点惩罚 + Σ极短片惩罚。惩罚让 DP 避开无证据处，
    偏差项让片长贴合中文段宽占比。二者同量级（字符数），故“为拿到 200 的惩罚减免，
    可接受 200 字符的宽度偏差”。
    `cand` = 候选点集合（**相对于本段 words 的左侧词索引**）；
    `min_ms` / `pen_short` = 片**时长**下限（防 0.1s 极短段：中文二字疑问句可短到 0.1s）与违反惩罚。
    返回 [(i, j)] 或 None（词数不足）。
    """
    m, k = len(words), len(targets)
    if m < k:
        return None
    cum = [0.0]
    for w in words:
        cum.append(cum[-1] + len(w["stem"]) + len(w["punct"]) + (1 if (w["stem"] or w["punct"]) else 0))
    bonus = [0.0] * (m + 1)
    for i in range(1, m):
        bonus[i] = cut_cost(words, i, cand, pen_cand)
    INF = float("inf")
    dp = [[INF] * (k + 1) for _ in range(m + 1)]
    par = [[-1] * (k + 1) for _ in range(m + 1)]
    dp[0][0] = 0.0
    for g in range(1, k + 1):
        for j in range(g, m + 1):
            for i in range(g - 1, j):
                if dp[i][g - 1] == INF:
                    continue
                cost = dp[i][g - 1] + abs((cum[j] - cum[i]) - targets[g - 1])
                if i > 0:
                    cost += bonus[i]          # 切点质量惩罚（第 i 词后切）
                if pen_short and (words[j - 1]["end"] - words[i]["start"]) * 1000.0 < min_ms:
                    cost += pen_short          # 极短片惩罚（0.1s 级段不可取）
                if cost < dp[j][g]:
                    dp[j][g] = cost
                    par[j][g] = i
    if dp[m][k] == INF:
        return None
    groups, j, g = [], m, k
    while g > 0:
        i = par[j][g]
        groups.append((i, j))
        j, g = i, g - 1
    return list(reversed(groups))


# ---------------------------------------------------------------- 对应关系

def load_align(align_dir):
    """`Z<n> = S<m>`（含 `Z1+Z2 = S3` / `Z1 = S2+S3`）→ {块号: {Z 号: [S 号]}}

    ⚠️ **Z 号是块内局部编号、跨块重复**（chunk_001 与 chunk_002 都有 Z1）——
    必须按块分装，否则后块会覆盖前块（静默错配）。
    ✅ **S 号是全局编号**（与 reflow2 的 E 号不同）→ S 时间无需按块分装（见 `load_stimes`）。
    """
    out = {}
    for fn in sorted(os.listdir(align_dir)):
        if not fn.endswith(".txt"):
            continue
        mc = re.search(r"chunk_(\d+)", fn)
        k = int(mc.group(1)) if mc else 0
        per = out.setdefault(k, {})
        with open(os.path.join(align_dir, fn), encoding="utf-8-sig") as fh:
            for ln in fh:
                if "=" not in ln:
                    continue
                left, right = ln.split("=", 1)
                zs = [int(x) for x in Z_KEY.findall(left)]
                ss = [int(x) for x in S_KEY.findall(right)]
                if zs and ss:
                    if len(zs) == 1:
                        per[zs[0]] = ss
                    else:                       # 组合：把 S 组摊到各 Z（少见）
                        for z in zs:
                            per[z] = ss
    return out


def load_candidates(cand_dir):
    """候选点目录 → {全局词号: 「S<n>」}（`vocalign_candidates.py norm` 产物 `chunk_<k>.tsv`）

    全局词号 = 切点**左侧词**在 `words.json` 的 `words[]` 下标（0-based，语义“在该词之后切”）。
    跨块合并：块号只是**派发单位**，候选点全局有效（回填按 E 组时间取词，与块划分无关）。
    """
    if not os.path.isdir(cand_dir):
        sys.exit("❌ --candidates 目录不存在：%s" % cand_dir)
    out = {}
    for fn in sorted(os.listdir(cand_dir)):
        if not re.fullmatch(r"chunk_\d{3}\.tsv", fn):
            continue
        with open(os.path.join(cand_dir, fn), encoding="utf-8-sig") as fh:
            for ln in fh:
                if ln.startswith("#") or not ln.strip():
                    continue
                parts = ln.rstrip("\n").split("\t")
                if len(parts) < 2:
                    continue
                for g in parts[1].split(","):
                    if g.strip().lstrip("-").isdigit():
                        out[int(g)] = parts[0]
    return out


def load_stimes(e0_dir=None, srt_path=None):
    """S 长句时间 → {S 号(int): (start, end)}

    数据源（优先前者）：
      · `<e0>/long_lines.srt`（E0 的 SRT 载体；cue 号 ≡ S 号）
      · 或直接给一份等价 SRT（如用户自己指定）

    ✅ **S 号是全局编号** → 无需按块分装（相对 reflow2 的 E 号坑的简化）。
    """
    path = srt_path or (os.path.join(e0_dir, "long_lines.srt") if e0_dir else None)
    if not path or not os.path.isfile(path):
        sys.exit("❌ 找不到 E0 载体（long_lines.srt）：%s" % path)
    out = {}
    raw = open(path, encoding="utf-8-sig").read()
    for block in re.split(r"\n\s*\n", raw.strip()):
        lines = [x.strip() for x in block.split("\n") if x.strip()]
        ti = next((i for i, ln in enumerate(lines) if SRT_TIME.search(ln)), None)
        if ti is None:
            continue
        m = SRT_TIME.search(lines[ti])
        try:
            idx = int(lines[0])
        except ValueError:
            continue
        out[idx] = (to_sec(m.groups()[:4]), to_sec(m.groups()[4:]))
    if not out:
        sys.exit("❌ E0 载体未解析出任何 S 长句：%s" % path)
    return out


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(description="vocalign 回填组装（词边界候选 + 语音权重）")
    ap.add_argument("--words", required=True, help="词级时轴 words.json")
    ap.add_argument("--r02", required=True, help="整段中文译文目录")
    ap.add_argument("--align", required=True, help="`Z<n> = S<m>` 对应目录（task-match 产物，vocalign 自产）")
    ap.add_argument("--e0", required=True, help="E0 目录（读 long_lines.srt 取 S 长句时间）")
    ap.add_argument("--stime-srt", default=None, help="自定义 S 时间 SRT（覆盖 --e0 的 long_lines.srt）")
    ap.add_argument("--chunks", required=True, help="分块目录（贡献块号集合；与 r02_results 取交集）")
    ap.add_argument("--candidates", default=None,
                    help="语义候选点目录（vocalign_candidates.py norm 产物；缺省 = 纯语音权重）")
    ap.add_argument("--penalty-candidate", type=float, default=PENALTY_CANDIDATE,
                    help="候选点切点惩罚（默认 60；调小 → 多修乱切但多挤标点；调大 → 保护标点）")
    ap.add_argument("-o", "--out", required=True, help="输出目录")
    ap.add_argument("--order", choices=("zh-en", "en-zh"), default="zh-en", help="双语行序")
    ap.add_argument("--soft-max", type=float, default=SOFT_MAX, help="中文段宽软限（默认 22）")
    ap.add_argument("--hard-max", type=float, default=HARD_MAX, help="中文段宽硬限（默认 27）")
    ap.add_argument("--expand", action="store_true", help="展开打印明细")
    args = ap.parse_args()

    toks = load_words_index(args.words)
    if not toks:
        sys.exit("❌ 词级时轴无可用的对齐词")
    prof = build_profile("zh")
    align = load_align(args.align)
    stime = load_stimes(args.e0, args.stime_srt)
    if not align:
        sys.exit("❌ align 目录无有效对应：%s" % args.align)
    cand = load_candidates(args.candidates) if args.candidates else {}
    if args.candidates and not cand:
        print("⚠️ --candidates 目录内无有效候选点（检查 norm 是否已跑）：%s" % args.candidates)

    chunk_files = collect_chunk_files(args.chunks)
    r02_files = collect_chunk_files(args.r02)
    keys = sorted(set(chunk_files) & set(r02_files))
    if not keys:
        sys.exit("❌ chunks 与 r02_results 无共同块号")

    os.makedirs(args.out, exist_ok=True)
    zh_out, bi_out, alerts, fails = [], [], [], []
    n_no_align = 0
    src_count, n_cand_used, no_evid = {}, 0, []

    for k in keys:
        with open(r02_files[k], encoding="utf-8") as fh:
            zh_text = fh.read().strip()
        from srt_reflow_presplit import split_zh
        z_sents = split_zh(zh_text, prof)

        # 建立“中文子段 → Z 号”映射（Z 号 = 块内局部序号，与 align 同源）
        seg_to_z = []
        zi = 0
        for z in z_sents:
            if not z:
                continue
            zi += 1
            sub = split_units(z, lang="zh", hard_max=args.hard_max, min_unit=MIN_UNIT,
                              soft_min=SOFT_MIN, soft_max=args.soft_max, profile=prof)
            if not sub:
                sub = [(z, text_width(z))]
            for s in sub:
                seg_to_z.append((s[0], s[1], zi))

        # 按 align 的 S 组聚簇：多个 Z 共享同一 S 组（`Z1+Z2 = S1`）时必须合并处理，
        # 否则两个 Z 都会占用同一段时间 → 时间倒挂 / 内容重复
        clusters, cidx = [], {}
        for zh_seg, zh_w, zno in seg_to_z:
            ss = align.get(k, {}).get(zno)
            if not ss:
                n_no_align += 1
                alerts.append("⚠️ 块 %s：Z%d 无对应（align 缺失）" % (k, zno))
                continue
            key = tuple(ss)
            if key not in cidx:
                cidx[key] = len(clusters)
                clusters.append([ss, []])
            clusters[cidx[key]][1].append((zh_seg, zh_w, zno))

        # 按 S 号递增排序（单调钳制依赖此顺序）；同组保持 Z 序
        clusters.sort(key=lambda c: min(c[0]) if c[0] else 0)
        prev_end = None                      # 上一个 S 组的词范围终点（单调钳制用）
        for ss, sibs in clusters:
            sts = [stime.get(s) for s in ss]
            sts = [x for x in sts if x]
            if not sts:
                alerts.append("⚠️ 块 %s：S 组 %s 无时间（E0 载体缺该长句）" % (k, ss))
                continue
            t0, t1 = min(x[0] for x in sts), max(x[1] for x in sts)
            rng = words_in_range(toks, t0, t1)
            if not rng:
                alerts.append("⚠️ 块 %s：S 组 %s 时间范围 %.2f–%.2f 内无词" % (k, ss, t0, t1))
                continue
            # 单调钳制：`words_in_range` 的 ±0.15s 容差会让**相邻组各多取同一个词**
            # → 上组末词 = 下组首词 → 片时间倒挂（实测 60ms 级）。按 S 号递增顺序钳制。
            if prev_end is not None and rng[0] < prev_end:
                if prev_end >= rng[1]:
                    alerts.append("⚠️ 块 %s：S 组 %s 的词范围被前组吃掉（无可用词）" % (k, ss))
                    continue
                rng = (prev_end, rng[1])
            prev_end = rng[1]
            wslice = toks[rng[0]:rng[1]]
            if len(sibs) == 1:
                groups = [(0, len(wslice))]
            else:
                # 中文段宽占比 → 英文词序列的目标片宽（带下限，防极短段）
                tot_zh = sum(w for _t, w, _z in sibs) or 1.0
                tot_en = sum(len(w["stem"]) + len(w["punct"]) + 1 for w in wslice) or 1.0
                targets = [max(MIN_PIECE_CHARS, tot_en * (w / tot_zh)) for _t, w, _z in sibs]
                # 候选点是**全局词号**（跨块有效）→ 换算成 wslice 内的相对索引
                local = {g - rng[0] for g in cand if rng[0] <= g < rng[1]}
                groups = dp_split_words(wslice, targets, cand=local,
                                        pen_cand=args.penalty_candidate)
                if groups is None:
                    # 词数 < 中文段数：按词索引**等分**为 k 组（可能含空组）——
                    # ⚠️ 不可整体合并（旧写法 groups=[(0,m)] 会让多余中文段拿到整段时间 → **时间重叠**）
                    alerts.append("⚠️ 块 %s：S 组 %s 词数 %d < 中文段数 %d → 按索引等分（部分英文行为空）"
                                  % (k, ss, len(wslice), len(sibs)))
                    nw, ng = len(wslice), len(sibs)
                    groups = [(int(round(nw * gi / ng)), int(round(nw * (gi + 1) / ng)))
                              for gi in range(ng)]
                else:
                    groups = pullback_dangling(wslice, groups)
                    # 切点验收统计（证据来源 + 候选点采用；必须在回拉后统计）
                    for gi in range(len(groups) - 1):
                        b = groups[gi][1]
                        why = cut_reason(wslice, b, local)
                        src_count[why] = src_count.get(why, 0) + 1
                        if b - 1 in local:
                            n_cand_used += 1
                        if why == "none":
                            no_evid.append("块 %s S组 %s：词 %d“%s”|“%s”无证据切点" % (
                                k, "+".join("S%d" % e for e in ss), rng[0] + b - 1,
                                wslice[b - 1]["stem"] + wslice[b - 1]["punct"],
                                wslice[b]["stem"] + wslice[b]["punct"]))
            for si, (seg_text, seg_w, zno) in enumerate(sibs):
                if si < len(groups):
                    a, b = groups[si]
                    gw = wslice[a:b]
                    if gw:
                        st, en, en_text = gw[0]["start"], gw[-1]["end"], render(gw)
                    else:
                        # 空片（词数不足时的等分结果）：零宽时间点，避免与相邻段重叠
                        st = en = (wslice[a - 1]["end"] if a > 0 else t0)
                        en_text = ""
                else:
                    st, en, en_text = t0, t1, ""
                zh_out.append({"start": st, "end": en, "text": seg_text, "z": zno})
                bi_out.append({"start": st, "end": en, "zh": seg_text, "en": en_text, "z": zno})

    def src_summary():
        return " / ".join("%s %d" % (kk, vv) for kk, vv in sorted(src_count.items())) or "无"

    def enforce_min_duration(rows, min_ms=MIN_PIECE_MS):
        """时间下限兜底：段时长 < 下限时先**向后借空隙**（延长 end）、不足再**向前借**（提前 start）

        只借空隙、不改切点、不改相邻段边界 —— 不违背“时间取语音实测”的原则。
        两侧都被相邻段顶住（无空隙可借）时保持原样，并在告警中列出。
        """
        n_fix = 0
        for i, r in enumerate(rows):
            need = min_ms / 1000.0 - (r["end"] - r["start"])
            if need <= 1e-6:
                continue
            fixed = False
            hi = rows[i + 1]["start"] if i + 1 < len(rows) else r["start"] + need
            back = min(need, hi - r["end"])
            if back > 1e-6:
                r["end"] += back
                need -= back
                fixed = True
            if need > 1e-6:
                lo = rows[i - 1]["end"] if i > 0 else max(0.0, r["start"] - need)
                fwd = min(need, r["start"] - lo)
                if fwd > 1e-6:
                    r["start"] -= fwd
                    fixed = True
            if fixed:
                n_fix += 1
        return n_fix

    n_short = sum(1 for r in zh_out if (r["end"] - r["start"]) * 1000.0 < MIN_PIECE_MS)
    n_fix = enforce_min_duration(zh_out)
    enforce_min_duration(bi_out)
    if n_short:
        alerts.append("⚠️ 段时长 < %.0fms：%d 处（其中 %d 处已用后续空隙延长，余者相邻段紧邻无空隙可借）"
                      % (MIN_PIECE_MS, n_short, n_fix))

    for i in range(1, len(zh_out)):
        if zh_out[i]["start"] < zh_out[i - 1]["start"] - 0.05:
            fails.append("时间倒挂：第 %d 段起 %.3fs < 前段 %.3fs" % (
                i + 1, zh_out[i]["start"], zh_out[i - 1]["start"]))
    for r in bi_out:
        if not r["zh"].strip():
            fails.append("空中文段（Z%d）" % r["z"])

    def write_srt(path, rows, bilingual):
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            for i, r in enumerate(rows, 1):
                fh.write("%d\n%s --> %s\n" % (
                    i, fmt(int(round(r["start"] * 1000))), fmt(int(round(r["end"] * 1000)))))
                if bilingual:
                    fh.write((r["zh"] + "\n" + r["en"]) if args.order == "zh-en"
                             else (r["en"] + "\n" + r["zh"]))
                    fh.write("\n\n")
                else:
                    fh.write(r["text"] + "\n\n")

    write_srt(os.path.join(args.out, "r04_draft.srt"), zh_out, False)
    write_srt(os.path.join(args.out, "r04_bilingual.srt"), bi_out, True)

    with open(os.path.join(args.out, "r04_alerts.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# vocalign 回填告警\n\n")
        fh.write("- 块数 %d；中文段 %d；Z 句无对应 %d\n" % (len(keys), len(zh_out), n_no_align))
        fh.write("- 切点来源：%s（候选点采用 %d）\n" % (src_summary(), n_cand_used))
        fh.write("- 语义候选点：%s\n" % ("目录 %s，共 %d 个" % (args.candidates, len(cand))
                                      if cand else "未启用（纯语音权重）"))
        if no_evid:
            fh.write("\n## 无证据切点（%d 处；加语义候选点环节应能消除）\n\n" % len(no_evid))
            for s in no_evid[:200]:
                fh.write("- %s\n" % s)
        if alerts:
            fh.write("\n## 告警\n\n")
            for a in alerts[:200]:
                fh.write("- %s\n" % a)
        if fails:
            fh.write("\n## 校验失败\n\n")
            for f in fails[:200]:
                fh.write("- ⛔ %s\n" % f)

    print("vocalign 回填：块 %d / 中文段 %d / Z 无对应 %d" % (len(keys), len(zh_out), n_no_align))
    print("切点来源：%s（候选点采用 %d）" % (src_summary(), n_cand_used))
    if no_evid:
        print("⚠️ 无证据切点 %d 处（详见 r04_alerts.md）" % len(no_evid))
    if alerts:
        print("告警 %d 项%s" % (len(alerts), "" if args.expand else "（--expand 展开）"))
        if args.expand:
            for a in alerts[:30]:
                print("   " + a)
    if fails:
        print("❌ 校验失败 %d 项：" % len(fails))
        for f in fails[:10]:
            print("   " + f)
        return 1
    print("产物：%s" % os.path.abspath(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
