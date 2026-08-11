# -*- coding: utf-8 -*-
"""任意文本（SRT / reflow 非 SRT 产物）的上下文量估算与分块建议（确定性，替代人工估算）

背景（为何按"窗口上限 × 比例"设阈值，而非绝对值）：
- 字幕翻译**不接受上下文压缩**（压缩丢细节 → 字幕失真），内容不能贴近窗口上限
- 读取某产物只是第一步：后续步骤（翻译输出 / 组装 / 校验 / subagent 汇总）也要占窗口
- 中间产物**落盘优于会话回顾**（断点恢复、subagent 组装都从文件读）——分块成本低，宁可多分块

阈值：估算 token > 窗口上限 × ratio（默认 0.5）即建议分块——内容+本步 prompt 不超窗口一半，
留出另一半给输出与后续步骤；字幕密集时可调低 ratio（如 0.4），宁低勿高。

确定性：字符 → token 用固定启发式（去空白字符 / 1.5，中英混合近似），同样输入同样输出。

用法（命令根 = Project_Main/）：
  python scripts/context_estimate.py <文件> [--window 128000] [--ratio 0.5]
  输入支持：SRT（额外报 cue 数）与 reflow 非 SRT 产物（r01_merged_en.txt / r02_translation_zh.txt / r03_plan.md 等 txt/md/json）
"""
import argparse
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

TS_RE = re.compile(r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})")


def parse_srt_cues(path):
    """SRT 解析：返回 [(idx, body), ...]；非 SRT 返回空列表（调用方退化为全文统计）"""
    text = open(path, encoding="utf-8-sig").read()
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        if not re.fullmatch(r"\d+", lines[0]):
            continue
        if not TS_RE.match(lines[1]):
            continue
        cues.append((int(lines[0]), " ".join(lines[2:])))
    return cues


def main():
    ap = argparse.ArgumentParser(description="上下文量估算与分块建议（SRT / 任意文本，确定性，替代人工估算）")
    ap.add_argument("file", help="输入文件：SRT 或 reflow 非 SRT 产物（txt/md/json）")
    ap.add_argument("--window", type=int, default=128000, help="模型上下文窗口上限（估算 token，默认 128000）")
    ap.add_argument("--ratio", type=float, default=0.5,
                    help="分块阈值 = 窗口上限 × 该比例（默认 0.5：内容+prompt 不超窗口一半，留余量给输出/后续步骤）")
    args = ap.parse_args()

    if not (0 < args.ratio < 1):
        sys.exit("--ratio 必须在 (0, 1) 内（建议 ≤0.5：字幕不容压缩、后续步骤也占窗口）")

    cues = parse_srt_cues(args.file)
    if cues:
        chars = sum(len(re.sub(r"\s", "", body)) for _i, body in cues)
        desc = "%d cue（SRT）" % len(cues)
    else:
        raw = open(args.file, encoding="utf-8-sig").read()
        chars = len(re.sub(r"\s", "", raw))
        desc = "非 SRT 文本（txt/md/json）"

    token_est = int(chars / 1.5)          # 固定启发式：去空白字符/1.5（中英混合近似，确定性可复现）
    threshold = int(args.window * args.ratio)
    pct = token_est * 100.0 / args.window if args.window else 0.0

    print("上下文量估算（确定性，非人工估算）:")
    print("  输入: %s" % args.file)
    print("  类型: %s" % desc)
    print("  去空白字符数: %d" % chars)
    print("  估算 token（字符/1.5）: %d" % token_est)
    print("  窗口上限: %d token" % args.window)
    print("  分块阈值（window×%.2f）: %d token" % (args.ratio, threshold))
    print("  当前占比: %.1f%%" % pct)
    if token_est > threshold:
        print("  → 超阈值：建议分块（字幕不容压缩、后续步骤也占窗口；分块方式见工作流分块策略）")
    else:
        print("  → 未超阈值：可整段处理（保守起见仍可按语义段分块）")


if __name__ == "__main__":
    main()
