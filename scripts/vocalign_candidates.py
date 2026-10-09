# -*- coding: utf-8 -*-
"""vocalign 语义候选点：清单导出 / 作答校验 / 词号归一化（三模式，纯标准库）

定位
    vocalign 工作流阶段三的**唯一 LLM 环节**。骨架（标点 + 净停顿）能给出的候选点
    有硬上限 —— 子句内部仍需切分时骨架零候选：

        S32  152.549 → 156.526（1 子句 / 18 词）
             What do you think happens when I input a pulse that's shorter than the delay the repeater has?
        → 实际必须切成 2 片（`What do you think happens | when I input a pulse...`），
          该位置无标点、无 ≥250ms 停顿，**只能靠 LLM 的语义判断**。

    ⚠️ 候选点**只是候选**（宁多勿少）：最终切点由 `vocalign_backfill.py` 按
    “中文段宽占比 + 语音证据（停顿 / 标点）”在候选中挑。故本脚本**不做取舍**。

三模式（两趟式）
    emit   骨架 + 词级时轴 → `<dir>/_request/chunk_<k>.md`（派发清单）
    check  agent 作答 `<dir>/reply/chunk_<k>.txt` → 校验报告 `<dir>/_check_report.md`
    norm   校验通过的行 → `<dir>/chunk_<k>.tsv`（机器消费：`S<n>\\t全局词号\\t句内词号`）

作答格式契约（与 `.github/skills/vocalign/task-candidates.md` 同步）
    | 项 | 规定 |
    | 行首 | `S<n>`（与 `skeleton.json` 的长句编号一致）+ 空白 |
    | 分隔符 | ` \\| `（前后各一空格，表示断在**词间**） |
    | 数量 | **宁多勿少**（候选集，不是最终切点） |
    | 禁止 | `/`（Minecraft 命令大量使用）、增删改任何词、写时间戳 / 行号 |
    | 清单给 | `⋯<ms>⋯` = 该词边界处**净停顿**（仅 ≥250ms 标注；**仅供参考，不是判据**） |
    | 清单不给 | 脚本自己的切分结果（避免引导“微调”而非“重判”） |

校验判据（4 条，任一条不过 → 该行失败）
    1. `S<n>` 存在于清单、不重复、无多余行
    2. 不含 `/`（原句本身含 `/` 时按数量放行）
    3. 去分隔符与空白后**逐字符等于**原句（禁增删改词）
    4. 分隔符**落在词边界**：按 ` | ` 分段后展开的 token 序列须**等于**原句 token 序列
       （判据 3 抓不到“切在词中”，如 `happ | ens` —— 故须判据 4）

    ⚠️ **无候选的行（原样回抄）同样过判据 2–4** —— 否则“删词但不加分隔符”会静默通过。

    失败行**不静默采信**：该 S 号记为空候选 → 回填时回退纯语音权重，并计入 `r04_alerts.md`。

词号口径
    **全局词号** = `words.json` 的 `words[]` 下标（0-based），语义为“在**该词之后**切”，
    与 `vocalign_backfill.py` 的 `cut_cost(words, i)` 一致。
    ⚠️ 本脚本**不跳过空 token**（索引与 `vocalign_skeleton.py` 的 token 序号同口径）；
    若 `words.json` 真含空 token，回填侧（`load_words_index` 会跳过）会错位 → 本脚本检出即告警。

E0 定稿文本（`--e0`）
    候选点清单的句子应显示 **E0 定稿文本**（而非 `skeleton.json` 的原始文本）——否则
    E0 的仲裁修正（如 `MD`→`Emdy`）不会进清单，标出的 ` | ` 位置会与实际文本错位。

    ⚠️ **E0 与骨架原文可能增删词**（仲裁替换词数不同、注释并入新增词）→
    **禁止按顺序映射** E0 词号 ↔ 原词号。正确做法：
      · **定位**句区间仍用**骨架文本**（与 `words.json` 同源，可靠）
      · **展示/校验**用 E0 文本
      · **词号锚定**用 **difflib 相似度对齐**（`map_e0_to_orig`）——E0 新增词映射为 None（不作切点）

用法（命令根 = Project_Main/）
    python scripts/vocalign_candidates.py emit  --skeleton <work>/vocalign --words <work>/vocalign \\
        --chunks <work>/vocalign/chunks --srt <work>/01_subtitle_asr_fixed.srt
    python scripts/vocalign_candidates.py check --skeleton <work>/vocalign --words <work>/vocalign
    python scripts/vocalign_candidates.py norm  --skeleton <work>/vocalign --words <work>/vocalign

退出码：0 = 无失败行；1 = 有失败行（详见校验报告）。
"""
import argparse
import bisect
import difflib
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

