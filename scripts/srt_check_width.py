# -*- coding: utf-8 -*-
"""检查 SRT 各段中文行视觉宽度（CJK=1, latin≈0.5, digit≈0.5, space≈0.5，半角标准）。

用法: python srt_check_width.py <draft.srt> [--warn 22] [--hard 26] [--order en-zh|zh-en]
--warn: 软告警阈值（默认 22，>warn 且 ≤hard 提示，软告警）；--hard: 硬限制阈值（默认 26，>hard 必切）。
--order: 双语行语言顺序，en-zh=英文行在前中文行在后（默认），zh-en=中文行在前英文行在后。
硬闸门：>hard 计 ERROR 并定位「文件:行号」，退出码 1 = 打回信号；软告警不阻断。
"""
import argparse, os, re, sys
sys.stdout.reconfigure(encoding='utf-8')

ap = argparse.ArgumentParser(description='检查 SRT 中文行视觉宽度')
ap.add_argument('srt', help='目标 SRT 路径（如 _work/<视频>/04_translation_draft.srt）')
ap.add_argument('--warn', type=float, default=22, help='软告警阈值，默认 22（>warn 提示）')
ap.add_argument('--hard', type=float, default=26, help='硬限制阈值，默认 26（>hard 必切）')
ap.add_argument('--order', choices=('en-zh', 'zh-en'), default='en-zh',
                help='双语行语言顺序：en-zh=英文行在前中文行在后（默认）；zh-en=中文行在前英文行在后')
args = ap.parse_args()

CJK = re.compile(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]')
LATIN = re.compile(r'[A-Za-z]')
DIGIT = re.compile(r'[0-9]')

def width(s):
    w = 0.0
    for ch in s:
        if CJK.match(ch):
            w += 1.0
        elif LATIN.match(ch):
            w += 0.5
        elif DIGIT.match(ch):
            w += 0.5
        elif ch == ' ':
            w += 0.5
        else:
            w += 1.0
    return w

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
        print(f'[{flag}] {os.path.basename(args.srt)}:行{start} 段{num} 宽={w:.1f}: {zh}')

n_hard = sum(1 for x in warn if x[2] > args.hard)
print(f'\n>软阈值 {args.warn} 的段数: {len(warn)}（其中 >硬阈值 {args.hard} 必切: {n_hard}）')
if n_hard:
    print(f'❌ 退出码 1：{n_hard} 段超过硬限制（> {args.hard} 必切），打回')
    sys.exit(1)
print('✅ 行宽硬校验通过（无 >硬限制 超限段）')
