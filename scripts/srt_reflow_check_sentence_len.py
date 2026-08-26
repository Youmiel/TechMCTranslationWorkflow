# -*- coding: utf-8 -*-
"""r01 补标点质量校验（2026-08-18）：按句末标点 .?! 分句，检测补标点质量——subagent 偷懒
（整段逗号堆砌、缺句末标点）导致句子过长，回填锚定 / r03 分句对应困难。

补标点校验新增项（reflow 步骤 3 校验段）：逐块按 `.?!` 分句（与预分句 `srt_reflow_presplit.py`
同逻辑，复用 `split_en`），**分级告警**——
- **硬（打回，退出码 1）**：
  - 句级 · 逗号数：单句逗号数 > `--max-comma`（默认 10）→ 逗号连接未用句号断句
    （实测 E5/E22 的 11 逗号口语长句为堆砌，故硬阈值取 10）
  - 句级 · 字符数：单句字符数 > `--max-sent`（默认 600）→ 绝对超长句
  - 块级 · 句均字符：块内**句均字符** > `--max-avg`（默认 350）→ 断句稀疏（整块仅 1–2 个句号）
- **软（提示复核 ℹ️，不阻断）**：单句逗号 ≥ `--soft-comma`（默认 8）且 字符 ≥ `--soft-sent`
  （默认 250）→ 疑似可断句（如 chunk_008 E15「there we go, the next thing...」8 逗号——
  中等超长、逗号连接明显但未达硬阈值）

硬指标确凿打回（chunk_003 整块 7000+ 字符仅 1 句 / 106 逗号 → 多指标命中）；软指标把
"该断未断"的中等长句列出供主会话/用户复核（与硬命中一并 task-fix 补句号，或放行真实长句）。
通过项只汇总计数（`--verbose` 展开每块句数/句均/最大逗号数）。
统一反馈：默认只输出「问题数目 + 提示」（每块一行统计，不输出行号/上下文）；--expand 展开每处详情；
--chunk <k> 只校验单块并默认展开（修复单块时防其他块报错占用上下文）。
退出码：任一**硬**命中 → 1；软提示不计退出码。

用法（命令根 = Project_Main/）：
  python scripts/srt_reflow_check_sentence_len.py reflow/r01_results/
    [--max-comma 15] [--max-sent 600] [--max-avg 350] [--soft-comma 8] [--soft-sent 250] [--expand] [--chunk 3] [--verbose]
"""
import argparse
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

from srt_reflow_common import collect_chunk_files, ctx_snippet
from srt_reflow_presplit import split_en


