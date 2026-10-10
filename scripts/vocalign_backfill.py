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
    --align      `Z<n> = S<m>` 对应目录（task-match 产物；vocalign 自产）
    --e0         E0 目录（读 long_lines.srt 取 S 长句时间）
    --chunks     分块目录（含 OWNED cue 范围）
    --candidates 语义候选点目录（`vocalign_candidates.py norm` 产物；缺省 = 纯语音权重）
    --fix-splits 定点修复清单（处置超宽片；缺省 = 不启用）
    -o           输出 r04_draft.srt / r04_bilingual.srt / r04_alerts.md

用法（命令根 = Project_Main/）
    python scripts/vocalign_backfill.py --words <work>/vocalign/words.json \\
        --r02 <work>/vocalign/r02_results --align <work>/vocalign/align \\
        --e0 <work>/vocalign/e0 --chunks <work>/vocalign/chunks \\
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
from scripts.srt_reflow_core.punct import (split_units, build_profile)  # noqa: E402

# ---- 切点权重（vocalign 特有：语音停顿作惩罚基线，与 reflow2 的标点/连接词奖励同量级）----
BASELINE_MS = 40.0            # 伪间隙 baseline（与 vocalign_skeleton 同源）
SENT_PAUSE_MS = 500.0         # 长停顿 → 强切点（无惩罚）
CLAUSE_PAUSE_MS = 250.0       # 短停顿 → 弱切点（轻罚）
PENALTY_CANDIDATE = 60.0      # LLM 语义候选点切点惩罚（**参数扫描甜点**，见下方注释）
PENALTY_SHORT_PAUSE = 20.0    # 短停顿切点惩罚
PENALTY_NO_EVIDENCE = 200.0   # 无标点且无停顿的切点惩罚（语义优先、比例次要）
MIN_PIECE_CHARS = 15.0        # 英文片目标宽下限（防极短段：段时长过短）
OVER_WIDE_RATIO = 2.0         # 英文片宽 / 中文段宽 超此倍率 = 比例失衡（缺候选点）
                              # 实测比值分布 p50 1.47 / p75 1.67 / p90 1.87 / p95 2.02 / max 3.35
LOWCONF_SCORE = 0.30          # 词对齐置信度低于此值 = 对齐可疑
LOWCONF_WINDOW = 2            # 查边界前后各几个词的对齐置信度（假空隙判据）
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
                    "end": None if en is None else float(en),
                    "score": w.get("score"),        # 对齐置信度（假空隙判据用）
                    "src": "real" if st is not None else None})
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
            raw[i + m]["src"] = "interp"          # 插值词：时间非实测（数字类）
        i = j
    return raw


def words_in_range(toks, t0, t1, tol=0.15):
    """取时间范围内的词区间 [i, j)

    容差宜小（默认 0.15s）：E 句时间是 cue 时间（01 字幕），与词级时间基本同基
    （实测 reflow2 切点离词边界中位仅 6ms）；容差过大会把相邻 E 句的词一并取入
    （实测 0.6s 时英文行多出上句尾巴 `they exist.`）。

    ⚠️ 容差施加于上下界都会越界：插值词的 `end` 被拉满到**下一词 start**（实测
    `15.` end = `So` start = 101.773）→ 下一词也满足 `start <= t1 + tol`。故调用方
    必须用 `hard_split_ranges` 做**双向钳制**（本函数只负责“按时间圈词”）。
    """
    idx = [k for k, t in enumerate(toks) if t0 - tol <= t["start"] <= t1 + tol]
    return (idx[0], idx[-1] + 1) if idx else None


def first_real_index(toks, lo, hi):
    """`[lo, hi)` 内第一个**实测**词（非 interp/synth）的 index；无则返 -1

    用于两组之间的硬分界：分界取**后组首个实测词**→ 其间夹着的插值词归前组末尾
    （它们本就是前句末尾的数字类未对齐词，时间由前词锚点插值而来）。
    """
    for k in range(lo, min(hi, len(toks))):
        if toks[k].get("src") == "real":
            return k
    return -1


