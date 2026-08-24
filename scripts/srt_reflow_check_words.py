# -*- coding: utf-8 -*-
"""r01 措辞校验：r01 词序列 == 01 词序列（剔除 [Music]/[Applause] 等非语音标记），验证"不得改动措辞"硬约束

回填工作流（reflow-redstone）步骤 1：LLM 合并补标点后，词序列必须与 01 一致（只加标点、不改措辞）。

块级模式（产物单轨）：<01.srt> <r01_results目录> --chunks <chunks目录>——逐块对比（块 ↔ 01 cue 区间由 chunks 块头解析；单块亦适用）。
差异定位：difflib 一次列出全部分歧（错词/缺词/多词），不再只报第一处；默认每处一行摘要，--expand 展开每处的上下文/行号/cue 定位。
整段模式（<01.srt> <r01_merged_en.txt>）保留兼容历史产物，同样一次列出全部分歧。

用法（命令根 = Project_Main/）：
  python scripts/srt_reflow_check_words.py <01.srt> <r01_results/> --chunks <chunks/>            # 块级（--chunks 必填）
  python scripts/srt_reflow_check_words.py <01.srt> <r01_results/> --chunks <chunks/> --expand  # 块级：展开每处分歧的上下文/行号/cue 定位（默认每处一行摘要）
退出码：0 = 一致；1 = 存在分歧。
"""
import argparse
import difflib
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

from srt_reflow_common import auto_wrap_file, collect_chunk_files, ctx_snippet, is_pure_marker, parse_owned_cue_range, strip_stitch_marks, MAX_LINE


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


def main():
    ap = argparse.ArgumentParser(description="r01 措辞校验：词序列与 01 一致（不得改动措辞）；块级模式（--chunks 必填）")
    ap.add_argument("srt", help="01_subtitle_asr_fixed.srt")
    ap.add_argument("r01", help="r01_results 目录（块级，--chunks 必填；单块亦适用）")
    ap.add_argument("--chunks", default=None, help="chunks 目录（块级模式必填，解析块↔cue区间；单块亦适用）")
    ap.add_argument("--verbose", action="store_true", help="展开打印全部通过项（默认折叠计数）")
    ap.add_argument("--expand", action="store_true", help="展开每处分歧的详细上下文/行号/cue 定位（默认每处一行摘要）")
    args = ap.parse_args()

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
        for k in sorted(chunks):
            rng = parse_owned_cue_range(chunks[k])
            if rng is None:
                print(f"⚠️ chunk_{k:03d}: 无 OWNED cue，跳过")
                continue
            cmin, cmax = rng
            # 01 对应 cue 段的词（剔除标记）
            srt_terms = []
            for i in range(cmin, cmax + 1):
                body = cue_map.get(i, "")
                if body:
                    srt_terms.extend(re.findall(r"[a-z0-9']+", body.lower()))
            # 块结果文件（剥离跨块句标记【承接句】/【延伸句】后再提词——标记内容为邻块补全，非本块 OWNED cue）
            res_path = os.path.join(args.r01, "chunk_%03d.txt" % k)
            if not os.path.exists(res_path):
                print(f"❌ chunk_{k:03d}: 无结果文件")
                n_err += 1
                continue
            raw = open(res_path, encoding="utf-8").read()
            has_stitch = ("【承接句】" in raw) or ("【延伸句】" in raw)
            r01_terms = re.findall(r"[a-z0-9']+", strip_stitch_marks(raw).lower())
            if srt_terms == r01_terms:
                n_ok += 1
                if args.verbose:
                    print(f"✅ chunk_{k:03d} (c{cmin}-c{cmax}): 词序列一致（{len(srt_terms)} 词）")
            elif has_stitch and len(r01_terms) < len(srt_terms) and all(w in srt_terms for w in r01_terms):
                n_ok += 1
                if args.verbose:
                    print(f"✅ chunk_{k:03d} (c{cmin}-c{cmax}): 缺 {len(srt_terms) - len(r01_terms)} 词——"
                          f"跨块句标记【承接句】/【延伸句】内含本块部分，归位时确认")
            else:
                n_err += 1
                entries = word_diff_entries(srt_terms, r01_terms)
                n_diff = len(entries)
                print(f"❌ chunk_{k:03d} (c{cmin}-c{cmax}): 词序列分歧 {n_diff} 处（01={len(srt_terms)} r01={len(r01_terms)}）")
                # 一次列出全部问题（默认每处一行摘要；--expand 展开详情）
                for idx, e in enumerate(entries, 1):
                    print(f"   [{idx}/{n_diff}] {diff_describe(e)}")
                if n_diff and not args.expand:
                    print(f"   （用 --expand 展开每处的上下文/行号/cue 定位）")
                if args.expand:
                    stripped = strip_stitch_marks(raw)
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
    for idx, e in enumerate(entries, 1):
        print(f"  [{idx}/{n_diff}] {diff_describe(e)}")
    if n_diff and not args.expand:
        print("  （用 --expand 展开每处详细上下文）")
    if args.expand:
        for idx, (tag, i1, i2, j1, j2, a, b) in enumerate(entries, 1):
            print(f"  ── [{idx}/{n_diff}] {diff_describe((tag, i1, i2, j1, j2, a, b))} ──")
            ctx1 = " ".join(w1[max(0, i1 - 4):i2 + 5])
            ctx2 = " ".join(w2[max(0, j1 - 4):j2 + 5])
            print(f"  01 上下文: ...{ctx1}...")
            print(f"  r01 上下文: ...{ctx2}...")
    sys.exit(1)


if __name__ == "__main__":
    main()

