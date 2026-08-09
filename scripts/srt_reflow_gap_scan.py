# -*- coding: utf-8 -*-
"""空隙探测（回填工作流前置）：扫描 01 的 cue 时间戳，生成 r00_gaps.md

供 reflow-redstone 步骤 1 合并补标点前参考——大空隙 = 强制分割点提示（不跨空隙合句）。
阈值与 reflow-redstone SKILL 一致：长停顿 >5s；剪辑跳转 >10s。

用法（命令根 = Project_Main/）：
  python scripts/srt_gap_scan.py <01.srt> [-o reflow/r00_gaps.md]
"""
import argparse
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

LONG_GAP_MS = 5000      # 长停顿阈值（与步骤 2/5 一致）
JUMP_GAP_MS = 10000     # 剪辑跳转阈值


def parse_time(s):
    h, m, rest = s.split(":")
    return int(h) * 3600000 + int(m) * 60000 + int(rest.replace(",", ".").split(".")[0]) * 1000 + int(rest.replace(",", ".").split(".")[1])


def fmt(ms):
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, msr = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{msr:03d}"


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
        cues.append({"idx": idx, "start": parse_time(m.group(1)), "end": parse_time(m.group(2)), "text": txt})
    return cues


def main():
    ap = argparse.ArgumentParser(description="空隙探测：扫描 01 时间戳，生成 r00_gaps.md")
    ap.add_argument("src", help="01_subtitle_asr_fixed.srt")
    ap.add_argument("-o", dest="out", default="reflow/r00_gaps.md", help="输出 r00_gaps.md（默认 reflow/r00_gaps.md）")
    args = ap.parse_args()

    cues = parse_srt(args.src)
    gaps = []  # (gap_ms, idx_a, idx_b, a_end, b_start, a_text, b_text, is_jump)
    for k in range(len(cues) - 1):
        gap = cues[k + 1]["start"] - cues[k]["end"]
        if gap > LONG_GAP_MS:
            gaps.append((gap, cues[k]["idx"], cues[k + 1]["idx"],
                         cues[k]["end"], cues[k + 1]["start"],
                         cues[k]["text"], cues[k + 1]["text"],
                         gap > JUMP_GAP_MS))
    gaps.sort(key=lambda g: -g[0])

    lines = []
    lines.append(f"# r00 空隙探测报告 — {args.src}")
    lines.append("")
    lines.append(f"- 输入: `{args.src}`（{len(cues)} cue）")
    lines.append(f"- 阈值: 长停顿 >{LONG_GAP_MS/1000:.0f}s；剪辑跳转 >{JUMP_GAP_MS/1000:.0f}s")
    lines.append("")
    lines.append(f"## 长停顿清单（>{LONG_GAP_MS/1000:.0f}s，共 {len(gaps)} 处，按时长降序）")
    lines.append("")
    n_jump = sum(1 for g in gaps if g[7])
    lines.append(f"- 其中剪辑跳转（>{JUMP_GAP_MS/1000:.0f}s）: {n_jump} 处")
    lines.append("")
    for i, (gap, ia, ib, a_end, b_start, at, bt, is_jump) in enumerate(gaps, 1):
        tag = "⚠️ 剪辑跳转" if is_jump else "长停顿"
        lines.append(f"### {i}. c{ia} → c{ib}（{gap/1000:.1f}s）{tag}")
        lines.append(f"- 区间: {fmt(a_end)} → {fmt(b_start)}")
        lines.append(f"- 前 cue c{ia}: `{at[:60]}{'…' if len(at)>60 else ''}`（{fmt(cues[ia-1]['start'])}→{fmt(a_end)}）")
        lines.append(f"- 后 cue c{ib}: `{bt[:60]}{'…' if len(bt)>60 else ''}`（{fmt(b_start)}→{fmt(cues[ib-1]['end'])}）")
        lines.append("- 用途: r01 合并补标点的强制分割点提示；r03 分句/游离停顿词归属参考")
        lines.append("")
    lines.append("## 使用说明")
    lines.append("")
    lines.append("1. **步骤 1 合并补标点**：本清单为空隙位置提供时间依据——补标点时在空隙处强制断句（不跨空隙合句），空隙两侧 cue 文本各自成句/成段。")
    lines.append("2. **步骤 3 分句对应**：游离停顿词 cue（单词级 so/okay/and）两侧若有大空隙，应独立成单元或归前句句尾，不与后句主体合并（避免跨空隙单元）。")
    lines.append("3. **复盘**：r04 回填告警（内部空隙/剪辑跳转/超长单元）应与本清单对照——理论上 r04 不应出现本清单之外的新空隙。")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"OK: {len(gaps)} 处长停顿（{n_jump} 剪辑跳转）→ {args.out}")
    for g in gaps:
        print(f"  c{g[1]}→c{g[2]} {g[0]/1000:.1f}s {'⚠️跳转' if g[7] else '停顿'}  {g[5][:30]} / {g[6][:30]}")


if __name__ == "__main__":
    main()