def hard_split_ranges(toks, ranges):
    """把相邻组的词范围切成**互不重叠**（返回新列表；不可切的保持原样）

    为何必须双向：命中未对齐词（数字）时其 `end` 由插值拉满到下一词 start，±0.15s
    容差就把**下一句首词**圈进本组 → 本组末词被替换为下一句首词 → 单向钳制把这个
    错值向下传递（实测 S19 组末词变 `repeater`，S20 片起点落后 683ms）。
    分界取后组首个实测词：前组末词保持为它真正的末词。
    """
    out = list(ranges)
    for i in range(1, len(out)):
        a, b = out[i - 1], out[i]
        if a is None or b is None or b[0] >= a[1]:
            continue                         # 无重叠
        cut = first_real_index(toks, b[0], min(b[1], a[1]))
        if cut <= a[0]:                      # 后组在重叠区内无实测词可作分界
            cut = b[0]                       # 退一步：按下界切
        out[i - 1] = (a[0], cut)
        out[i] = (cut, b[1])
    return out


def _low_conf(words, i, thr=LOWCONF_SCORE, win=LOWCONF_WINDOW):
    """切点 `i` 附近是否存在**对齐可疑**的词（score < thr）

    查证：对齐空洞的实测形态是“个别词音素对齐失败 → 该词 start 被推后 / 下一词 score 陡低
    → 中间多出一段无处安放的空隙”。实测 4 处“无标点且 gap ≥ 1s”中命中 3 处；
    第 4 处窗口内最低 score 0.539（真停顿）不命中 — 区分成立。
    """
    lo, hi = max(0, i - win), min(len(words), i + 2 + win)
    return any((words[j].get("score") or 0.0) < thr for j in range(lo, hi))


def cut_reason(words, i, cand=None, fix=None):
    """切点的**证据来源**：punct / fix / sent-pause / candidate / clause-pause / lowconf / none

    既供 `cut_cost` 定惩罚，也是**验收统计口径**（两稿对照必须同一口径 —— 踩坑清单 §7.3 第 10 条）。
    `cand` = 候选点集合，键为**切点左侧词的索引**（与 `vocalign_candidates.py` norm 产物同口径）。
    `fix` = **定点修复**切点集（同一口径），零惩罚（与标点同级，强制生效）。

    `lowconf` = **假空隙**：无标点、靠停顿当证据，但边界附近有对齐可疑的词
    （音素对齐失败所致的空隙，非真停顿）→ 不作语音证据。
    """
    if i <= 0 or i >= len(words):
        return "edge"
    a, b = words[i - 1], words[i]
    if a["punct"]:
        return "punct"                      # 词尾标点：天然断点
    if fix and (i - 1) in fix:
        return "fix"                        # 定点修复：人工/agent 指定，强制生效
    net = (b["start"] - a["end"]) * 1000.0 - BASELINE_MS
    if net >= SENT_PAUSE_MS:
        # 强停顿先过一道闸：附近有对齐可疑的词 → 空隙来自对齐失败，不当证据
        if _low_conf(words, i):
            return "lowconf"
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
COST_BY_REASON = {"punct": 0.0, "fix": 0.0, "sent-pause": 0.0,
                  "clause-pause": PENALTY_SHORT_PAUSE, "none": PENALTY_NO_EVIDENCE,
                  "lowconf": PENALTY_NO_EVIDENCE}


def cut_cost(words, i, cand=None, pen_cand=None, fix=None):
    """在第 i 个词之后切（i ∈ 1..m-1；i = 切点**右侧**词索引 → 左侧词索引 = i-1）的惩罚

    用惩罚而非奖励（2026-10-08 实测教训）：奖励（10）远小于宽度偏差代价（可达几十）
    → DP 会选“宽度精确但无语音证据”的切点（实测停顿证据率从 92% 掉到 17%）。
    改为惩罚后，无证据切点只在“宽度偏差 > 40 字符”时才值得。
    """
    r = cut_reason(words, i, cand, fix)
    if r == "candidate":
        return PENALTY_CANDIDATE if pen_cand is None else pen_cand
    return COST_BY_REASON.get(r, 0.0)


