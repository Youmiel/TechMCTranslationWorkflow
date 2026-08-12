# -*- coding: utf-8 -*-
"""任意文本（SRT / reflow 非 SRT 产物）的上下文量估算与分块建议（确定性，替代人工估算）

背景（为何按"窗口上限 × 比例"设阈值，而非绝对值）：
- 字幕翻译**不接受上下文压缩**（压缩丢细节 → 字幕失真），内容不能贴近窗口上限
- 读取某产物只是第一步：后续步骤（翻译输出 / 组装 / 校验 / subagent 汇总）也要占窗口
- 中间产物**落盘优于会话回顾**（断点恢复、subagent 组装都从文件读）——分块成本低，宁可多分块

阈值：估算 token > 窗口上限 × ratio（默认 0.04）即建议分块——分块阈值按全流程读取次数摊销
（完整流程 0.04=3.8% 保守、子任务不读 r03/r04 时 0.05=5% 上限，推导见 redstone-conventions 分块）；宁低勿高。

确定性：字符 → token 用固定启发式（去空白字符 / 1.5，中英混合近似），同样输入同样输出。

用法（命令根 = Project_Main/）：
  python scripts/context_estimate.py <文件> [--window 128000] [--ratio 0.04]
  输入支持：SRT（额外报 cue 数）与 reflow 非 SRT 产物（r01_merged_en.txt / r02_translation_zh.txt / r03_plan.md 等 txt/md/json）
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "context_window.json"
DEFAULT_WINDOW = 128000

TS_RE = re.compile(r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})")


def load_context_length():
    """模型窗口上限（单一事实源 = configs/context_window.json，仅 context_length 一个值）。
    缺失/损坏 → None（调用方降级默认并提示询问用户写入）。"""
    try:
        v = int(json.loads(CONFIG_PATH.read_text(encoding="utf-8")).get("context_length", 0))
        return v if v > 0 else None
    except (OSError, ValueError, KeyError):
        return None


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
    ap.add_argument("--window", type=int, default=None, help="模型上下文窗口上限（估算 token；默认读 configs/context_window.json，缺失时提示配置）")
    ap.add_argument("--ratio", type=float, default=0.04,
                    help="分块阈值 = 窗口上限 × 该比例（默认 0.04 保守=完整流程摊销 3.8%；子任务不读 r03/r04 时用 0.05；推导见 redstone-conventions 分块）")
    args = ap.parse_args()
    cfg = load_context_length()
    if args.window is None:
        args.window = cfg or DEFAULT_WINDOW
        if cfg is None:
            print(f"⚠️ 未配置窗口上限：configs/context_window.json 缺失或无效，暂按 {DEFAULT_WINDOW} 计。")
            print(f"   请询问用户期望的窗口上限（仅一个值），写入 configs/context_window.json：{{\"context_length\": <值>}}")

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
        print("  → 超阈值：建议分块（字幕不容压缩、后续步骤也占窗口）")
        # 给可执行建议（非 SRT 按语义单位、SRT 按 cue）
        if cues:
            print("  → 建议命令: python scripts/text_chunk.py %s --out <chunk_dir> --type srt --owned <N> --ctx 6" % args.file)
        else:
            print("  → 建议命令: python scripts/text_chunk.py %s --out <chunk_dir> --type text --unit 段 --ctx 1 --max-chars <字符>" % args.file)
            print("     语义单位: r01 用 --unit 段（空隙语义段）；r02 用 --unit 句；r03 用 --unit 整句组；超长单位自动细分（--max-chars，默认 6000）")
        print("     合并: python scripts/text_merge.py <chunk_dir> <结果目录> --out <合并产物>（全自动，异常读 .report.md）")
    else:
        print("  → 未超阈值：可整段处理（保守起见仍可按语义段分块）")


if __name__ == "__main__":
    main()
