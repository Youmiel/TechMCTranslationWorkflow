# -*- coding: utf-8 -*-
"""r01 硬性断句校验（输出层，打回机制）：检查 r01_merged_en.txt 是否跨空隙合句

空隙点 = 01 中相邻 cue gap > 长停顿阈值（与 srt_reflow_gap_scan.py / srt_reflow_breaks.py 一致）；
非语音标记 cue（[Music] 等，去括号后为空）两侧不参与空隙判定。
对每个空隙点 c_a → c_b：
  在 r01 中定位 c_a 的末尾字符偏移 与 c_b 的首字符偏移（全文按 cue 顺序对齐），
  检查两偏移之间的原始文本是否含句末标点（. ? !）：
    有 → 通过（空隙处已断句）；无 → 违规（跨空隙合句，打回步骤 1 重跑）。

Agent 裁决角色：
- 违规的处置：默认打回；若判定该空隙为语义停顿（语义本就连贯）可作受控例外放行，但须在 r03 不跨空隙成单元。
- 通过的复核：断句方式（独立成句 / 分段 / 归前句）由 Agent 复核，影响 r03 游离停顿词归属。

用法（命令根 = Project_Main/）：
  python scripts/srt_check_r01_breaks.py <01.srt> <r01_merged_en.txt>
退出码：0 = 全部通过；1 = 存在违规（打回信号）。
"""
import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

LONG_GAP_MS = 5000      # 长停顿阈值（与 srt_gap_scan.py 一致）
NORM_RE = re.compile(r"[^a-z0-9']")
SENT_END_RE = re.compile(r"[.?!]")
BRACKET_RE = re.compile(r"\[[^\]]*\]")


def is_pure_marker(text):
    """纯非语音标记 cue：去掉全部 [xxx] 后无可见字符（[Music]/[Applause] 等）——
    动态识别、不硬编码枚举；此类 cue 两侧不参与空隙判定"""
    return BRACKET_RE.sub("", text).strip() == ""


def parse_time(s):
    h, m, rest = s.split(":")
    return int(h) * 3600000 + int(m) * 60000 + int(rest.replace(",", ".").split(".")[0]) * 1000 + int(rest.replace(",", ".").split(".")[1])


def parse_srt(path):
    text = open(path, encoding="utf-8-sig").read()
    cues = []
    for block in text.strip().split("\n\n"):
        lines = [l for l in block.splitlines() if l.strip()]
        # 空文本 cue 只有索引行+时间行（2 行）；只要含有效时间行即保留，保证 cues 与 SRT 原始索引一一对齐
        if len(lines) < 2:
            continue
        idx = int(re.match(r"\d+", lines[0]).group())
        m = re.match(r"(\d\d:\d\d:\d\d,\d\d\d) --> (\d\d:\d\d:\d\d,\d\d\d)", lines[1])
        if not m:
            continue
        txt = " ".join(lines[2:]).strip()
        # 保留全部 cue（含 [Music] 空文本）以保原始索引；方括号标记在归一化对齐时剔除
        cues.append({"idx": idx, "start": parse_time(m.group(1)), "end": parse_time(m.group(2)), "text": txt})
    return cues


def norm_with_map(raw):
    """归一化（去非字母数字撇号、小写）+ 每个归一化字符→原文偏移 的映射"""
    norm_chars = []
    idx_map = []
    for i, ch in enumerate(raw):
        if not NORM_RE.match(ch.lower()):   # 先小写再判断（否则大写字母被当标点剔除）
            norm_chars.append(ch.lower())
            idx_map.append(i)
    return "".join(norm_chars), idx_map


def main():
    ap = argparse.ArgumentParser(description="r01 硬性断句校验：逐空隙点查句末标点，违规退出码 1（打回信号）；支持整段/块级")
    ap.add_argument("src", help="01_subtitle_asr_fixed.srt")
    ap.add_argument("r01", help="r01_merged_en.txt（整段）或 r01_results 目录（块级）")
    ap.add_argument("--chunks", default=None, help="chunks 目录（块级模式用，解析块↔cue区间）")
    ap.add_argument("--gaps", default=None, help="r00_gaps.md（可选，空隙点清单；不传则脚本自行探测，但建议复用已验证的 r00_gaps）")
    args = ap.parse_args()

    cues = parse_srt(args.src)

    # 空隙点：优先复用 r00_gaps.md（人工已验证），否则脚本自行探测
    breaks = load_breaks(args.gaps) if args.gaps else detect_breaks(cues)

    if os.path.isdir(args.r01):
        main_block(args, cues, breaks)
    else:
        main_whole(args, cues, breaks)


