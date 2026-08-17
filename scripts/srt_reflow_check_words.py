# -*- coding: utf-8 -*-
"""r01 措辞校验：r01 词序列 == 01 词序列（剔除 [Music]/[Applause] 非语音标记），验证"不得改动措辞"硬约束

回填工作流（reflow-redstone）步骤 1：LLM 合并补标点后，词序列必须与 01 一致（只加标点、不改措辞）。

块级模式（产物单轨）：<01.srt> <r01_results目录> --chunks <chunks目录>——逐块对比（块 ↔ 01 cue 区间由 chunks 块头解析；单块亦适用）。整段模式（<01.srt> <r01_merged_en.txt>）保留兼容历史产物。

用法（命令根 = Project_Main/）：
  python scripts/srt_check_r01.py <01.srt> <r01_results/> --chunks <chunks/>   # 块级（--chunks 必填）
退出码：0 = 一致；1 = 存在分歧。
"""
import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

from srt_reflow_common import auto_wrap_file, collect_chunk_files, ctx_snippet, parse_owned_cue_range, strip_stitch_marks, MAX_LINE


def srt_words(path):
    raw = open(path, encoding="utf-8-sig").read()
    texts = []
    for block in raw.split("\n\n"):
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        body = " ".join(lines[2:])
        if body.strip() in ("[Music]", "[Music] ", "[Applause]", "[Applause] "):
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
        if body.strip() in ("[Music]", "[Music] ", "[Applause]", "[Applause] "):
            body = ""
        cues.append((int(m.group()), body))
    return cues


def main():
    ap = argparse.ArgumentParser(description="r01 措辞校验：词序列与 01 一致（不得改动措辞）；块级模式（--chunks 必填）")
    ap.add_argument("srt", help="01_subtitle_asr_fixed.srt")
    ap.add_argument("r01", help="r01_results 目录（块级，--chunks 必填；单块亦适用）")
    ap.add_argument("--chunks", default=None, help="chunks 目录（块级模式必填，解析块↔cue区间；单块亦适用）")
    ap.add_argument("--verbose", action="store_true", help="展开打印全部通过项（默认折叠计数）")
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
                print(f"❌ chunk_{k:03d} (c{cmin}-c{cmax}): 词序列分歧（01={len(srt_terms)} r01={len(r01_terms)}）")
                diff_i = next((i for i, (a, b) in enumerate(zip(srt_terms, r01_terms)) if a != b),
                              min(len(srt_terms), len(r01_terms)))
                a = srt_terms[diff_i] if diff_i < len(srt_terms) else "—"
                b = r01_terms[diff_i] if diff_i < len(r01_terms) else "—"
                print(f"    第 {diff_i} 词: 01=[{a}] r01=[{b}]")
                # r01 定位：分歧词在 r01 原文中的行号 + 上下文（供直接编辑）
                anchor = b if b != "—" else a
                pos = raw.lower().find(anchor)
                if pos != -1:
                    ln, frag = ctx_snippet(raw, pos)
                    print(f"    {os.path.basename(res_path)} 行 {ln}｜{frag}")
                else:
                    print(f"    {os.path.basename(res_path)}: 未定位到分歧词（缺词/改写，需打开块核对）")
                # 01 定位：分歧词对应 cue
                if diff_i < len(srt_terms):
                    c = None
                    for cc in range(cmin, cmax + 1):
                        body = cue_map.get(cc, "")
                        if body and srt_terms[:diff_i + 1][-1] in re.findall(r"[a-z0-9']+", body.lower()):
                            c = cc
                            break
                    if c:
                        print(f"    01 cue c{c}: `{cue_map.get(c, '')}`")
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
    # 定位第一处分歧
    for i, (a, b) in enumerate(zip(w1, w2)):
        if a != b:
            ctx1 = " ".join(w1[max(0, i - 4):i + 5])
            ctx2 = " ".join(w2[max(0, i - 4):i + 5])
            print(f"❌ 第 {i} 词分歧: 01=[{a}] r01=[{b}]")
            print(f"  01 上下文: ...{ctx1}...")
            print(f"  r01 上下文: ...{ctx2}...")
            print(f"  01 长度 {len(w1)} / r01 长度 {len(w2)}")
            sys.exit(1)
    # 前缀一致，长度不同
    print(f"⚠️ 前缀一致但长度不同（01={len(w1)} r01={len(w2)}）")
    extra1 = " ".join(w1[len(w2):][:15])
    extra2 = " ".join(w2[len(w1):][:15])
    if extra1:
        print(f"  01 多出: ...{extra1}")
    if extra2:
        print(f"  r01 多出: ...{extra2}")
    sys.exit(1)


if __name__ == "__main__":
    main()

