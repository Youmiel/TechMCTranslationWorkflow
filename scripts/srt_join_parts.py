# -*- coding: utf-8 -*-
"""SRT 片段拼接脚本（preprocess §1.1 第一次遍历合并链路）。

把「英文预整理 subagent」各块输出的 SRT 片段（`_en_results/chunk_<k>.srt`，保留原时间码、
不增删 cue）按块序拼接成完整 01 字幕，全局段号重排。

与 text_merge.py（srt 模式）的区别：text_merge 的 srt 模式面向 translate 断句合并
（`段号|cue范围|文本` 前缀、段会合并），会丢失时间码；而第一次遍历是 1:1 cue（只改文本、
保留时间码），需保留逐 cue 时间码 —— 故用本脚本直接拼裸 SRT 片段。

时间轴精确校验（cue 数一致 + 逐 cue 时间戳与原始完全一致）仍由 `srt_check_segments.py
--cue-exact` 承担（现成工具，见 redstone-preprocess §1.1）。

用法（命令根 = Project_Main/）:
  python scripts/srt_join_parts.py <results_dir> --out <01.srt> [--chunks <chunks_dir>]
  results_dir = 各块 SRT 片段目录（`chunk_<k>.srt`，text_chunk.py 同款块号）
  --chunks    = text_chunk.py 分块目录（校验每块 cue 数 = 该块 OWNED cue 数，拦截漏/多 cue）
  --out       = 合并后的完整 SRT（全局段号重排）

示例:
  python scripts/srt_join_parts.py "_work/<视频名>/_en_results" \
      --out "_work/<视频名>/01_subtitle_asr_fixed.srt" --chunks "_work/<视频名>/_en_chunks"
"""
import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

TS_RE = re.compile(r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})")


def parse_srt_file(path):
    """解析裸 SRT → [(段号, start, end, text), ...]。文本多行合并为单行（空格连接）。"""
    with open(path, encoding="utf-8-sig") as f:
        text = f.read()
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        m_idx = re.fullmatch(r"\d+", lines[0])
        m_ts = TS_RE.fullmatch(lines[1])
        if not m_idx or not m_ts:
            continue
        body = " ".join(lines[2:])
        cues.append((int(lines[0]), m_ts.group(1), m_ts.group(2), body))
    return cues


def owned_cue_count(chunk_path):
    """text_chunk.py 块文件 OWNED 分区 cue 数（`c<idx>\\t...` 行数）。"""
    n = 0
    in_owned = False
    with open(chunk_path, encoding="utf-8") as f:
        for ln in f:
            if re.match(r"^## (BEFORE|OWNED|AFTER)", ln):
                in_owned = ln.startswith("## OWNED")
                continue
            if in_owned and re.match(r"^c\d+\t", ln):
                n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description="SRT 片段拼接（第一次遍历合并链路，全局段号重排）")
    ap.add_argument("results_dir", help="各块 SRT 片段目录（chunk_<k>.srt）")
    ap.add_argument("--out", required=True, help="合并后的完整 SRT 路径")
    ap.add_argument("--chunks", default=None, help="text_chunk.py 分块目录（校验每块 cue 数 = OWNED cue 数）")
    args = ap.parse_args()

    # 收集块片段文件
    parts = {}
    for name in sorted(os.listdir(args.results_dir)):
        m = re.match(r"chunk_(\d+)\.srt$", name)
        if m:
            parts[int(m.group(1))] = os.path.join(args.results_dir, name)
    if not parts:
        sys.exit(f"错误：{args.results_dir} 下未找到 chunk_<k>.srt 片段文件")
    ordered = sorted(parts)

    errors = []
    merged = []
    seq = 0
    prev_end = None  # (start_ms, end_ms) 时间连续性（仅告警，精确校验交 srt_check_segments --cue-exact）

    for k in ordered:
        path = parts[k]
        cues = parse_srt_file(path)
        if not cues:
            errors.append(f"块 {k}: {path} 无有效 SRT 片段")
            continue
        if args.chunks:
            chunk_path = os.path.join(args.chunks, f"chunk_{k:03d}.txt")
            if os.path.exists(chunk_path):
                expected = owned_cue_count(chunk_path)
                if len(cues) != expected:
                    errors.append(f"块 {k}: cue 数 {len(cues)} ≠ OWNED {expected}（漏/多 cue）")
        for idx, start, end, body in cues:
            seq += 1
            if body:
                merged.append(f"{seq}\n{start} --> {end}\n{body}")
            else:
                merged.append(f"{seq}\n{start} --> {end}")

    if errors:
        print("=== 拼接错误（先修块片段再重跑）===")
        for e in errors:
            print(f"- {e}")
        sys.exit(1)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n\n".join(merged) + "\n")
    print(f"已拼接 {len(merged)} 条 cue → {args.out}（共 {len(ordered)} 块）")


if __name__ == "__main__":
    main()