from shared.srt_common import collect_chunk_files, parse_owned_cue_range

PM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PM not in sys.path:
    sys.path.insert(0, PM)
from scripts.srt_reflow_core.io import parse_srt  # noqa: E402

# ---- 格式契约常量（改动须同步 skill 的 task-candidates.md / docs/PRODUCT_FORMATS_VOCALIGN.md）----
SEP_CHAR = "|"                 # 候选点分隔符（**禁用 `/`**：MC 命令 `/give` `/setblock` 会撞车）
SEP_SPLIT = re.compile(r"\s*\|\s*")
MARK_RE = re.compile(r"\s*\u22ef\s*(\d+)\s*ms\s*\u22ef\s*")   # `⋯320ms⋯` 停顿标注
PAUSE_MARK_MS = 250.0          # 仅标注净停顿 ≥ 此值的边界（与骨架子句阈值同源）
FORBID = "/"                   # 禁止字符（原句本身含有时按数量放行）
S_LINE = re.compile(r"^\s*S(\d+)\s+(.*\S)\s*$")
TRIM = set(".,;:!?\u2014\u2013\"')]")
DEFAULT_DIRNAME = "candidates"
REQUEST_SUB = "_request"
REPLY_SUB = "reply"
REPORT_NAME = "_check_report.md"


def split_punct(tok):
    """拆词尾标点（与 vocalign_skeleton.py 同口径）"""
    t = (tok or "").strip()
    i = len(t)
    while i > 0 and t[i - 1] in TRIM:
        i -= 1
    return t[:i], t[i:]


def strip_mark(s):
    """剥离清单里的停顿标注（`⋯320ms⋯`）——校验前必须做，否则会被判成“改词”"""
    return MARK_RE.sub(" ", s)


def densify(s):
    """去全部空白（逐字符比较用）"""
    return re.sub(r"\s+", "", s)


def _file(path, name):
    """路径可为文件本身，也可为所在目录（自动补默认文件名）"""
    return path if os.path.isfile(path) else os.path.join(path, name)


# ---------------------------------------------------------------- 输入

def load_words_ordered(path):
    """`words.json` → 词序列（**不跳过空 token**，索引须与 skeleton 的 token 序号同口径）

    ⚠️ `vocalign_backfill.py` 的 `load_words_index` **会跳过**空 token —— 若 words.json 真含
    空 token，两者索引会错位。故此处检出即告警（实测 PRR 2 = 0 个）。
    """
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    raw = data.get("words") if isinstance(data, dict) else data
    toks, n_empty = [], 0
    for w in raw or []:
        stem, punct = split_punct(w.get("text", ""))
        if not stem and not punct:
            n_empty += 1
        toks.append({"stem": stem, "punct": punct})
    return toks, n_empty


