# -*- coding: utf-8 -*-
"""检查 SRT 各段中文行视觉宽度（CJK=1, latin≈1.5, digit≈1, space≈0.5）。

用法: python srt_check_width.py <draft.srt> [--warn 24] [--order en-zh|zh-en]
--order: 双语行语言顺序，en-zh=英文行在前中文行在后（默认），zh-en=中文行在前英文行在后。
"""
import argparse, re, sys
sys.stdout.reconfigure(encoding='utf-8')

ap = argparse.ArgumentParser(description='检查 SRT 中文行视觉宽度')
ap.add_argument('srt', help='目标 SRT 路径（如 _work/<视频>/04_translation_draft.srt）')
ap.add_argument('--warn', type=float, default=24, help='告警阈值，默认 24')
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
            w += 1.5
        elif DIGIT.match(ch):
            w += 1.0
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
    flag = 'WARN' if w > args.warn else ('ok' if w <= 20 else '~')
    if w > 20:
        warn.append((num, w, zh))
        print(f'[{flag}] 段{num} 宽={w:.1f}: {zh}')

print(f'\n>20 的段数: {len(warn)}')
