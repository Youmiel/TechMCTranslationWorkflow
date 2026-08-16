# -*- coding: utf-8 -*-
"""任意文本（SRT / reflow 非 SRT 产物）的上下文量估算与分块建议（确定性，替代人工估算）

背景（为何按"窗口上限 × 比例"设阈值，而非绝对值）：
- 字幕翻译**不接受上下文压缩**（压缩丢细节 → 字幕失真），内容不能贴近窗口上限
- 读取某产物只是第一步：后续步骤（翻译输出 / 组装 / 校验 / subagent 汇总）也要占窗口
- 中间产物**落盘优于会话回顾**（断点恢复、subagent 组装都从文件读）——分块成本低，宁可多分块

阈值：估算 token > 窗口上限 × split_ratio（默认读 configs/context_window.json 的 split_ratio；config 缺失时降级代码默认）即建议分块——**分块阈值 = subagent 单窗口预算**（执行在 subagent，全新上下文；**分句读中英两倍材料** r01 EN + r02 ZH 对照为最坏场景，按示例 split_ratio=0.05、1M 窗口：单语言 ≈ 50k、中英两倍 ≈ 100k 仍可一次处理；宁低勿高；推导见 redstone-conventions 分块）。

确定性：字符 → token 用固定启发式（去空白字符 / 1.5，中英混合近似），同样输入同样输出。

用法（命令根 = Project_Main/）：
  python scripts/context_estimate.py <文件> [--window <窗口>] [--split-ratio <比例>] [--no-amplification]
  默认读 configs/context_window.json（context_length 窗口 + split_ratio 比例）；CLI 可覆盖
  输入支持：SRT（额外报 cue 数）与 reflow 非 SRT 产物（r03_plan.md 等 txt/md/json）
  --no-amplification：不考虑放大协调（单块输入上限 = min(输入阈值, 输出阈值)，不除以 amplification）；
     默认使用放大协调（单块输入上限 = min(输入阈值, 输出阈值 ÷ amplification)）
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "context_window.json"
DEFAULT_WINDOW = 1000000
DEFAULT_SPLIT_RATIO = 0.05
DEFAULT_OUTPUT_RATIO = 0.8  
DEFAULT_MAX_OUTPUT = 8192   
DEFAULT_AMPLIFICATION = 5.0 

TS_RE = re.compile(r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})")


def load_config():
    """读取 configs/context_window.json（单一事实源：context_length 窗口上限 + ratio 分块比例）。
    缺失/损坏 → {}（调用方降级默认并提示）。"""
    try:
        d = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def load_context_length():
    """窗口上限（config 的 context_length）；缺失/无效 → None（调用方降级默认并提示）"""
    try:
        v = int(load_config().get("context_length", 0))
        return v if v > 0 else None
    except (ValueError, TypeError):
        return None


def load_split_ratio():
    """分块比例（config 的 split_ratio，须在 (0,1)）；缺失/无效 → None（调用方降级默认并提示）"""
    try:
        r = float(load_config().get("split_ratio", 0.0))
        return r if 0 < r < 1 else None
    except (ValueError, TypeError):
        return None


def load_output_ratio():
    """输出比例（config 的 output_ratio，须在 (0,1)）；缺失/无效 → None（调用方降级默认并提示）"""
    try:
        r = float(load_config().get("output_ratio", 0.0))
        return r if 0 < r < 1 else None
    except (ValueError, TypeError):
        return None


def load_max_output():
    """模型单次最大输出（config 的 max_output）；缺失/无效 → None（调用方降级默认并提示）"""
    try:
        v = int(load_config().get("max_output", 0))
        return v if v > 0 else None
    except (ValueError, TypeError):
        return None


def load_amplification():
    """断句预测放大倍数（config 的 amplification，>1）；缺失/无效 → None（调用方降级默认并提示）"""
    try:
        v = float(load_config().get("amplification", 0.0))
        return v if v > 1 else None
    except (ValueError, TypeError):
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
    ap.add_argument("--split-ratio", type=float, default=None,
                    help="输入阈值比例 = 窗口上限 × 该比例（单块输入材料上限；默认读 configs/context_window.json 的 split_ratio，config 缺失时降级代码默认；宁低勿高；推导见 redstone-conventions 分块）")
    ap.add_argument("--output-ratio", type=float, default=None,
                    help="输出阈值比例 = max_output × 该比例（最大允许输出，留余量 < max_output；默认读 configs/context_window.json 的 output_ratio；单块最大输出文件不得超出）")
    ap.add_argument("--max-output", type=int, default=None,
                    help="模型单次最大输出 token（硬上限；默认读 configs/context_window.json 的 max_output；输出阈值 = max_output×output_ratio，留余量）")
    ap.add_argument("--amplification", type=float, default=None,
                    help="断句等最重环节预测放大倍数（预测最大输出 = 输入材料×该倍数；默认读 configs/context_window.json 的 amplification；断句 ≈ 5）")
    ap.add_argument("--no-amplification", action="store_true",
                    help="不考虑放大协调：单块输入上限 = min(输入阈值, 输出阈值)（不除以 amplification）；默认使用放大协调（min(输入阈值, 输出阈值 ÷ amplification)）")
    args = ap.parse_args()
    if args.window is None:
        args.window = load_context_length()
        if args.window is None:
            args.window = DEFAULT_WINDOW
            print(f"⚠️ 未配置窗口上限：configs/context_window.json 缺失或无效，暂按 {DEFAULT_WINDOW} 计。")
            print(f"   请询问用户期望的窗口上限，写入 configs/context_window.json：{{\"context_length\": <值>, \"split_ratio\": <0-1>}}")
    if args.split_ratio is None:
        args.split_ratio = load_split_ratio()
        if args.split_ratio is None:
            args.split_ratio = DEFAULT_SPLIT_RATIO
            print(f"⚠️ 未配置分块比例（split_ratio）：configs/context_window.json 缺失或无效，暂按 {DEFAULT_SPLIT_RATIO} 计。")
            print(f"   写入 configs/context_window.json：{{\"context_length\": {args.window}, \"split_ratio\": <0-1>, \"output_ratio\": <0-1>}}")
    if args.output_ratio is None:
        args.output_ratio = load_output_ratio()
        if args.output_ratio is None:
            args.output_ratio = DEFAULT_OUTPUT_RATIO
            print(f"⚠️ 未配置输出比例（output_ratio）：configs/context_window.json 缺失或无效，暂按 {DEFAULT_OUTPUT_RATIO} 计。")
            print(f"   写入 configs/context_window.json：{{\"context_length\": {args.window}, \"max_output\": <输出上限>, \"split_ratio\": <0-1>, \"output_ratio\": <0-1>}}")
    if args.max_output is None:
        args.max_output = load_max_output()
        if args.max_output is None:
            args.max_output = DEFAULT_MAX_OUTPUT
            print(f"⚠️ 未配置 max_output：configs/context_window.json 缺失或无效，暂按 {DEFAULT_MAX_OUTPUT} 计。")
            print(f"   写入 configs/context_window.json：{{\"context_length\": {args.window}, \"max_output\": <输出上限>, \"split_ratio\": <0-1>, \"output_ratio\": <0-1>, \"amplification\": <倍数>}}")
    if not args.no_amplification and args.amplification is None:
        args.amplification = load_amplification()
        if args.amplification is None:
            args.amplification = DEFAULT_AMPLIFICATION
            print(f"⚠️ 未配置 amplification：configs/context_window.json 缺失或无效，暂按 {DEFAULT_AMPLIFICATION} 计。")
            print(f"   写入 configs/context_window.json：{{\"context_length\": {args.window}, \"max_output\": <输出上限>, \"split_ratio\": <0-1>, \"output_ratio\": <0-1>, \"amplification\": <倍数>}}")

    if not (0 < args.split_ratio < 1):
        sys.exit("--split-ratio 必须在 (0, 1) 内（建议 ≤0.4：subagent 单窗口还要容纳输出与预留）")
    if not (0 < args.output_ratio < 1):
        sys.exit("--output-ratio 必须在 (0, 1) 内（留余量，建议 0.7-0.9）")
    if args.max_output <= 0:
        sys.exit("--max-output 必须为正整数（模型单次最大输出 token）")
    if not args.no_amplification and args.amplification <= 1:
        sys.exit("--amplification 必须 > 1（预测放大倍数，断句 ≈ 5；--no-amplification 时忽略）")

    cues = parse_srt_cues(args.file)
    if cues:
        chars = sum(len(re.sub(r"\s", "", body)) for _i, body in cues)
        desc = "%d cue（SRT）" % len(cues)
    else:
        raw = open(args.file, encoding="utf-8-sig").read()
        chars = len(re.sub(r"\s", "", raw))
        desc = "非 SRT 文本（txt/md/json）"

    token_est = int(chars / 1.5)          # 固定启发式：去空白字符/1.5（中英混合近似，确定性可复现）
    in_threshold = int(args.window * args.split_ratio)      # 输入阈值：单块输入材料上限 = 窗口×split_ratio
    out_threshold = int(args.max_output * args.output_ratio)    # 输出阈值：单块最大输出文件上限 = max_output×output_ratio（留余量）
    pct = token_est * 100.0 / args.window if args.window else 0.0

    print("上下文量估算（确定性，非人工估算）:")
    print("  输入: %s" % args.file)
    print("  类型: %s" % desc)
    print("  去空白字符数: %d" % chars)
    print("  估算 token（字符/1.5）: %d" % token_est)
    print("  窗口上限: %d token" % args.window)
    print("  输入阈值（window×%.2f）: %d token" % (args.split_ratio, in_threshold))
    print("  输出阈值（max_output×%.2f）: %d token（max_output=%d 留余量）" % (args.output_ratio, out_threshold, args.max_output))
    if args.no_amplification:
        # 不考虑放大：单块输入上限 = min(输入阈值, 输出阈值)——输出侧不除以 amplification
        out_by_amp = out_threshold
        pred_output = 0
        effective_in = min(in_threshold, out_by_amp)
        print("  未启用放大协调（--no-amplification）：单块输入上限 = min(输入阈值, 输出阈值) = %d token" % effective_in)
        if in_threshold > out_by_amp:
            print(f"  ⚠️ 输入阈值（{in_threshold}）> 输出阈值（{out_by_amp}）——输出预算偏紧；术语清单等输出通常远小于输入，可不降")
    else:
        pred_output = int(token_est * args.amplification)      # 预测最大输出 = 输入材料×放大倍数（断句最重环节）
        print("  预测最大输出（输入×%.1f）: %d token" % (args.amplification, pred_output))
        out_by_amp = int(out_threshold / args.amplification)      # 输出阈值÷amplification（反推的输入上限）
        effective_in = min(in_threshold, out_by_amp)              # 单块输入上限 = min(输入阈值, 输出阈值÷amplification)
        print("  单块输入上限（min(输入阈值, 输出阈值÷%.1f)）: %d token" % (args.amplification, effective_in))
        if in_threshold > out_by_amp:
            print(f"  ⚠️ min 落到输出侧：输入阈值（{in_threshold}）> 输出阈值÷amplification（{out_by_amp}）——输出预算成瓶颈，单块输入上限取输出侧值（{out_by_amp}），按此反推 --owned 分块大小")
    print("  当前占比: %.1f%%" % pct)
    if token_est > in_threshold:
        print("  → 超输入阈值：建议分块（字幕不容压缩、后续步骤也占窗口）")
        # 给可执行建议（非 SRT 按语义单位、SRT 按 cue）
        if cues:
            print("  → 建议命令: python scripts/text_chunk.py %s --out <chunk_dir> --type srt --owned <N> --ctx 6" % args.file)
        else:
            print("  → 建议命令: python scripts/text_chunk.py %s --out <chunk_dir> --type text --unit 段 --ctx 1 --max-chars <字符>" % args.file)
            print("     语义单位: r01 用 --unit 段（空隙语义段）；r02 用 --unit 句；r03 用 --unit 整句组；超长单位自动细分（--max-chars，默认 6000）")
        print("     合并: python scripts/text_merge.py <chunk_dir> <结果目录> --out <合并产物> [--wrap 1000]（全自动，异常读 .report.md）")
    else:
        print("  → 未超输入阈值：空隙组内不分片（仍派 subagent 执行；块数 = 空隙组数 × 组内片数，产物落 r0X_results/）")
    if token_est > out_threshold:
        print("  → 超输出阈值：本产物若为单块最大输出已超输出上限——须更小分块")
    elif not args.no_amplification and pred_output > out_threshold:
        print(f"  → 超输出阈值（预测放大）：本文件若为单块输入材料，×{args.amplification:.0f} 后预测输出（{pred_output}）> 输出阈值（{out_threshold}）——须更小分块")
    else:
        print("  → 未超输出阈值：单块输入材料可容纳（放大协调场景按最重环节反推后仍须复核）")


if __name__ == "__main__":
    main()
