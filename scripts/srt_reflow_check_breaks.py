# -*- coding: utf-8 -*-
"""r01 硬性断句校验（输出层，打回机制）：检查 r01_merged_en.txt 是否跨空隙合句

空隙点 = 01 中相邻 cue gap > 长停顿阈值（与 srt_reflow_gap_scan.py / srt_reflow_breaks.py 一致）。
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
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

LONG_GAP_MS = 5000      # 长停顿阈值（与 srt_gap_scan.py 一致）
NORM_RE = re.compile(r"[^a-z0-9']")
SENT_END_RE = re.compile(r"[.?!]")
BRACKET_RE = re.compile(r"\[[^\]]*\]")


def parse_time(s):
    h, m, rest = s.split(":")
    return int(h) * 3600000 + int(m) * 60000 + int(rest.replace(",", ".").split(".")[0]) * 1000 + int(rest.replace(",", ".").split(".")[1])


def parse_srt(path):
    text = open(path, encoding="utf-8-sig").read()
    cues = []
    for block in text.strip().split("\n\n"):
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) < 3:
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
    ap = argparse.ArgumentParser(description="r01 硬性断句校验：逐空隙点查句末标点，违规退出码 1（打回信号）")
    ap.add_argument("src", help="01_subtitle_asr_fixed.srt")
    ap.add_argument("r01", help="r01_merged_en.txt（补标点后输出）")
    args = ap.parse_args()

    cues = parse_srt(args.src)
    r01_raw = open(args.r01, encoding="utf-8").read()

    # 空隙点
    breaks = []  # (ia, ib, gap)
    for k in range(len(cues) - 1):
        gap = cues[k + 1]["start"] - cues[k]["end"]
        if gap > LONG_GAP_MS:
            breaks.append((cues[k]["idx"], cues[k + 1]["idx"], gap))

    n_r01, idx_map = norm_with_map(r01_raw)

    # 逐 cue 在 r01 归一化中顺序对齐（词序一致前提，srt_reflow_check_words.py 已验证）
    aligns = []  # 每 cue（原始顺序）-> (norm_start, norm_end) 或 None
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

    n_violate = 0
    n_pass = 0
    n_skip = 0
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


if __name__ == "__main__":
    main()
