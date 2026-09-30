# -*- coding: utf-8 -*-
"""r01 措辞校验：r01 词序列 == 01 词序列（剔除 [Music]/[Applause] 等非语音标记），验证"不得改动措辞"硬约束

回填工作流（reflow-redstone）步骤 1：LLM 合并补标点后，词序列必须与 01 一致（只加标点、不改措辞）。

块级模式（产物单轨）：<01.srt> <r01_results目录> --chunks <chunks目录>——逐块对比（块 ↔ 01 cue 区间由 chunks 块头解析；单块亦适用）。
差异定位：difflib 一次列出全部分歧（错词/缺词/多词），不再只报第一处。
统一反馈：默认只输出「问题数目 + 提示」（各问题块一行统计，不输出错误内容/上下文）；--expand 展开每处的上下文/行号/cue 定位；
--chunk <k> 只校验单块并默认展开该块详情（修复单块时防其他块报错占用上下文）。
整段模式（<01.srt> <r01_merged_en.txt>）保留兼容历史产物，同样一次列出全部分歧。

用法（命令根 = Project_Main/）：
  python scripts/srt_reflow_check_words.py <01.srt> <r01_results/> --chunks <chunks/>            # 块级（--chunks 必填）：默认只给问题数
  python scripts/srt_reflow_check_words.py <01.srt> <r01_results/> --chunks <chunks/> --expand  # 块级：展开每处分歧的上下文/行号/cue 定位
  python scripts/srt_reflow_check_words.py <01.srt> <r01_results/> --chunks <chunks/> --chunk 3 # 只查 chunk_003（默认展开该块详情）
退出码：0 = 一致；1 = 存在分歧。
"""
import argparse
import difflib
import os
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

from shared.srt_common import auto_wrap_file, collect_chunk_files, ctx_snippet, is_pure_marker, parse_owned_cue_range, strip_stitch_marks, MAX_LINE


def srt_words(path):
    raw = open(path, encoding="utf-8-sig").read()
    texts = []
    for block in raw.split("\n\n"):
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        body = " ".join(lines[2:])
        # 非语音 cue 剔除：方括号标记（is_pure_marker 动态识别，[Music]/[Applause] 等）
        if is_pure_marker(body):
            continue
        texts.append(body)
    joined = " ".join(texts)
    return re.findall(r"[a-z0-9']+", joined.lower())


def txt_words(path):
    raw = strip_stitch_marks(open(path, encoding="utf-8").read())
    return re.findall(r"[a-z0-9']+", raw.lower())


def parse_srt(path):
    """返回 [(idx, text), ...]（含 [Music] 等标记，供块级模式按 cue 区间取词）。"""
    raw = open(path, encoding="utf-8-sig").read()
    cues = []
    for block in raw.strip().split("\n\n"):
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) < 3:
            continue
        m = re.match(r"\d+", lines[0])
        if not m:
            continue
        body = " ".join(lines[2:]).strip()
        # 非语音 cue 剔除：方括号标记（is_pure_marker 动态识别，[Music]/[Applause] 等）
        if is_pure_marker(body):
            body = ""
        cues.append((int(m.group()), body))
    return cues