def load_boundaries(path):
    """`boundaries.txt` → {词号: 净停顿 ms}

    词号 i = 在 toks[i] 与 toks[i+1] 之间；`why=interp-skip` 的边界**不作停顿证据**
    （未对齐词的时间是插值估算的，拿它当停顿会把“空洞”误报成边界 —— 踩坑清单 §7.1 第 1 条）。
    """
    out = {}
    if not os.path.isfile(path):
        return out
    with open(path, encoding="utf-8-sig") as fh:
        for ln in fh:
            if ln.startswith("#") or not ln.strip():
                continue
            parts = ln.rstrip("\n").split("\t")
            if len(parts) < 7:
                continue
            try:
                i, net = int(parts[0]), float(parts[5])
            except ValueError:
                continue
            if parts[2] == "interp-skip":
                continue
            out[i] = net
    return out


def load_skeleton(path):
    """`skeleton.json` → sentences 列表（S1 起，顺序即长句编号）"""
    with open(path, encoding="utf-8-sig") as fh:
        rep = json.load(fh)
    sents = rep.get("sentences") or []
    if not sents:
        sys.exit("❌ skeleton.json 无 sentences 字段：%s" % path)
    return rep, sents


def load_e0_texts(e0_dir):
    """读 E0 定稿文本 → {S 号: 文本}（无 E0 时返回 {}，回退骨架文本）

    优先 `long_lines.srt`（机器产物），回退 `long_lines.md`。
    """
    if not e0_dir:
        return {}
    srt = os.path.join(e0_dir, "long_lines.srt")
    md = os.path.join(e0_dir, "long_lines.md")
    out = {}
    if os.path.isfile(srt):
        with open(srt, encoding="utf-8-sig") as fh:
            raw = fh.read()
        for block in re.split(r"\n\s*\n", raw.strip()):
            lines = [x.strip() for x in block.split("\n") if x.strip()]
            ti = next((i for i, ln in enumerate(lines) if "-->" in ln), None)
            if ti is None:
                continue
            try:
                out[int(lines[0])] = " ".join(lines[ti + 1:])
            except ValueError:
                continue
    elif os.path.isfile(md):
        with open(md, encoding="utf-8-sig") as fh:
            for ln in fh:
                m = S_LINE.match(ln.rstrip("\n"))
                if m:
                    out[int(m.group(1))] = m.group(2)
    return out


def canon_one(tok):
    """词形归一（仅用于**相似度比较**；不用于展示）"""
    return re.sub(r"[^a-z0-9']", "", (tok or "").lower())