def dp_split_words(words, targets, cand=None, pen_cand=None, fix=None,
                   min_ms=MIN_PIECE_MS, pen_short=PENALTY_SHORT_PIECE):
    """词序列 → len(targets) 组：最小化“片宽偏差 + 切点惩罚 + 极短片惩罚”

    代价 = Σ|片宽 − 目标宽| + Σ切点惩罚 + Σ极短片惩罚。惩罚让 DP 避开无证据处，
    偏差项让片长贴合中文段宽占比。二者同量级（字符数），故“为拿到 200 的惩罚减免，
    可接受 200 字符的宽度偏差”。
    `cand` = 候选点集合（**相对于本段 words 的左侧词索引**）；
    `fix` = 定点修复切点集（同一口径，零惩罚 → 强制生效）；
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
        bonus[i] = cut_cost(words, i, cand, pen_cand, fix)
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


def load_fix_splits(path, toks, stimes):
    """定点修复清单 → ({全局词号(切点左侧词下标)}, [未命中条目])

    用途：**后处理兜底**。回填报“超宽英文片”（英宽 / 中宽 ≥ 阈值）后，重跑整个候选点
    环节代价高；人工/agent 只需针对出问题的那一处写一行修复，再重跑回填即可。

    格式（TSV，`|` 分隔切点两侧词，与候选点作答同形）：
        # S号	切点两侧词（左 | 右）
        S69	useful | to
    锚 = **S 号 + 相邻两词**（不用词号——词号随 E0 增删词漂移，不稳）；
    定位 = 在**该 S 时间范围内**的词序列中找该相邻词对（去标点、不区分大小写）。
    命中不唯一或未命中 → 记入未命中（**不静默**），由回填写进 `r04_alerts.md`。
    """
    fix, miss = set(), []
    if not path or not os.path.isfile(path):
        if path:
            sys.exit("❌ --fix-splits 文件不存在：%s" % path)
        return fix, miss
    with open(path, encoding="utf-8-sig") as fh:
        for ln in fh:
            if ln.startswith("#") or not ln.strip():
                continue
            parts = ln.rstrip("\n").split("\t")
            if len(parts) < 2 or "|" not in parts[1]:
                miss.append("%s（格式：`<S号>\\t<左词> | <右词>`）" % ln.strip()[:60])
                continue
            snos = [int(x) for x in S_KEY.findall(parts[0])]
            left, right = [x.strip().lower() for x in parts[1].split("|", 1)]
            if not snos:
                miss.append("%s（缺 S 号）" % ln.strip()[:60])
                continue
            rng = None
            snos_st = [stimes[s] for s in snos if s in stimes]
            if snos_st:
                # 合译组（`S94+S95`）取**并集**时间范围——否则切点落在后一个 S 内会误报未命中
                rng = words_in_range(toks, min(x[0] for x in snos_st), max(x[1] for x in snos_st))
            if not rng:
                miss.append("S%s：无时间范围（E0 载体缺该长句）" % "+".join(str(s) for s in snos))
                continue
            hits = [i for i in range(rng[0] + 1, rng[1])
                    if toks[i - 1]["stem"].lower() == left
                    and toks[i]["stem"].lower() == right]
            if len(hits) == 1:
                fix.add(hits[0] - 1)
            elif not hits:
                miss.append("S%s：范围内未找到“%s | %s”" % ("+".join(str(s) for s in snos), left, right))
            else:
                miss.append("S%s：“%s | %s”命中 %d 处（不唯一）"
                            % ("+".join(str(s) for s in snos), left, right, len(hits)))
    return fix, miss


def _piece_widths(toks, groups):
    """各片的英文视觉宽度（诊断输出用）"""
    out = []
    for a, b in groups:
        ws = toks[a:b]
        out.append(text_width(render(ws)) if ws else 0.0)
    return out


def sim_group(toks, rng, sibs_w, cand, fix, pen_cand, extra_fix=None):
    """重跑某 S 组的英文切分 DP（可额外强制一个切点）→ groups

    与回填主循环**同构**（同样的 targets 口径与候选换算），供草稿预估“若在此切，本组
    会切成什么样”。`extra_fix` = 追加切点（**切点左侧词的相对索引**，与 `fix` 同口径）。
    """
    wslice = toks[rng[0]:rng[1]]
    k = len(sibs_w)
    if k <= 1 or not wslice:
        return [(0, len(wslice))]
    tot_zh = sum(sibs_w) or 1.0
    tot_en = sum(len(w["stem"]) + len(w["punct"]) + 1 for w in wslice) or 1.0
    targets = [max(MIN_PIECE_CHARS, tot_en * (wv / tot_zh)) for wv in sibs_w]
    local = {g - rng[0] for g in cand if rng[0] <= g < rng[1]}
    lf = {g - rng[0] for g in fix if rng[0] <= g < rng[1]}
    if extra_fix is not None:
        lf = lf | {extra_fix}
    return dp_split_words(wslice, targets, cand=local, pen_cand=pen_cand, fix=lf)


DRAFT_MAX_ROWS = 8        # 草稿每处最多列几个切点（按效果排序后截断）


def over_wide_draft(over_en, bi_out, toks, cand, fix, pen_cand):
    """超宽英文片 → 待裁决草稿（Markdown 文本行）

    **成因两类，处置不同——必须分开报**：
    - **甲 切点错位**：该 S 组中文已分 ≥2 段 → 英文有多个片位，只是 DP 选了偏的位置
      → 列出片内可切点并**模拟重跑该组**给出新片宽，供人工挑点后写 `_fix_splits.tsv`
    - **乙 片数不足**：该 S 组中文只 1 段 → 回填**直接跳过切分 DP**（`groups = [(0, m)]`）
      → 定点修复**物理上不可能生效**，只能回中文译文侧补句内标点（或接受）
    """
    lines = ["# 超宽英文片定点修复草稿", "",
             "> **待裁决草稿，不参与回填**。选定后把「抄进 tsv 的行」抄到 "
             "`vocalign/_fix_splits.tsv`（`<S号>\\t<左词> | <右词>`）再重跑回填。",
             "> 成因两类、处置不同——**乙类写 `_fix_splits.tsv` 无效**（该 S 组回填不跑切分 DP）。", ""]
    n_jia = n_yi = 0
    for i, we, wz, rt, _en in over_en:
        r = bi_out[i - 1]
        ss = r.get("ss") or ()
        slabel = "+".join("S%d" % s for s in ss) or "(无 S 号)"
        sibs = [q for q in bi_out if q.get("ss") == ss]
        lines += ["## 第 %d 片 → %s（英宽 %.1f / 中宽 %.1f = %.2f 倍）" % (i, slabel, we, wz, rt),
                  "", "- 中文：%s" % r["zh"], "- 英文：%s" % r["en"]]
        if len(sibs) <= 1:
            n_yi += 1
            lines += ["",
                      "**成因：乙 片数不足** —— 该 S 组中文仅 1 段，回填直接令英文 1 片（**不跑切分 DP**）。",
                      "",
                      "→ 处置：定点修复**无效**。回中文译文侧在句内补一处标点使其分 2 段，或接受现状。", ""]
            continue
        n_jia += 1
        rng = (min(q["w0"] for q in sibs), max(q["w1"] for q in sibs))
        sibs_w = [text_width(q["zh"]) for q in sibs]
        lines += ["",
                  "**成因：甲 切点错位** —— 该 S 组中文分 %d 段（本片为组内第 %d 片），"
                  "英文片位足够，只是 DP 把切点放偏。" % (len(sibs), r["pi"] + 1),
                  "",
                  "组内现状：" + " · ".join(
                      "%d) 中 %.1f / 英 %.1f" % (j, text_width(q["zh"]), text_width(q["en"]))
                      for j, q in enumerate(sibs, 1)),
                  "",
                  "| 切点（本片内） | 证据 | 抄进 tsv 的行 | 本片 英/中 | 组内最大 英/中 |",
                  "|---|---|---|---|---|"]
        rows = []
        for gi in range(1, r["w1"] - r["w0"]):
            g = r["w0"] + gi
            if g >= r["w1"]:
                break
            # extra_fix 是**相对组首**（wslice 起点）的左侧词索引，非相对本片首
            newg = sim_group(toks, rng, sibs_w, cand, fix, pen_cand, extra_fix=g - rng[0] - 1)
            if not newg or len(newg) != len(sibs):
                continue
            pw = _piece_widths(toks, newg)
            my = pw[r["pi"]] / max(sibs_w[r["pi"]], 1.0)
            mx = max(pw[j] / max(sibs_w[j], 1.0) for j in range(len(sibs)))
            rows.append((my, mx, "%s | %s" % (toks[g - 1]["stem"], toks[g]["stem"]),
                         cut_reason(toks, g, cand, fix),
                         "%s\t%s | %s" % (slabel, toks[g - 1]["stem"], toks[g]["stem"])))
        rows.sort(key=lambda t: (t[1], t[0]))            # 按**组内最大比例**排（最小化最坏情况）
        for my, mx, label, why, tsv in rows[:DRAFT_MAX_ROWS]:
            lines.append("| %s | %s | `%s` | %.2f | %.2f |" % (label, why, tsv, my, mx))
        if len(rows) > DRAFT_MAX_ROWS:
            lines.append("| …… | （另有 %d 个切点，效果更差已略） | | | |" % (len(rows) - DRAFT_MAX_ROWS))
        if rows:
            best = rows[0]
            ok = ("组内**全部片达标**（最大 %.2f 倍）" % best[1] if best[1] < OVER_WIDE_RATIO
                  else "组内仍不达标（最大 %.2f 倍）——本片内切点已穷举，须回候选点环节补候选或接受" % best[1])
            lines += ["", "✓ 推荐（组内最均衡）：`%s` —— %s" % (best[4], ok)]
        lines.append("")
    lines.insert(4, "- 甲 切点错位 %d 处 / 乙 片数不足 %d 处" % (n_jia, n_yi))
    return lines


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


def load_e0_texts(e0_dir=None, srt_path=None):
    """E0 载体 → {S 号: 定稿长句文本}

    回填的英文片文本源（替代语音词序列的转写原样）——定稿的**仲裁修正**
    （如 `MD`→`Emdy`）与**并入的非口播注释**因此进入交付稿英文行，与中文侧一致。
    文件缺失时返回空 dict（调用方回退词序列文本）。
    """
    path = srt_path or (os.path.join(e0_dir, "long_lines.srt") if e0_dir else None)
    if not path or not os.path.isfile(path):
        return {}
    out = {}
    raw = open(path, encoding="utf-8-sig").read()
    for block in re.split(r"\n\s*\n", raw.strip()):
        lines = [x.strip() for x in block.split("\n") if x.strip()]
        ti = next((i for i, ln in enumerate(lines) if SRT_TIME.search(ln)), None)
        if ti is None:
            continue
        try:
            idx = int(lines[0])
        except ValueError:
            continue
        out[idx] = " ".join(lines[ti + 1:]).strip()
    return out


def _tokkey(tok):
    return re.sub(r"[^a-z0-9']", "", tok.lower())


def map_e0_slices(skel_tokens, e0_text, groups):
    """把骨架切点分组映射到 E0 定稿文本 → 每片的定稿文本

    骨架词序列（语音实测时间锚）与定稿文本（含仲裁修正 / 并入注释）经 difflib 对齐：
      · 有锚的定稿词 → 归属其锚所在片
      · 无锚的新增词（仲裁改写、并入注释）→ 归属**前一个**有锚词所在片
    映射乱序（分组边界非单调）时返回 None，调用方回退骨架文本。
    """
    import difflib
    e_toks = e0_text.split()
    if not e_toks or not skel_tokens:
        return None
    sm = difflib.SequenceMatcher(None, [_tokkey(t) for t in skel_tokens],
                                 [_tokkey(t) for t in e_toks], autojunk=False)
    grp_of_skel = {}
    for gi, (a, b) in enumerate(groups):
        for i in range(a, b):
            grp_of_skel[i] = gi
    e_grp = [0] * len(e_toks)
    last = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "delete":
            continue
        n = min(i2 - i1, j2 - j1)
        for k in range(n):
            g = grp_of_skel.get(i1 + k)
            if g is not None:
                last = g
            e_grp[j1 + k] = last
        for k in range(n, j2 - j1):
            e_grp[j1 + k] = last
    maxidx = []
    for gi in range(len(groups)):
        js = [j for j in range(len(e_toks)) if e_grp[j] == gi]
        maxidx.append(max(js) if js else -1)
    seq = [x for x in maxidx if x >= 0]
    if any(seq[k] > seq[k + 1] for k in range(len(seq) - 1)):
        return None
    buckets = [[] for _ in groups]
    for j, t in enumerate(e_toks):
        buckets[e_grp[j]].append(t)
    return [" ".join(b) for b in buckets]


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
    ap.add_argument("--fix-splits", default=None,
                    help="定点修复清单（后处理兜底：对超宽/失衡处直接指定切点；格式见文档）")
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
    e0_texts = load_e0_texts(args.e0, args.stime_srt)
    if not align:
        sys.exit("❌ align 目录无有效对应：%s" % args.align)
    cand = load_candidates(args.candidates) if args.candidates else {}
    if args.candidates and not cand:
        print("⚠️ --candidates 目录内无有效候选点（检查 norm 是否已跑）：%s" % args.candidates)
    fix, fix_miss = load_fix_splits(args.fix_splits, toks, stime)
    if fix:
        print("定点修复切点：%d 处" % len(fix))
    for m in fix_miss:
        print("⚠️ --fix-splits 未命中：%s" % m)

    chunk_files = collect_chunk_files(args.chunks)
    r02_files = collect_chunk_files(args.r02)
    keys = sorted(set(chunk_files) & set(r02_files))
    if not keys:
        sys.exit("❌ chunks 与 r02_results 无共同块号")

    os.makedirs(args.out, exist_ok=True)
    zh_out, bi_out, alerts, fails = [], [], [], []
    n_no_align = 0
    src_count, n_cand_used, n_fix_used, no_evid = {}, 0, 0, []
    lowconf_pts = []
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
        # ---- 取词范围：先算原始范围，再一次双向钳成互不重叠（见 hard_split_ranges）----
        plan = []
        for ss, sibs in clusters:
            sts = [x for x in (stime.get(s) for s in ss) if x]
            if not sts:
                alerts.append("⚠️ 块 %s：S 组 %s 无时间（E0 载体缺该长句）" % (k, ss))
                continue
            t0, t1 = min(x[0] for x in sts), max(x[1] for x in sts)
            rng = words_in_range(toks, t0, t1)
            if not rng:
                alerts.append("⚠️ 块 %s：S 组 %s 时间范围 %.2f–%.2f 内无词" % (k, ss, t0, t1))
                continue
            plan.append([ss, sibs, t0, t1, rng])
        for pp, fr in zip(plan, hard_split_ranges(toks, [pp[4] for pp in plan])):
            pp[4] = fr
        prev_end = None                      # 上一个 S 组的词范围终点（兜底校验用）
        for ss, sibs, t0, t1, rng in plan:
            if prev_end is not None and rng[0] < prev_end:
                # 双向钳制后理论上不应再重叠；残留即告警（不改数据，避免静默偏移）
                alerts.append("⚠️ 块 %s：S 组 %s 词范围仍与前组重叠（%d < %d）"
                              % (k, ss, rng[0], prev_end))
            prev_end = rng[1]
            wslice = toks[rng[0]:rng[1]]
            # 假空隙探测（**与是否被采用无关**）：本组内“有长停顿但附近有对齐可疑词”的位置。
            # 旧稿里它们是**零惩罚强切点**（sent-pause）→ 空隙落在段间、播放时字幕消失 1s+。
            for gi in range(1, len(wslice)):
                gnet = (wslice[gi]["start"] - wslice[gi - 1]["end"]) * 1000.0 - BASELINE_MS
                if gnet < SENT_PAUSE_MS or wslice[gi - 1]["punct"]:
                    continue
                if _low_conf(wslice, gi):
                    lo = max(0, gi - LOWCONF_WINDOW)
                    hi = min(len(wslice), gi + 2 + LOWCONF_WINDOW)
                    lowconf_pts.append(
                        "块 %s %s：词 %d“%s”|“%s”（停顿 %.0fms，附近最低 score %.2f）" % (
                            k, "+".join("S%d" % e for e in ss), rng[0] + gi - 1,
                            wslice[gi - 1]["stem"] + wslice[gi - 1]["punct"],
                            wslice[gi]["stem"] + wslice[gi]["punct"],
                            gnet + BASELINE_MS,
                            min((wslice[j].get("score") or 0.0) for j in range(lo, hi))))
            if len(sibs) == 1:
                groups = [(0, len(wslice))]
            else:
                # 中文段宽占比 → 英文词序列的目标片宽（带下限，防极短段）
                tot_zh = sum(w for _t, w, _z in sibs) or 1.0
                tot_en = sum(len(w["stem"]) + len(w["punct"]) + 1 for w in wslice) or 1.0
                targets = [max(MIN_PIECE_CHARS, tot_en * (w / tot_zh)) for _t, w, _z in sibs]
                # 候选点是**全局词号**（跨块有效）→ 换算成 wslice 内的相对索引
                local = {g - rng[0] for g in cand if rng[0] <= g < rng[1]}
                local_fix = {g - rng[0] for g in fix if rng[0] <= g < rng[1]}
                groups = dp_split_words(wslice, targets, cand=local,
                                        pen_cand=args.penalty_candidate, fix=local_fix)
                if groups is None:
                    # 词数 < 中文段数：按词索引**等分**为 k 组（可能含空组）——
                    # ⚠️ 不可整体合并（旧写法 groups=[(0,m)] 会让多余中文段拿到整段时间 → **时间重叠**）
                    alerts.append("⚠️ 块 %s：S 组 %s 词数 %d < 中文段数 %d → 按索引等分（部分英文行为空）"
                                  % (k, ss, len(wslice), len(sibs)))
                    nw, ng = len(wslice), len(sibs)
                    groups = [(int(round(nw * gi / ng)), int(round(nw * (gi + 1) / ng)))
                              for gi in range(ng)]
                else:
                    # 切点验收统计（证据来源 + 候选点采用）
                    for gi in range(len(groups) - 1):
                        b = groups[gi][1]
                        why = cut_reason(wslice, b, local, local_fix)
                        src_count[why] = src_count.get(why, 0) + 1
                        if b - 1 in local_fix:
                            n_fix_used += 1
                        if b - 1 in local:
                            n_cand_used += 1
                        if why == "none":
                            no_evid.append("块 %s S组 %s：词 %d“%s”|“%s”无证据切点" % (
                                k, "+".join("S%d" % e for e in ss), rng[0] + b - 1,
                                wslice[b - 1]["stem"] + wslice[b - 1]["punct"],
                                wslice[b]["stem"] + wslice[b]["punct"]))
            # 英文片文本改用 E0 定稿文本（仲裁修正 / 并入注释随之进入英文行）
            e0_slices = None
            if e0_texts:
                e0_text = " ".join(e0_texts.get(s, "") for s in ss).strip()
                if e0_text:
                    e0_slices = map_e0_slices(
                        [w["stem"] + w["punct"] for w in wslice], e0_text, groups)
            for si, (seg_text, seg_w, zno) in enumerate(sibs):
                if si < len(groups):
                    a, b = groups[si]
                    gw = wslice[a:b]
                    if gw:
                        st, en = gw[0]["start"], gw[-1]["end"]
                    else:
                        # 空片（词数不足时的等分结果）：零宽时间点，避免与相邻段重叠
                        st = en = (wslice[a - 1]["end"] if a > 0 else t0)
                    if e0_slices and si < len(e0_slices):
                        en_text = e0_slices[si]
                    else:
                        en_text = render(gw) if gw else ""
                else:
                    a, b = len(wslice), len(wslice)
                    st, en = t0, t1
                    en_text = e0_slices[si] if (e0_slices and si < len(e0_slices)) else ""
                zh_out.append({"start": st, "end": en, "text": seg_text, "z": zno})
                # ss / pi / pn / w0 / w1 = 超宽片诊断所需（S 组号、组内序号与总片数、全局词号区间）
                bi_out.append({"start": st, "end": en, "zh": seg_text, "en": en_text, "z": zno,
                               "ss": tuple(ss), "pi": si, "pn": len(sibs),
                               "w0": rng[0] + a, "w1": rng[0] + b})

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

    # ---- 超宽片检测：**比例失衡**是缺候选点的唯一可见信号 ----
    # 为何不单用“英宽 > 硬限”：硬限是**中文**（1.0/字符）的尺，英文按视觉宽（0.4/字符）
    # 本就比中文大（正常片英/中 ≈ 1.3）——按硬限单判会报出四成片为“超宽”（全是误报）。
    # 真失衡（缺候选点）的实测形态：中文 7 字而英文片 99 字符（比例 5.7）。故叠加倍率条件。
    # 两类分开：中文自己超限（中文分段问题）vs 英宽超限且比例失衡（缺候选点）。
    over_en, over_zh = [], []
    for i, r in enumerate(bi_out, 1):
        we, wz = text_width(r["en"]), text_width(r["zh"])
        if wz > args.hard_max:
            over_zh.append((i, round(wz, 1), r["zh"]))
        elif we > args.hard_max and we / max(wz, 1.0) >= OVER_WIDE_RATIO:
            over_en.append((i, round(we, 1), round(wz, 1), round(we / max(wz, 1.0), 1), r["en"]))
    # 成因分类（决定处置路径）：甲 = 该 S 组中文 ≥2 段（可挪切点）；乙 = 中文只 1 段（不跑 DP）
    over_jia = [t for t in over_en if (bi_out[t[0] - 1].get("pn") or 1) > 1]
    over_yi = [t for t in over_en if (bi_out[t[0] - 1].get("pn") or 1) <= 1]

    with open(os.path.join(args.out, "r04_alerts.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# vocalign 回填告警\n\n")
        fh.write("- 块数 %d；中文段 %d；Z 句无对应 %d\n" % (len(keys), len(zh_out), n_no_align))
        fh.write("- 切点来源：%s（候选点采用 %d；定点修复采用 %d）\n"
                 % (src_summary(), n_cand_used, n_fix_used))
        fh.write("- 语义候选点：%s\n" % ("目录 %s，共 %d 个" % (args.candidates, len(cand))
                                      if cand else "未启用（纯语音权重）"))
        if fix or fix_miss:
            fh.write("- 定点修复（`--fix-splits`）：%s；命中 %d / 未命中 %d\n" % (
                args.fix_splits, n_fix_used, len(fix_miss)))
        if fix_miss:
            fh.write("\n## 定点修复未命中（%d 处）\n\n" % len(fix_miss))
            fh.write("> 逐条核对：锚为「S 号 + 相邻两词」，需在**该 S 时间范围内**唯一命中；\n")
            fh.write("> 未命中 = 词写错 / 该词对不在该 S 范围内 / 该 S 无时间（E0 载体缺句）。\n\n")
            for m in fix_miss[:200]:
                fh.write("- %s\n" % m)
        if no_evid:
            fh.write("\n## 无证据切点（%d 处）\n\n" % len(no_evid))
            fh.write("> 无标点也无停顿可依的切点——语义候选点环节的目标消除对象。\n\n")
            for s in no_evid[:200]:
                fh.write("- %s\n" % s)
        if lowconf_pts:
            fh.write("\n## 假空隙位置（低置信停顿，%d 处）\n\n" % len(lowconf_pts))
            fh.write("> 该处**有长停顿、但附近有对齐可疑词**（score < %.2f）——空隙来自音素对齐失败\n"
                     % LOWCONF_SCORE)
            fh.write("> （非真停顿）。已从语音证据中剔除（惩罚同“无证据”位）。\n")
            fh.write("> 其中 gap ≥ 1s 者若不剔除会落在段间 → 播放时字幕消失 1s+（超出空隙填充阈值）。\n\n")
            for s in lowconf_pts[:200]:
                fh.write("- %s\n" % s)
        if over_zh:
            fh.write("\n## 超宽中文段（宽 > %.0f，%d 处）\n\n" % (args.hard_max, len(over_zh)))
            fh.write("> 中文分段未能拆到硬限内（**中文侧**问题，非候选点缺失）：回中文译文侧收窄措辞或补句内标点。\n\n")
            for i, wz, zh in over_zh[:200]:
                fh.write("- 第 %d 段（宽 %.1f）：%s\n" % (i, wz, zh[:70]))
        if over_jia:
            fh.write("\n## 超宽英文片·甲 切点错位（%d 处）\n\n" % len(over_jia))
            fh.write("> 该 S 组中文已分 ≥2 段，英文片位足够，**只是 DP 把切点放偏**。\n")
            fh.write("> 处置：按 `_fix_splits.draft.md` 挑切点写 `_fix_splits.tsv` → 带 `--fix-splits` 重跑回填。\n\n")
            for i, we, wz, ratio, en in over_jia[:200]:
                fh.write("- 第 %d 片（英宽 %.1f / 中宽 %.1f = %.1f 倍）：%s\n"
                         % (i, we, wz, ratio, en[:70]))
        if over_yi:
            fh.write("\n## 超宽英文片·乙 片数不足（%d 处）\n\n" % len(over_yi))
            fh.write("> 该 S 组中文**只 1 段** → 回填直接令英文 1 片（**不跑切分 DP**）\n")
            fh.write("> → 定点修复与补候选点**均无效**。处置：回中文译文侧补句内标点使其分 2 段，或接受现状。\n\n")
            for i, we, wz, ratio, en in over_yi[:200]:
                fh.write("- 第 %d 片（英宽 %.1f / 中宽 %.1f = %.1f 倍）：%s\n"
                         % (i, we, wz, ratio, en[:70]))
        if alerts:
            fh.write("\n## 告警\n\n")
            for a in alerts[:200]:
                fh.write("- %s\n" % a)
        if fails:
            fh.write("\n## 校验失败\n\n")
            for f in fails[:200]:
                fh.write("- ⛔ %s\n" % f)

    print("vocalign 回填：块 %d / 中文段 %d / Z 无对应 %d" % (len(keys), len(zh_out), n_no_align))
    print("切点来源：%s（候选点采用 %d；定点修复采用 %d）" % (src_summary(), n_cand_used, n_fix_used))
    if fix_miss:
        print("⚠️ 定点修复未命中 %d 处（详见 r04_alerts.md）" % len(fix_miss))
    if no_evid:
        print("⚠️ 无证据切点 %d 处（详见 r04_alerts.md）" % len(no_evid))
    if lowconf_pts:
        print("ℹ️ 假空隙位置 %d 处已从语音证据中剔除（详见 r04_alerts.md）" % len(lowconf_pts))
    if over_en or over_zh:
        print("⚠️ 超宽片：英文 甲%d / 乙%d（中文 %d）——详见 r04_alerts.md" % (
            len(over_jia), len(over_yi), len(over_zh)))
        if over_en:
            draft_path = os.path.join(args.out, "_fix_splits.draft.md")
            with open(draft_path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("\n".join(
                    over_wide_draft(over_en, bi_out, toks, cand, fix, args.penalty_candidate)) + "\n")
            print("   定点修复草稿（待裁决）：%s" % draft_path)
    else:
        stale = os.path.join(args.out, "_fix_splits.draft.md")
        if os.path.isfile(stale):
            print("ℹ️ 已无超宽片；旧草稿仍在（可删）：%s" % stale)
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