def word_diff_entries(srt, r01):
    """difflib 找出 srt 与 r01 词序列的全部分歧（一次发现多处错词/缺词/多词）。
    返回 [(tag, i1, i2, j1, j2, a_slice, b_slice), ...]；tag ∈ replace/delete/insert。"""
    sm = difflib.SequenceMatcher(None, srt, r01, autojunk=False)
    return [(tag, i1, i2, j1, j2, srt[i1:i2], r01[j1:j2])
            for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal"]


def diff_describe(entry):
    """分歧条目的单行描述（供折叠/展开两种模式复用）。"""
    tag, i1, i2, j1, j2, a, b = entry
    if tag == "replace" and len(a) == 1 and len(b) == 1:
        return f"第 {i1} 词: 01=[{a[0]}] r01=[{b[0]}]"
    if tag == "replace":
        return f"01[{i1}:{i2}]={{{' '.join(a) or '∅'}}} ↔ r01[{j1}:{j2}]={{{' '.join(b) or '∅'}}}"
    if tag == "delete":
        return f"01 独有 01[{i1}:{i2}]={{{' '.join(a)}}}（r01 缺 {len(a)} 词）"
    return f"r01 独有 r01[{j1}:{j2}]={{{' '.join(b)}}}（01 缺 {len(b)} 词）"


def _multi_diff(a, b):
    """a 相对 b 多出的元素（保序、计重复次数）。"""
    cb = Counter(b)
    out = []
    for w in a:
        if cb[w] > 0:
            cb[w] -= 1
        else:
            out.append(w)
    return out


def _shift_parts(st, rt):
    """位置感知差异片段：(extra, missing)，各为「单一连续词段」（空 list 表示无）。

    返回 None = 非单一连续差异（多处不连续 / 含替换），即非衔接归位所致。
    extra = rt 相对 st 多出的词（本块多写）；missing = st 相对 rt 多出的词（本块少写）。

    与 `_multi_diff`（多重集差、位置无关）的区别：多重集差在跨块句含高频词（is/the/you 等）
    时会被邻段同名词**错位吸收**，导致「前块多出」与「后块缺失」判为不等（假阳性打回）；
    此处按序列位置对齐，归位的「前块尾部多出 / 后块头部缺失」必然落在同一连续段上。
    """
    sm = difflib.SequenceMatcher(None, st, rt, autojunk=False)
    extra, missing = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if tag == "insert":
            extra.append(rt[j1:j2])
        elif tag == "delete":
            missing.append(st[i1:i2])
        else:                        # replace：出现替换 = 真措辞分歧
            return None
    if len(extra) > 1 or len(missing) > 1:
        return None                  # 多处不连续差异 = 非归位所致
    return (extra[0] if extra else [], missing[0] if missing else [])


def cross_chunk_note(k, cache):
    """块 k 与相邻块的词差异是否恰好互补（= 跨块句衔接归位的正常结果）。

    背景（配合 `srt_reflow2_stitch.py`）：块边界常落句中，跨块句由补标点 agent
    在两侧各补全一次；**衔接归位**把该句整体留给前块（后块整句删除）→ 前块比自己的 cue 区间
    **多**出该句的部分词、后块**少**同样这些词。此处判定「多出的词 == 邻块缺失的词」即放行。
    返回人类可读说明或 None（非互补 = 真分歧）。
    """
    if k not in cache:
        return None
    st, rt = cache[k]
    # ① 位置感知判定（首选）：单一连续词段——归位后「前块尾部多出 == 后块头部缺失」或反向
    parts = _shift_parts(st, rt)
    if parts is not None:
        extra_p, missing_p = parts
        if len(extra_p) <= 40 and len(missing_p) <= 40:
            if extra_p and not missing_p:
                nxt = cache.get(k + 1)
                if nxt:
                    np = _shift_parts(nxt[0], nxt[1])
                    if np is not None and not np[0] and np[1] == extra_p:
                        return f"本块多出 {len(extra_p)} 词，恰为块{k+1}所缺（前块保留完整句）"
            if missing_p and not extra_p:
                prv = cache.get(k - 1)
                if prv:
                    pp = _shift_parts(prv[0], prv[1])
                    if pp is not None and not pp[1] and pp[0] == missing_p:
                        return f"本块缺 {len(missing_p)} 词，恰为块{k-1}多出（后块删除重复句）"
    # ② 兜底：多重集差（保留原行为；跨块句含高频词时可能错位，故仅作后备）
    extra = _multi_diff(rt, st)      # 本块相对 01 多出的词
    missing = _multi_diff(st, rt)    # 本块相对 01 缺失的词
    if len(extra) > 40 or len(missing) > 40:
        return None                  # 差异过大 = 非归位所致
    if extra and not missing:
        nxt = cache.get(k + 1)
        if nxt and _multi_diff(nxt[0], nxt[1]) == extra:
            return f"本块多出 {len(extra)} 词，恰为块{k+1}所缺（前块保留完整句）"
    if missing and not extra:
        prv = cache.get(k - 1)
        if prv and _multi_diff(prv[1], prv[0]) == missing:
            return f"本块缺 {len(missing)} 词，恰为块{k-1}多出（后块删除重复句）"
    if extra and missing:
        nxt, prv = cache.get(k + 1), cache.get(k - 1)
        if nxt and prv and _multi_diff(nxt[0], nxt[1]) == extra and _multi_diff(prv[1], prv[0]) == missing:
            return f"前接块{k-1}、后送块{k+1}（双向归位边界）"
    return None


def main():
    ap = argparse.ArgumentParser(description="r01 措辞校验：词序列与 01 一致（不得改动措辞）；块级模式（--chunks 必填）")
    ap.add_argument("srt", help="01_subtitle_asr_fixed.srt")
    ap.add_argument("r01", help="r01_results 目录（块级，--chunks 必填；单块亦适用）")
    ap.add_argument("--chunks", default=None, help="chunks 目录（块级模式必填，解析块↔cue区间；单块亦适用）")
    ap.add_argument("--verbose", action="store_true", help="展开打印全部通过项（默认折叠计数）")
    ap.add_argument("--expand", action="store_true", help="展开每处分歧的详细上下文/行号/cue 定位（默认只给问题数+提示）")
    ap.add_argument("--chunk", type=int, default=None, metavar="k",
                    help="只校验指定块（chunk_<k>.txt，如 --chunk 3）；单块模式默认展开该块详情（修复单块时防其他块报错占用上下文）")
    args = ap.parse_args()
    expand = args.expand or args.chunk is not None  # 单块模式默认展开（只查一块，输出量小且是修复目标）

    if os.path.isdir(args.r01):
        # 块级模式
        if not args.chunks:
            sys.exit("块级模式需要 --chunks <chunks目录>（解析块↔cue区间）")
        cues = parse_srt(args.srt)
        cue_map = {idx: body for idx, body in cues}
        # 收集块文件
        chunks = collect_chunk_files(args.chunks)
        # 单行上限处理：超长单行 read_file 不可读 → 就地折行重排（折行非语义分行，校验按整段解析不受影响；不消耗 subagent token）
        n_wrapped = 0
        for k in sorted(chunks):
            p = os.path.join(args.r01, "chunk_%03d.txt" % k)
            if os.path.exists(p) and auto_wrap_file(p, MAX_LINE):
                n_wrapped += 1
                print(f"   ↻ 自动折行重排 chunk_{k:03d}")
        if n_wrapped:
            print(f"   ✅ 已就地折行 {n_wrapped} 个块文件（显示性换行非语义分行，继续校验）")
        n_err = 0
        n_ok = 0
        # 预收集每块 (01 词, r01 词)——跨块句归位互补判定需相邻块数据
        terms_cache = {}
        for _k in sorted(chunks):
            _rng = parse_owned_cue_range(chunks[_k])
            if _rng is None:
                continue
            _st = []
            for _i in range(_rng[0], _rng[1] + 1):
                _b = cue_map.get(_i, "")
                if _b:
                    _st.extend(re.findall(r"[a-z0-9']+", _b.lower()))
            _rp = os.path.join(args.r01, "chunk_%03d.txt" % _k)
            if not os.path.exists(_rp):
                continue
            _raw = open(_rp, encoding="utf-8").read()
            terms_cache[_k] = (_st, re.findall(r"[a-z0-9']+", strip_stitch_marks(_raw).lower()))
        if args.chunk is not None and args.chunk not in chunks:
            sys.exit(f"❌ --chunk {args.chunk}: chunks 目录无该块（可用块: {sorted(chunks)}）")
        to_check = [args.chunk] if args.chunk is not None else sorted(chunks)
        for k in to_check:
            rng = parse_owned_cue_range(chunks[k])
            if rng is None:
                print(f"⚠️ chunk_{k:03d}: 无 OWNED cue，跳过")
                continue
            cmin, cmax = rng
            # 块结果文件（剥跨块句标记【承接句】/【延伸句】后提词——标记内容为邻块补全，非本块 OWNED cue）
            res_path = os.path.join(args.r01, "chunk_%03d.txt" % k)
            if not os.path.exists(res_path):
                print(f"❌ chunk_{k:03d}: 无结果文件")
                n_err += 1
                continue
            raw = open(res_path, encoding="utf-8").read()
            has_stitch = ("【承接句】" in raw) or ("【延伸句】" in raw)
            srt_terms, r01_terms = terms_cache.get(k, ([], []))
            xnote = cross_chunk_note(k, terms_cache)
            if srt_terms == r01_terms:
                n_ok += 1
                if args.verbose:
                    print(f"✅ chunk_{k:03d} (c{cmin}-c{cmax}): 词序列一致（{len(srt_terms)} 词）")
            elif has_stitch and len(r01_terms) < len(srt_terms) and all(w in srt_terms for w in r01_terms):
                n_ok += 1
                if args.verbose:
                    print(f"✅ chunk_{k:03d} (c{cmin}-c{cmax}): 缺 {len(srt_terms) - len(r01_terms)} 词——"
                          f"跨块句标记【承接句】/【延伸句】内含本块部分，归位时确认")
            elif xnote:
                n_ok += 1
                print(f"✅ chunk_{k:03d} (c{cmin}-c{cmax}): 跨块句归位互补——{xnote}")
            else:
                n_err += 1
                entries = word_diff_entries(srt_terms, r01_terms)
                n_diff = len(entries)
                print(f"❌ chunk_{k:03d} (c{cmin}-c{cmax}): 词序列分歧 {n_diff} 处（01={len(srt_terms)} r01={len(r01_terms)}）")
                # 统一反馈：默认只给问题数；--expand / 单块（--chunk）展开每处详情
                if expand:
                    stripped = strip_stitch_marks(raw)
                    for idx, e in enumerate(entries, 1):
                        print(f"   [{idx}/{n_diff}] {diff_describe(e)}")
                    for idx, (tag, i1, i2, j1, j2, a, b) in enumerate(entries, 1):
                        print(f"   ── [{idx}/{n_diff}] {diff_describe((tag, i1, i2, j1, j2, a, b))} ──")
                        # 01/r01 词级上下文并列（±6 词，措辞差异一眼可辨）
                        ctx1 = " ".join(srt_terms[max(0, i1 - 6):i2 + 8])
                        ctx2 = " ".join(r01_terms[max(0, j1 - 6):j2 + 8])
                        print(f"   01 上下文: ...{ctx1}...")
                        print(f"   r01 上下文: ...{ctx2}...")
                        # r01 定位：剥离跨块句标记后定位（避免定位到邻块补全的标记内容）+ 行号供直接编辑
                        anchor = (b[0] if b else a[0])
                        pos = stripped.lower().find(anchor)
                        if pos != -1:
                            ln, frag = ctx_snippet(stripped, pos)
                            print(f"   {os.path.basename(res_path)} 行 {ln}｜{frag}")
                        else:
                            print(f"   {os.path.basename(res_path)}: 未定位到分歧词（缺词/改写，需打开块核对）")
                        # 01 定位：按累计词数定位到分歧词所在 cue（避免重复词误定位）
                        if i1 < len(srt_terms):
                            c = None
                            acc = 0
                            for cc in range(cmin, cmax + 1):
                                body = cue_map.get(cc, "")
                                if body:
                                    ws = re.findall(r"[a-z0-9']+", body.lower())
                                    if acc + len(ws) > i1:
                                        c = cc
                                        break
                                    acc += len(ws)
                            if c:
                                print(f"   01 cue c{c}: `{cue_map.get(c, '')}`")
        if n_err:
            print(f"\n❌ 块级措辞校验失败：{n_err} 块异常（打回）")
            if not expand:
                print("   提示：--expand 展开每处详细上下文；--chunk <k> 只查单个块（修复单块时防其他块报错占用上下文）")
            sys.exit(1)
        print(f"\n✅ 块级措辞校验通过：{n_ok} 块词序列一致（含跨块句标记块）")
        return

    # 整段模式
    w1 = srt_words(args.srt)
    w2 = txt_words(args.r01)
    print(f"01 词数: {len(w1)}  r01 词数: {len(w2)}")
    if w1 == w2:
        print("✅ 词序列完全一致（含顺序）")
        return
    # 一次性列出所有分歧（difflib 同时发现错词/缺词/多词，不再只报第一处）
    entries = word_diff_entries(w1, w2)
    n_diff = len(entries)
    print(f"❌ 词序列分歧 {n_diff} 处（01={len(w1)} r01={len(w2)}）")
    if args.expand:
        for idx, e in enumerate(entries, 1):
            print(f"  [{idx}/{n_diff}] {diff_describe(e)}")
        for idx, (tag, i1, i2, j1, j2, a, b) in enumerate(entries, 1):
            print(f"  ── [{idx}/{n_diff}] {diff_describe((tag, i1, i2, j1, j2, a, b))} ──")
            ctx1 = " ".join(w1[max(0, i1 - 4):i2 + 5])
            ctx2 = " ".join(w2[max(0, j1 - 4):j2 + 5])
            print(f"  01 上下文: ...{ctx1}...")
            print(f"  r01 上下文: ...{ctx2}...")
    else:
        print("  （用 --expand 展开每处详细上下文）")
    sys.exit(1)


if __name__ == "__main__":
    main()