def map_e0_to_orig(e0_text, slice_toks):
    """E0 定稿词序列 → 原词号映射（**difflib 相似度对齐**，不按顺序）

    为何需要：E0 相对骨架原文可能**增删词**（仲裁替换词数不同、注释并入新增词）
    → “第 k 个 E0 词 = 第 k 个原词”不成立。对两边的**归一词形序列**做对齐：
      · equal / replace → E0 该词映射到对应原词号
      · insert（E0 有、原无） → `None`（E0 新增词，如注释：不作切点锚）
      · delete（原有、E0 无） → 不产生映射项

    返回 `(mapping, inv)`：`mapping[k]` = 原词号或 None；`inv[原词号]` = E0 词号。
    """
    e = e0_text.split()
    o = [t["stem"] + t["punct"] for t in slice_toks]
    ec = [canon_one(x) for x in e]
    oc = [canon_one(x) for x in o]
    sm = difflib.SequenceMatcher(None, oc, ec, autojunk=False)
    mapping = [None] * len(e)
    inv = {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("equal", "replace"):
            for k in range(min(i2 - i1, j2 - j1)):
                mapping[j1 + k] = i1 + k
                inv[i1 + k] = j1 + k
    return mapping, inv


def locate_sentences(sents, toks):
    """把骨架长句定位到词序列区间 `[a, b)`

    判据：**去空白后的长句文本应是词序列拼接串的连续子串**（骨架本由 words 生成，必然成立；
    不成立说明 skeleton.json 与 words.json 不同源 → 必须报错而非猜）。用递增游标 + find
    定位，兼作一致性校验。返回 (ranges, warnings, error)。
    """
    parts, starts, pos = [], [], 0
    for t in toks:
        starts.append(pos)
        piece = t["stem"] + t["punct"]
        parts.append(piece)
        pos += len(piece)
    flat = "".join(parts)

    out, cursor, nonmono = [], 0, 0
    for si, s in enumerate(sents, 1):
        key = densify(s.get("text", ""))
        if not key:
            return None, None, "S%d 文本为空（skeleton.json 异常）" % si
        p = flat.find(key, cursor)
        if p < 0:
            p = flat.find(key)              # 回退：骨架次序与词序不一致
            if p < 0:
                return None, None, ("S%d 文本在词序列中找不到（skeleton 与 words 不同源）：%s"
                                    % (si, s["text"][:60]))
            nonmono += 1
        cursor = p + len(key)
        a = bisect.bisect_right(starts, p) - 1
        b = bisect.bisect_left(starts, cursor)
        if b <= a:
            return None, None, "S%d 定位到空区间（%d,%d）" % (si, a, b)
        out.append((a, b))
    warns = ["长句次序与词序不一致 %d 处（已按文本回退定位）" % nonmono] if nonmono else []
    return out, warns, None


# ---------------------------------------------------------------- 分块

def chunk_ranges(chunks_dir, srt_path):
    """分块目录 + 01 srt → [(块号, 起, 止)]（用 OWNED cue 范围的时间）"""
    cues = {c["idx"]: (c["start"] / 1000.0, c["end"] / 1000.0) for c in parse_srt(srt_path)}
    out = []
    for k, p in sorted(collect_chunk_files(chunks_dir).items()):
        r = parse_owned_cue_range(p)
        if not r:
            continue
        a, b = r
        if a in cues and b in cues:
            out.append((k, cues[a][0], cues[b][1]))
    return out


def bucket_of(t, ranges):
    """时间 → 块号：落在 [t0,t1) 内即归该块；落在块间缝隙或末尾 → 归**前一块**（保证全覆盖）"""
    prev = None
    for k, t0, t1 in ranges:
        if t0 <= t < t1:
            return k
        if t < t0:
            return prev if prev is not None else k
        prev = k
    return prev


# ---------------------------------------------------------------- 渲染

def render_text(slice_toks):
    """词序列 → 文本（标点紧贴前词，词间单空格）"""
    out = ""
    for t in slice_toks:
        piece = t["stem"] + t["punct"]
        out = piece if not out else out + " " + piece
    return out


def render_marked(slice_toks, marks, first_word):
    """带停顿标注的清单文本：`happens ⋯320ms⋯ when`

    `slice_toks` 可以是词 dict（骨架词）或**字符串**（E0 定稿文本按空白切）；
    `marks` 的键是**相对本句**的词号（0-based，表示该词之后），
    `first_word` = 本句首词的全局词号（字符串模式下传 0，marks 键用相对词号）。
    """
    out = ""
    for j, t in enumerate(slice_toks):
        piece = (t["stem"] + t["punct"]) if isinstance(t, dict) else t
        out = piece if not out else out + " " + piece
        g = first_word + j
        if g in marks:
            out += " \u22ef%dms\u22ef" % int(round(marks[g]))
    return out


# ---------------------------------------------------------------- 作答校验（check / norm 共用）

def validate_line(body, orig_text):
    """校验一行作答 → (错误列表, 切点相对词号列表)

    返回的切点词号 = **该词之后切**（1-based，相对本句词序）。
    """
    errs, cuts = [], []
    clean = strip_mark(body).strip()
    if not clean:
        return ["空作答（未回抄原句）"], []
    if FORBID in clean and clean.count(FORBID) > orig_text.count(FORBID):
        errs.append("含 `/`（MC 命令撞车，契约禁止）")
    segs = SEP_SPLIT.split(clean)
    if any(not x.strip() for x in segs):
        errs.append("空段（分隔符落在句首 / 句尾或连续）")
    tok_ans = [t for x in segs for t in x.split()]
    tok_orig = orig_text.split()
    if tok_ans != tok_orig:
        # 细分原因，便于 agent 定位
        if densify(SEP_SPLIT.sub("", clean)) != densify(orig_text):
            errs.append("增删改词（去分隔符与空白后与原句不逐字符相等）")
        else:
            errs.append("词被拆开（插了空格，或分隔符不在词边界）")
    if len(segs) == 1:
        return errs, []                      # 无候选：合法（该句语义上不需额外切点）
    acc = 0
    for x in segs[:-1]:
        n = len(x.split())
        if n == 0:
            return errs, []
        acc += n
        cuts.append(acc)
    return errs, cuts


def load_reply(path):
    """读 agent 作答 → [(S号, 正文行)]（按行；跳过空行与 `#` 注释）"""
    rows = []
    with open(path, encoding="utf-8-sig") as fh:
        for ln in fh:
            ln = ln.rstrip("\n")
            if not ln.strip() or ln.lstrip().startswith("#"):
                continue
            m = S_LINE.match(ln)
            if not m:
                rows.append((None, ln))
                continue
            rows.append((int(m.group(1)), m.group(2)))
    return rows


def validate_chunk(rows, texts, expect=None):
    """校验整块作答 → (通过项 [(sno, cuts)], 报告行 [(sno, 问题)], 统计)

    `texts` = 长句文本列表（**E0 定稿**，agent 对着它抄）；`expect` = 该块应出现的 S 号集合。
    """
    ok, bad, seen, extra = [], [], {}, []
    for sno, body in rows:
        if sno is None:
            bad.append((None, "行首不是 `S<n>` 格式：%s" % body[:50]))
            continue
        if sno < 1 or sno > len(texts):
            bad.append((sno, "S 号越界（本视频长句数 %d）" % len(texts)))
            continue
        seen[sno] = seen.get(sno, 0) + 1
        if seen[sno] > 1:
            bad.append((sno, "S 号重复出现（第 %d 次）" % seen[sno]))
            continue
        errs, cuts = validate_line(body, texts[sno - 1])
        if errs:
            bad.append((sno, "；".join(errs)))
        else:
            ok.append((sno, cuts))
    if expect:
        extra = sorted(set(seen) - set(expect))
        for sno in extra:
            bad.append((sno, "该 S 号不在本批清单内（块归属错误或串行）"))
        for sno in sorted(set(expect) - set(seen)):
            bad.append((sno, "清单内的 S 号缺失作答（跳句 / 漏抄）"))
    return ok, bad, {"rows": len(rows), "extra": len(extra)}


# ---------------------------------------------------------------- 三模式

def do_emit(args, sents, toks, bounds, loc, cand_dir, e0_texts):
    """导出派发清单 `<dir>/_request/chunk_<k>.md`"""
    if args.chunks and args.srt:
        ranges = chunk_ranges(args.chunks, args.srt)
        if not ranges:
            sys.exit("❌ 未能从 chunks + srt 解析出块时间范围")
    else:
        ranges = [(1, float("-inf"), float("inf"))]

    groups = {}                              # 块号 → [(sno, a, b)]
    for si, (a, b) in enumerate(loc, 1):
        k = bucket_of(sents[si - 1].get("start", 0.0), ranges)
        groups.setdefault(k, []).append((si, a, b))

    os.makedirs(os.path.join(cand_dir, REQUEST_SUB), exist_ok=True)
    os.makedirs(os.path.join(cand_dir, REPLY_SUB), exist_ok=True)      # 供 subagent 直接写入
    lines, total_mark, total_sent = [], 0, 0
    for k in sorted(groups):
        if args.chunk and k != args.chunk:
            continue
        rows, n_mark = [], 0
        for si, a, b in groups[k]:
            sub = toks[a:b]
            e0t = e0_texts.get(si)
            if e0t:
                # E0 定稿文本：显示它；停顿标注需把**原词号**映射到 E0 词位置
                _mapping, inv = map_e0_to_orig(e0t, sub)
                mine = {}
                for g in range(a, b - 1):
                    if bounds.get(g, 0.0) >= PAUSE_MARK_MS:
                        j = inv.get(g - a)
                        if j is not None:
                            mine[j] = bounds[g]
                rows.append("S%d  %s" % (si, render_marked(e0t.split(), mine, 0)))
            else:
                mine = {g: bounds[g] for g in range(a, b - 1)
                        if bounds.get(g, 0.0) >= PAUSE_MARK_MS}
                rows.append("S%d  %s" % (si, render_marked(sub, mine, a)))
            n_mark += len(mine)
        nword = sum(b - a for _si, a, b in groups[k])
        body = ["# chunk_%03d" % k, "",
                "> 在语义单元边界插入 ` | `（前后各一空格）。已有标点处**不必**标注。",
                "> 候选**宁多勿少**；不得增删改任何词、不得写 `/` 与时间戳。",
                "> `\u22ef<ms>\u22ef` = 该词边界处实测净停顿（仅 ≥250ms 标注；仅供参考，**不是判据**）。",
                "> 长句 %d / 词 %d" % (len(rows), nword), ""]
        body += rows
        path = os.path.join(cand_dir, REQUEST_SUB, "chunk_%03d.md" % k)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(body) + "\n")
        lines.append("chunk_%03d：长句 %d / 词 %d / 停顿标注 %d" % (k, len(rows), nword, n_mark))
        total_mark += n_mark
        total_sent += len(rows)

    print("vocalign 候选点清单：块 %d / 长句 %d / 停顿标注 %d" % (len(lines), total_sent, total_mark))
    if args.expand:
        for ln in lines:
            print("   " + ln)
    print("产物目录：%s" % os.path.abspath(os.path.join(cand_dir, REQUEST_SUB)))
    return 0