def detect_breaks(cues):
    """脚本自行探测空隙点（与 srt_reflow_breaks.py 一致）。"""
    breaks = []
    speech = [c for c in cues if not is_pure_marker(c["text"])]
    for k in range(len(speech) - 1):
        gap = speech[k + 1]["start"] - speech[k]["end"]
        if gap > LONG_GAP_MS:
            breaks.append((speech[k]["idx"], speech[k + 1]["idx"], gap))
    return breaks


def load_breaks(gaps_path):
    """从 r00_gaps.md 解析空隙点清单：`c<ia> → c<ib>（<gap>s）`。返回 [(ia, ib, gap_ms), ...]。"""
    breaks = []
    for ln in open(gaps_path, encoding="utf-8").read().split("\n"):
        m = re.match(r"###?\s*\d+\.\s*c(\d+)\s*→\s*c(\d+)\s*（([\d.]+)s）", ln)
        if m:
            breaks.append((int(m.group(1)), int(m.group(2)), int(float(m.group(3)) * 1000)))
    return breaks


def main_whole(args, cues, breaks):
    """整段模式：r01 为完整文本，在全文定位 cue 检查空隙点断句。"""
    r01_raw = open(args.r01, encoding="utf-8").read()
    n_r01, idx_map = norm_with_map(r01_raw)
    aligns = []  # 每 cue -> (norm_start, norm_end) 或 None
    cursor = 0
    for c in cues:
        n = NORM_RE.sub("", BRACKET_RE.sub("", c["text"]).lower())
        if not n:
            aligns.append(None)
            continue
        p = n_r01.find(n, cursor)
        if p == -1:
            aligns.append(None)
            continue
        aligns.append((p, p + len(n) - 1))
        cursor = p + len(n)

    print(f"r01: {args.r01}  空隙点: {len(breaks)} 处（长停顿 >{LONG_GAP_MS/1000:.0f}s）")
    print("-" * 60)
    n_violate, n_pass, n_skip = 0, 0, 0
    for ia, ib, gap in breaks:
        ra = aligns[ia - 1]
        rb = aligns[ib - 1]
        if ra is None or rb is None:
            n_skip += 1
            print(f"❓ c{ia}→c{ib}（{gap/1000:.1f}s）: 未能定位 cue 文本，跳过校验")
            continue
        raw_a_end = idx_map[ra[1]]
        raw_b_start = idx_map[rb[0]]
        between = r01_raw[raw_a_end + 1:raw_b_start]
        a_text = cues[ia - 1]["text"]
        b_text = cues[ib - 1]["text"]
        if SENT_END_RE.search(between):
            n_pass += 1
            print(f"✅ c{ia}→c{ib}（{gap/1000:.1f}s）: 已断句  `…{a_text[-20:]}` [句末标点] `{b_text[:20]}…`")
            print(f"   复核: 断句方式是否合理（独立成句 / 分段 / 归前句）——影响 r03 游离停顿词归属，见 r01_breaks.md 复核清单")
        else:
            n_violate += 1
            gap_snippet = between.strip()
            print(f"❌ c{ia}→c{ib}（{gap/1000:.1f}s）: 跨空隙合句（两锚间无句末标点，仅 {repr(gap_snippet[:60])}）")
            print(f"   前 cue c{ia}: `{a_text}`")
            print(f"   后 cue c{ib}: `{b_text}`")
            print(f"   → 默认处置: 打回步骤 1，用 r01_breaks.md 的补标点输入文本重跑（空隙标记处强制断句）")
            print(f"   受控例外: 若你判定该空隙为语义停顿（非剪辑跳转、语义本就连贯），可放行——")
            print(f"   但须在 r03 分句对应时确保不跨空隙成单元，并在 r04 告警对照中记录（与 r00_gaps.md 对照）")
    print("-" * 60)
    print(f"结果: 通过 {n_pass} / 违规 {n_violate} / 未定位 {n_skip}（共 {len(breaks)}）")
    if n_violate:
        print("❌ 存在跨空隙合句 —— r01 需打回步骤 1 重跑（硬性断句）")
        sys.exit(1)
    if n_skip:
        print("⚠️ 存在未定位空隙点，建议人工核对")
    print("✅ r01 硬性断句校验通过（所有空隙点均已断句）")


