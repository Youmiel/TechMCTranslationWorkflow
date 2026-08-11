# -*- coding: utf-8 -*-
"""检查 SRT 各段中文行视觉宽度（CJK=1, latin≈0.5, digit≈0.5, space≈0.5，半角标准）。

用法: python srt_check_width.py <draft.srt> [--warn 22] [--hard 26] [--order en-zh|zh-en]
--warn: 软告警阈值（默认 22，>warn 提示）；--hard: 硬限制阈值（默认 26，>hard 必切）。
--order: 双语行语言顺序，en-zh=英文行在前中文行在后（默认），zh-en=中文行在前英文行在后。
"""
import argparse, re, sys
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
    content = fh.read()

blocks = content.strip().split('\n\n')
print(f'总段数: {len(blocks)}')
warn = []
for b in blocks:
    lines = b.split('\n')
    if len(lines) < 3:
        continue
    num = lines[0].strip()
    # 双语行：按 --order 定位中文行（en-zh: 中文行在最后；zh-en: 中文行在正文第一行）
    zh = lines[-1] if args.order == 'en-zh' else lines[2]
    w = width(zh)
    flag = 'ERROR' if w > args.hard else ('WARN' if w > args.warn else 'ok')
    if w > args.warn:
        warn.append((num, w, zh))
        print(f'[{flag}] 段{num} 宽={w:.1f}: {zh}')

print(f'\n>软阈值 {args.warn} 的段数: {len(warn)}（其中 >硬阈值 {args.hard} 必切: {sum(1 for x in warn if x[1] > args.hard)}）')