def _chunk_listing(cand_dir, only=None):
    """列出待校验的块：优先用 reply/，其次用 _request/（都在则取交集）"""
    def nums(sub):
        d = os.path.join(cand_dir, sub)
        if not os.path.isdir(d):
            return set()
        return {int(m.group(1)) for fn in os.listdir(d)
                for m in [re.fullmatch(r"chunk_(\d{3})\.(?:txt|md)", fn)] if m}
    rep, req = nums(REPLY_SUB), nums(REQUEST_SUB)
    ks = sorted(rep & req) if (rep and req) else sorted(rep or req)
    if only:
        ks = [k for k in ks if k == only]
    return ks, rep, req


def _expected_snos(cand_dir, k):
    """清单里的 S 号集合（用于检缺失 / 检串块）"""
    path = os.path.join(cand_dir, REQUEST_SUB, "chunk_%03d.md" % k)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8-sig") as fh:
        return {int(m.group(1)) for ln in fh for m in [S_LINE.match(ln)] if m}


def build_texts(sents, e0_texts):
    """长句文本列表（**E0 优先**）+ 与骨架文本不同的句数

    展示与校验都用它（E0 才是 agent 实际看到的、也是翻译的输入）。
    """
    texts, n_diff = [], 0
    for i, s in enumerate(sents, 1):
        t = e0_texts.get(i) or s.get("text", "")
        texts.append(t)
        if e0_texts.get(i) and densify(t) != densify(s.get("text", "")):
            n_diff += 1
    return texts, n_diff


