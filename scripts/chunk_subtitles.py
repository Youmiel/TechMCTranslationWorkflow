# -*- coding: utf-8 -*-
"""将 SRT 字幕流按「N 条负责 + M 条上下文」分块，供 subagent 分块处理长视频。

设计：
- 每块 = OWNED 区（本块负责的 cue，必须产出）+ CONTEXT 区（前/后各 M 条，只读，仅作衔接参考，不产出）
- 块边界始终在 cue 边界，不切开任何 cue；合并后的段时间码仍 ⊆ 原字幕边界集
- 「未完成句结转」是语义规则（见 `segment-subtitles` Skill），本脚本只做确定性分块：
  每块只负责产出 start cue 落在 OWNED 区的完整句；跨块未完成句由下一块在 CONTEXT 中看到开头后完成。

用法:
  python scripts/chunk_subtitles.py <input.srt> --out <dir> --owned 100 --ctx 6 [--order en-zh|zh-en]

输入:
  merge 阶段     : 01_subtitle_asr_fixed.srt（单语英文 cue 流）
  translate 阶段 : 合并后的段 SRT（双语，en-zh 或 zh-en）
输出:
  <dir>/chunk_001.txt ...：每块一个文件，含 OWNED / CONTEXT 两个分区（tab 分隔：cue索引\t时间码\t文本）
"""
import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ap = argparse.ArgumentParser(description='将 SRT 字幕流按 N+M 分块，供 subagent 分块处理')
ap.add_argument('srt', help='输入 SRT 路径')
ap.add_argument('--out', required=True, help='输出目录（不存在则创建）')
ap.add_argument('--owned', type=int, default=100, help='每块负责的 cue 数 N（默认 100）')
ap.add_argument('--ctx', type=int, default=6, help='块前后只读上下文 cue 数 M（默认 6）')
ap.add_argument('--order', choices=('en-zh', 'zh-en'), default='en-zh',
                help='双语行语言顺序（仅影响输出标注）：en-zh=英文前中文后（默认）；zh-en=中文前英文后')
args = ap.parse_args()

if args.owned < 1:
    sys.exit('--owned 必须 >= 1')
if args.ctx < 0:
    sys.exit('--ctx 必须 >= 0')


def parse_srt(path):
    """返回 [(idx, start, end, [body_lines...]), ...]"""
    with open(path, 'r', encoding='utf-8-sig') as fh:
        text = fh.read()
    units = []
    for block in re.split(r'\n\s*\n', text.strip()):
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        m_idx = re.fullmatch(r'\d+', lines[0])
        m_ts = re.fullmatch(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', lines[1])
        if not m_idx or not m_ts:
            continue
        units.append((int(lines[0]), m_ts.group(1), m_ts.group(2), lines[2:]))
    return units


def fmt_text(body, order):
    """将 body 行格式化为单行文本（双语块带 en/zh 标注）。"""
    if len(body) <= 1:
        return body[0] if body else ''
    if order == 'en-zh':
        return 'en: %s | zh: %s' % (body[0], body[1])
    return 'zh: %s | en: %s' % (body[0], body[1])


units = parse_srt(args.srt)
if not units:
    sys.exit('未解析到任何 cue，请检查 SRT 格式')
n = len(units)
N, M = args.owned, args.ctx

os.makedirs(args.out, exist_ok=True)


def write_chunk(k, start, end):
    """写第 k 块；owned 区为 units[start:end]。"""
    owned = units[start:end]
    before = units[max(0, start - M):start]
    after = units[end:min(n, end + M)]
    total = (n + N - 1) // N
    lines = ['# Chunk %d/%d  owned: c%d..c%d  ctx: before=%d after=%d' %
             (k + 1, total, owned[0][0], owned[-1][0], len(before), len(after))]
    lines.append('## OWNED（本块负责：对这些 cue 做合并/翻译并产出）')
    for idx, s, e, body in owned:
        lines.append('c%d\t%s --> %s\t%s' % (idx, s, e, fmt_text(body, args.order)))
    lines.append('## CONTEXT（只读：仅供衔接参考，不产出）')
    for idx, s, e, body in before:
        lines.append('c%d\t%s --> %s\t%s' % (idx, s, e, fmt_text(body, args.order)))
    for idx, s, e, body in after:
        lines.append('c%d\t%s --> %s\t%s' % (idx, s, e, fmt_text(body, args.order)))
    fname = os.path.join(args.out, 'chunk_%03d.txt' % (k + 1))
    with open(fname, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(lines) + '\n')
    return fname


k = 0
for start in range(0, n, N):
    write_chunk(k, start, min(start + N, n))
    k += 1

print('总 cue 数: %d' % n)
print('分块数: %d（每块负责 %d 条，前后只读上下文各 %d 条）' % (k, N, M))
print('输出目录: %s' % os.path.abspath(args.out))