def main():
    ap = argparse.ArgumentParser(description="r01 补标点质量校验：按 .?! 分句检测逗号堆砌/超长句/断句稀疏/疑似可断句（分级告警）")
    ap.add_argument("src", help="r01_results/ 目录（补标点产物）")
    ap.add_argument("--max-comma", type=int, default=10, help="硬：单句逗号数阈值（默认 10，超出=逗号连接未断句；实测 11 逗号 E5/E22 为堆砌）")
    ap.add_argument("--max-sent", type=int, default=600, help="硬：单句字符硬阈值（默认 600）")
    ap.add_argument("--max-avg", type=int, default=350, help="硬：块内句均字符阈值（默认 350，超出=断句稀疏）")
    ap.add_argument("--soft-comma", type=int, default=8, help="软：单句逗号数提示阈值（默认 8，与 --soft-sent 联合）")
    ap.add_argument("--soft-sent", type=int, default=250, help="软：单句字符提示阈值（默认 250，与 --soft-comma 联合）")
    ap.add_argument("--verbose", action="store_true", help="展开打印每块句数/句均/最大逗号数/最大句长")
    ap.add_argument("--expand", action="store_true", help="展开每处问题的行号+上下文（默认只给问题数+提示）")
    ap.add_argument("--chunk", type=int, default=None, metavar="k",
                    help="只校验指定块（chunk_<k>.txt，如 --chunk 3）；单块模式默认展开该块详情（修复单块时防其他块报错占用上下文）")
    args = ap.parse_args()
    expand = args.expand or args.chunk is not None  # 单块模式默认展开（只查一块，输出量小且是修复目标）

    blocks = collect_chunk_files(args.src)
    if not blocks:
        sys.exit(f"❌ 输入目录无块文件：{args.src}")
    if args.chunk is not None and args.chunk not in blocks:
        sys.exit(f"❌ --chunk {args.chunk}: 输入目录无该块（可用块: {sorted(blocks)}）")
    to_check = [args.chunk] if args.chunk is not None else sorted(blocks)

    issues = 0
    n_soft = 0
    for k in to_check:
        with open(blocks[k], encoding="utf-8") as fh:
            raw = fh.read()
        flat = re.sub(r"\s+", " ", raw).strip()
        sents = split_en(raw)
        if not sents:
            continue
        lens = [len(s) for s in sents]
        commas = [s.count(",") for s in sents]
        total = sum(lens)
        avg = total / len(sents)
        if args.verbose:
            print(f"   chunk_{k:03d}: {len(sents)} 句 / 总 {total} 字符 / 句均 {avg:.0f} / 最大逗号 {max(commas)} / 最大句长 {max(lens)}")
        hard_this = []
        soft_this = []
        if avg > args.max_avg:
            hard_this.append(("块级", f"断句稀疏：{len(sents)} 句 / {total} 字符 / 句均 {avg:.0f}（>{args.max_avg}，疑似逗号堆砌未用句号断句）"))
        for s, nc in zip(sents, commas):
            ln = len(s)
            hard = nc > args.max_comma or ln > args.max_sent
            if hard:
                pos = flat.find(s)
                line_no, frag = ctx_snippet(flat, pos)
                if nc > args.max_comma:
                    hard_this.append((f"行{line_no}", f"逗号连接 {nc} 个（>{args.max_comma}，疑似应用句号断句）：{frag}"))
                if ln > args.max_sent:
                    hard_this.append((f"行{line_no}", f"超长句 {ln} 字符（>{args.max_sent}）：{frag}"))
            elif nc >= args.soft_comma and ln >= args.soft_sent:
                pos = flat.find(s)
                line_no, frag = ctx_snippet(flat, pos)
                soft_this.append((f"行{line_no}", f"疑似可断句：逗号 {nc} 个 / {ln} 字符（≥{args.soft_comma} 且 ≥{args.soft_sent}，语义断点建议复核）：{frag}"))
        issues += len(hard_this)
        n_soft += len(soft_this)
        if hard_this or soft_this:
            if expand:
                print(f"⚠️ chunk_{k:03d}.txt: 硬 {len(hard_this)} 项 / 软 {len(soft_this)} 处")
                for tag, msg in hard_this:
                    print(f"   ⚠️ chunk_{k:03d}.txt {tag} {msg}")
                for tag, msg in soft_this:
                    print(f"   ℹ️ chunk_{k:03d}.txt {tag} {msg}")
            else:
                print(f"⚠️ chunk_{k:03d}: 硬 {len(hard_this)} 项 / 软 {len(soft_this)} 处")
    if issues:
        print(f"❌ 补标点质量校验未通过：{issues} 项硬命中 → 复核（明显逗号堆砌走 task-fix 补句号；真实长句可放行）")
        if not expand:
            print("   提示：--expand 展开每处详情（文件:行号+上下文）；--chunk <k> 只查单个块")
        return 1
    if n_soft:
        print(f"ℹ️ 另有 {n_soft} 处疑似可断句（软提示，不阻断）→ 主会话/用户复核语义断点，确认后一并 task-fix")
    print(f"✅ 补标点质量通过：{len(to_check)} 块无硬命中（逗号 ≤{args.max_comma}、单句 ≤{args.max_sent}、句均 ≤{args.max_avg}）")
    return 0


if __name__ == "__main__":
    main()