def do_check(args, sents, texts, cand_dir):
    """校验 agent 作答 → 报告 `<dir>/_check_report.md`"""
    ks, rep, req = _chunk_listing(cand_dir, args.chunk)
    if not ks:
        sys.exit("❌ 未找到待校验的作答（%s/chunk_<k>.txt）" % os.path.join(cand_dir, REPLY_SUB))
    if req - rep:
        print("⚠️ 清单存在但无作答的块：%s" % ", ".join("chunk_%03d" % k for k in sorted(req - rep)))

    rep_lines, n_rows, n_bad, n_cut = [], 0, 0, 0
    for k in ks:
        path = os.path.join(cand_dir, REPLY_SUB, "chunk_%03d.txt" % k)
        rows = load_reply(path)
        ok, bad, st = validate_chunk(rows, texts, _expected_snos(cand_dir, k))
        n_rows += st["rows"]
        n_bad += len(bad)
        n_cut += sum(len(c) for _s, c in ok)
        rep_lines.append("| chunk_%03d | %d | %d | %d | %d |" % (
            k, st["rows"], len(ok), n_bad, sum(len(c) for _s, c in ok)))
        if bad:
            rep_lines.append("")
            rep_lines.append("### chunk_%03d 失败明细" % k)
            rep_lines.append("")
            for sno, why in bad:
                rep_lines.append("- `%s`：%s" % ("S%d" % sno if sno else "（行）", why))
            rep_lines.append("")

    body = ["# vocalign 候选点校验报告", "",
            "- 块 %d；作答行 %d；失败 %d；候选点 %d" % (len(ks), n_rows, n_bad, n_cut),
            "", "| 块 | 行 | 通过 | 失败 | 候选点 |", "|---|---|---|---|---|"] + rep_lines
    with open(os.path.join(cand_dir, REPORT_NAME), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(body) + "\n")

    print("vocalign 候选点校验：块 %d / 行 %d / 失败 %d / 候选点 %d" % (len(ks), n_rows, n_bad, n_cut))
    print("报告：%s" % os.path.abspath(os.path.join(cand_dir, REPORT_NAME)))
    return 1 if n_bad else 0