def main_block(args, cues, breaks):
    """块级模式：r01_results 为逐块补标点结果；空隙点两侧 cue 应落在相邻块边界处。
    检查前块 OWNED 末尾与后块 OWNED 开头之间是否断句。"""
    results_dir = args.r01
    if not args.chunks:
        sys.exit("块级模式需要 --chunks <chunks目录>（解析块↔cue区间）")
    # 解析各块的 cue 区间
    chunk_files = {}
    for fn in sorted(os.listdir(args.chunks)):
        m = re.fullmatch(r"chunk_(\d{3})\.txt", fn)
        if m:
            chunk_files[int(m.group(1))] = os.path.join(args.chunks, fn)
    block_cues = {}  # k -> (min_c, max_c)
    for k, fp in chunk_files.items():
        cids = []
        in_owned = False
        for ln in open(fp, encoding="utf-8").read().split("\n"):
            if ln.startswith("## OWNED"):
                in_owned = True
                continue
            if ln.startswith("## CONTEXT"):
                in_owned = False
                continue
            if in_owned:
                mm = re.match(r"c(\d+)\t", ln)
                if mm:
                    cids.append(int(mm.group(1)))
        if cids:
            block_cues[k] = (min(cids), max(cids))

    print(f"r01_results: {args.r01}  空隙点: {len(breaks)} 处")
    print("-" * 60)
    n_violate, n_pass, n_skip = 0, 0, 0
    for ia, ib, gap in breaks:
        # 找含 c_ia 的块 与 含 c_ib 的块
        ka = kb = None
        for k, (cmin, cmax) in block_cues.items():
            if cmin <= ia <= cmax:
                ka = k
            if cmin <= ib <= cmax:
                kb = k
        if ka is None or kb is None:
            n_skip += 1
            print(f"❓ c{ia}→c{ib}（{gap/1000:.1f}s）: 未找到含该 cue 的块（块↔cue 映射缺失），跳过")
            continue
        # 读前块结果末尾 + 后块结果开头
        res_a = os.path.join(results_dir, "chunk_%03d.txt" % ka)
        res_b = os.path.join(results_dir, "chunk_%03d.txt" % kb)
        if not os.path.exists(res_a) or not os.path.exists(res_b):
            n_skip += 1
            print(f"❓ c{ia}→c{ib}: 块结果缺失（chunk_{ka:03d} / chunk_{kb:03d}），跳过")
            continue
        text_a = open(res_a, encoding="utf-8").read().strip()
        text_b = open(res_b, encoding="utf-8").read().strip()
        # 前块末尾最后一个句末标点之后到后块开头：检查块边界处衔接
        # 简化：前块末尾字符 + 后块开头字符拼接，看块边界附近是否断句
        tail = text_a[-30:] if len(text_a) >= 30 else text_a
        head = text_b[:30] if len(text_b) >= 30 else text_b
        boundary = tail + "\n" + head
        a_text = cues[ia - 1]["text"]
        b_text = cues[ib - 1]["text"]
        # 块级：空隙点应在块边界处（块边界优先在空隙点）；检查前块是否以句末标点结尾
        ends_punct = bool(SENT_END_RE.search(text_a.rstrip()[-8:])) if text_a else False
        if ends_punct:
            n_pass += 1
            print(f"✅ c{ia}→c{ib}（{gap/1000:.1f}s）: 前块以句末标点结尾（chunk_{ka:03d}→chunk_{kb:03d}）  `…{a_text[-20:]}` | `{b_text[:20]}…`")
        else:
            n_violate += 1
            print(f"❌ c{ia}→c{ib}（{gap/1000:.1f}s）: 前块末尾无句末标点（chunk_{ka:03d}→chunk_{kb:03d}）")
            print(f"   前 cue c{ia}: `{a_text}`  |  后 cue c{ib}: `{b_text}`")
            print(f"   边界片段: ...{repr(tail[-20:])} | {repr(head[:20])}...")
            print(f"   → 默认处置: 打回该块重跑（空隙标记处强制断句）；语义停顿可作受控例外，须 r03 不跨空隙成单元")
    print("-" * 60)
    print(f"结果: 通过 {n_pass} / 违规 {n_violate} / 未定位 {n_skip}（共 {len(breaks)}）")
    if n_violate:
        print("❌ 存在跨空隙合句 —— 打回对应块重跑（硬性断句）")
        sys.exit(1)
    if n_skip:
        print("⚠️ 存在未定位空隙点，建议人工核对")
    print("✅ r01 硬性断句校验通过（所有空隙点均已断句）")


if __name__ == "__main__":
    main()
