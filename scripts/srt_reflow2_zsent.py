# -*- coding: utf-8 -*-
"""Z 句切分（新 reflow2 工作流）：r02 译文切 Z 句列表（供 task-match 语义对齐）

背景（2026-09-09 设计「时间轴源头固化」）：新 reflow2 的 Z 句 = 中文整句单元，脚本从 r02 译文
按句末标点切（复用 srt_reflow_presplit.split_zh：。！？… 分句、括号配平保护、折行合并保留中英/
数字空格、剥跨块句标记前缀）。产物为**整句级 Z 精简列表**（无脚手架），供 task-match LLM 对照
en_timeline（E 句）做 Z↔E 纯号对齐。

Z 号 = 只读真值锚对照物（en_timeline 的 E 号）；Z 每次从 r02 重算（删句/改句后重切重对齐，不依赖
记忆编号）。本产物为机器消费 + task-match LLM 输入（人读需按 `Z<n> <文本>` 每行一句理解）。

输入/输出（新工作流独立产物目录 reflow2/）：
- 输入：`reflow2/r02_results/`（整段译文原稿，task-translate 产物）
- 输出：`reflow2/zh_sentences/chunk_<k>.txt`（每行 `Z<n> <整句文本>`）

用法（命令根 = Project_Main/）：
  python scripts/srt_reflow2_zsent.py reflow2/r02_results/ -o reflow2/zh_sentences/
退出码：0 = 全部块切分完成；1 = 输入目录无块文件。
"""
import argparse
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

from srt_reflow_common import collect_chunk_files
from srt_reflow_presplit import split_zh, render_zslim


def main():
    ap = argparse.ArgumentParser(description="Z 句切分：r02 译文 → zh_sentences（整句级 Z 精简列表，供 task-match 对齐）")
    ap.add_argument("r02_dir", help="译文目录：reflow2/r02_results/（整段中文原稿）")
    ap.add_argument("-o", "--out", required=True, help="输出目录：reflow2/zh_sentences/")
    ap.add_argument("--verbose", action="store_true", help="展开打印每块句数")
    args = ap.parse_args()

    blocks = collect_chunk_files(args.r02_dir)
    if not blocks:
        sys.exit(f"❌ 输入目录无块文件：{args.r02_dir}")
    os.makedirs(args.out, exist_ok=True)
    total = 0
    for k in sorted(blocks):
        with open(blocks[k], encoding="utf-8") as fh:
            sents = split_zh(fh.read())
        zh_sents = [(f"Z{i}", s) for i, s in enumerate(sents, 1)]
        with open(os.path.join(args.out, "chunk_%03d.txt" % k), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(render_zslim(zh_sents))
        total += len(sents)
        if args.verbose:
            print(f"   chunk_{k:03d}: Z {len(sents)} 句")
    print(f"✅ Z 句切分完成：{len(blocks)} 块 / {total} Z 句 → {args.out}")
    return 0


if __name__ == "__main__":
    main()
