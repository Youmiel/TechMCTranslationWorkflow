# -*- coding: utf-8 -*-
"""检查 SRT 各段中文行视觉宽度（CJK=1, latin≈0.4, digit≈0.5, space≈0.4；单一事实源 = shared.srt_common.text_width，阈值同源于其 SOFT_MAX/HARD_MAX）。

用法: python srt_check_width.py <draft.srt> [--warn 22] [--hard 27] [--order en-zh|zh-en] [--expand]
--warn: 软告警阈值（默认 22，>warn 且 ≤hard 提示，软告警）；--hard: 硬限制阈值（默认 27，>hard 必切）。
--order: 双语行语言顺序，zh-en=中文行在前英文行在后（默认），en-zh=英文行在前中文行在后。
统一反馈：默认只输出「超限段数 + 提示」（不输出每处内容/行号）；--expand 展开每处 文件:行号+内容。
硬闸门：>hard 计 ERROR 并定位「文件:行号」（--expand），退出码 1 = 打回信号；软告警不阻断。
"""
import argparse, os, re, sys
sys.stdout.reconfigure(encoding='utf-8')

from shared.srt_common import SOFT_MAX as _DEFAULT_WARN, HARD_MAX as _DEFAULT_HARD

ap = argparse.ArgumentParser(description='检查 SRT 中文行视觉宽度')
ap.add_argument('srt', help='目标 SRT 路径（如 _work/<视频>/s04_draft.srt）')
ap.add_argument('--warn', type=float, default=_DEFAULT_WARN, help=f'软告警阈值，默认 {_DEFAULT_WARN:g}（>warn 提示）')
ap.add_argument('--hard', type=float, default=_DEFAULT_HARD, help=f'硬限制阈值，默认 {_DEFAULT_HARD:g}（>hard 必切）')
ap.add_argument('--order', choices=('en-zh', 'zh-en'), default='zh-en',
                help='双语行语言顺序：zh-en=中文行在前英文行在后（默认）；en-zh=英文行在前中文行在后')
ap.add_argument('--expand', action='store_true',
                help='展开每处超限段的「文件:行号 + 内容」（默认只给超限段数+提示）')
args = ap.parse_args()

# 视觉宽度复用 shared.srt_common.text_width（**单一事实源**）。
# 2026-09-27 修：本脚本原有独立 width() 副本（拉丁/空格 0.5），与生成侧（pack_by_strength /
# srt_reflow2_backfill）用的 text_width 口径脱节——改一处不改另一处会出**假 ERROR**
# （实测 `所以这次我和同为红石玩家、YouTuber 的 mattbatwings 一样，`：
# 生成侧按拉丁/空格 0.4 算 26.2，本脚本副本按 0.5 报 28.5）。
from shared.srt_common import text_width as width

with open(args.srt, encoding='utf-8-sig') as fh:
    lines_all = fh.read().split('\n')

# 逐块扫描（记录段号行 1-based 行号，供「文件:行号」定位）
blocks = []
i, n = 0, len(lines_all)
while i < n:
    ln = lines_all[i].strip()
    if ln.isdigit():
        start = i + 1
        j = i
        while j < n and lines_all[j].strip():
            j += 1
        body = [l.strip() for l in lines_all[i + 1:j] if l.strip()]
        if len(body) >= 2 and '-->' in body[0]:
            # 双语行：en-zh=中文行在最后；zh-en=中文行在正文第一行
            zh = body[-1] if args.order == 'en-zh' else body[1]
            blocks.append((ln, start, zh))
        i = j
    else:
        i += 1

print(f'总段数: {len(blocks)}')
warn = []
for num, start, zh in blocks:
    w = width(zh)
    flag = 'ERROR' if w > args.hard else ('WARN' if w > args.warn else 'ok')
    if w > args.warn:
        warn.append((num, start, w, zh))
        if args.expand:
            print(f'[{flag}] {os.path.basename(args.srt)}:行{start} 段{num} 宽={w:.1f}: {zh}')

n_hard = sum(1 for x in warn if x[2] > args.hard)
print(f'\n>软阈值 {args.warn} 的段数: {len(warn)}（其中 >硬阈值 {args.hard} 必切: {n_hard}）')
if warn and not args.expand:
    print('   提示：--expand 查看每处超限段的 文件:行号+内容')
if n_hard:
    print(f'❌ 退出码 1：{n_hard} 段超过硬限制（> {args.hard} 必切），打回')
    sys.exit(1)
print('✅ 行宽硬校验通过（无 >硬限制 超限段）')