def do_norm(args, sents, texts, toks, loc, cand_dir):
    """校验通过的行 → `<dir>/chunk_<k>.tsv`（S号 / 全局词号 / 句内词号）

    消费方 `vocalign_backfill.py --candidates <dir>`：**按全局词号取候选**
    （与块划分无关 —— 回填是按 S 组时间取词，故候选点全局有效）。

    ⚠️ 句内词号是 **E0 文本**的（agent 对着它标）；全局词号需经**相似度对齐**转成**原词号**
    （E0 可能增删词 → 不可 `a + c - 1` 直接加）。
    """
    ks, rep, _req = _chunk_listing(cand_dir, args.chunk)
    if not ks:
        sys.exit("❌ 未找到待归一化的作答（%s/chunk_<k>.txt）" % os.path.join(cand_dir, REPLY_SUB))
    all_bad, total, n_drop = [], 0, 0
    for k in ks:
        rows = load_reply(os.path.join(cand_dir, REPLY_SUB, "chunk_%03d.txt" % k))
        ok, bad, _st = validate_chunk(rows, texts, _expected_snos(cand_dir, k))
        all_bad += [("chunk_%03d" % k, sno, why) for sno, why in bad]
        out = ["# chunk_%03d\t长句 %d / 有候选 %d / 候选点 %d"
               % (k, len(rows), len(ok), sum(len(c) for _s, c in ok))]
        for sno, cuts in ok:
            a, b = loc[sno - 1]
            mapping, _inv = map_e0_to_orig(texts[sno - 1], toks[a:b])
            glob = []
            for c in cuts:
                kk = c - 1                        # E0 第 c 个词（0-based）
                if 0 <= kk < len(mapping) and mapping[kk] is not None:
                    glob.append(a + mapping[kk])  # → 原词号
                else:
                    n_drop += 1                   # 切点落在 E0 新增词上（无原词锚）→ 丢弃
            out.append("%s\t%s\t%s" % ("S%d" % sno,
                                       ",".join(str(g) for g in glob),
                                       ",".join(str(c) for c in cuts)))
            total += len(glob)
        with open(os.path.join(cand_dir, "chunk_%03d.tsv" % k), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(out) + "\n")

    print("vocalign 候选点归一化：块 %d / 候选点 %d" % (len(ks), total))
    if n_drop:
        print("   ℹ️ 丢弃 %d 个落在 E0 新增词上的切点（无原词锚）" % n_drop)
    if all_bad:
        print("⚠️ 跳过失败行 %d 条（该 S 号无候选 → 回填将回退纯语音权重）" % len(all_bad))
        if args.expand:
            for k, sno, why in all_bad[:30]:
                print("   %s %s：%s" % (k, "S%d" % sno if sno else "（行）", why))
    return 1 if all_bad else 0


def main():
    ap = argparse.ArgumentParser(
        description="vocalign 语义候选点：emit 清单 / check 校验 / norm 归一化（纯标准库）")
    ap.add_argument("action", choices=("emit", "check", "norm"), help="动作")
    ap.add_argument("--skeleton", required=True, help="vocalign 工作目录（含 skeleton.json）或该文件")
    ap.add_argument("--words", required=True, help="vocalign 工作目录（含 words.json）或该文件")
    ap.add_argument("--dir", default=None, help="候选点根目录（默认 <skeleton 目录>/candidates）")
    ap.add_argument("--chunks", default=None, help="分块目录（emit 用；不给则全部长句为一块）")
    ap.add_argument("--srt", default=None, help="01_subtitle_asr_fixed.srt（emit 用；解析块时间范围）")
    ap.add_argument("--e0", default=None,
                    help="E0 目录（读 long_lines.srt 的**定稿文本**；默认 <skeleton 目录>/e0）")
    ap.add_argument("--chunk", type=int, default=None, help="仅处理该块号")
    ap.add_argument("--expand", action="store_true", help="展开打印明细")
    args = ap.parse_args()

    sk_path = _file(args.skeleton, "skeleton.json")
    wd_path = _file(args.words, "words.json")
    if not os.path.isfile(sk_path):
        sys.exit("❌ 找不到 skeleton.json：%s" % sk_path)
    if not os.path.isfile(wd_path):
        sys.exit("❌ 找不到 words.json：%s" % wd_path)
    cand_dir = args.dir or os.path.join(os.path.dirname(os.path.abspath(sk_path)), DEFAULT_DIRNAME)

    _rep, sents = load_skeleton(sk_path)
    toks, n_empty = load_words_ordered(wd_path)
    loc, warns, err = locate_sentences(sents, toks)
    if err:
        sys.exit("❌ %s" % err)
    for w in warns:
        print("⚠️ %s" % w)
    if n_empty:
        print("⚠️ words.json 含空 token %d 个 —— 回填侧（跳过空 token）索引会错位，须先查采集结果"
              % n_empty)

    bounds = load_boundaries(os.path.join(os.path.dirname(os.path.abspath(sk_path)), "boundaries.txt"))
    if not bounds:
        print("⚠️ 未读到 boundaries.txt（停顿标注将为空；不影响校验与归一化）")

    e0_dir = args.e0 or os.path.join(os.path.dirname(os.path.abspath(sk_path)), "e0")
    e0_texts = load_e0_texts(e0_dir)
    texts, n_diff = build_texts(sents, e0_texts)
    if e0_texts:
        print("E0 定稿文本：%d 句（其中 %d 句与骨架原文不同 —— 仲裁修正 / 注释并入）"
              % (len(e0_texts), n_diff))
    else:
        print("⚠️ 未找到 E0 定稿（%s）→ 回退骨架原文；若已跑 E0，请传 --e0" % e0_dir)

    if args.action == "emit":
        return do_emit(args, sents, toks, bounds, loc, cand_dir, e0_texts)
    if args.action == "check":
        return do_check(args, sents, texts, cand_dir)
    return do_norm(args, sents, texts, toks, loc, cand_dir)


if __name__ == "__main__":
    sys.exit(main())
