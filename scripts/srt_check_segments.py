# -*- coding: utf-8 -*-
"""校验分段方案/成稿 SRT 的时间约束（对照原字幕）：

  1. 相邻段时间不重叠：end_i <= start_{i+1}  —— 硬规则（允许相接，不允许交叉）
  2. 所有时间边界 ⊆ 原字幕边界集（不允许新造时间点）
     - 03_segments.md 中标注 `~` 的估算切分点跳过此检查（受控例外，见
       segment-subtitles「中间断句与估算时间」）；成稿 SRT 模式用 --allow-estimated 降级为告警
  3. 段序不逆序：start/end 单调不减
  4. （03_segments.md 模式）cue 覆盖完整、段号连续

用法:
  python scripts/srt_check_segments.py <目标> --orig <原字幕.srt> [--allow-estimated]

<目标> 两种输入：
  - 03_segments.md（行格式 `段号|cstart[-cend][~]|文本`；`~` 标注该侧边界为估算切分点）
  - 成稿 SRT（04_translation_draft.srt 等）

退出码：0=全部通过；1=发现问题。
"""
import argparse
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ap = argparse.ArgumentParser(description='校验分段/成稿时间约束：不重叠、⊆原边界集、不逆序')
ap.add_argument('target', help='目标文件：03_segments.md 或成稿 SRT')
ap.add_argument('--orig', required=True, help='原字幕 SRT（如 01_subtitle_asr_fixed.srt）')
ap.add_argument('--allow-estimated', action='store_true',
                help='允许估算切分点：成稿 SRT 中新时间点降级为告警（仅限受控例外的中间断句）')
args = ap.parse_args()

TS_RE = re.compile(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})')


def parse_time(s):
    m = TS_RE.match(s)
    if not m:
        return None
    h, mm, ss, ms = (int(x) for x in m.groups())
    return h * 3600000 + mm * 60000 + ss * 1000 + ms


def fmt(ms):
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return '%02d:%02d:%02d,%03d' % (h, m, s, ms)


def parse_orig(path):
    """返回 (边界毫秒集合, {cue_idx: (start, end)})"""
    bounds = set()
    cues = {}
    idx = None
    with open(path, encoding='utf-8-sig') as fh:
        for line in fh:
            line = line.strip()
            m = re.fullmatch(r'\d+', line)
            if m:
                idx = int(m.group(0))
                continue
            m = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', line)
            if m and idx is not None:
                s = parse_time(m.group(1))
                e = parse_time(m.group(2))
                bounds.add(s)
                bounds.add(e)
                cues[idx] = (s, e)
                idx = None
    return bounds, cues


def parse_md(path):
    """返回 [(seg_no, cs, cs_est, ce, ce_est), ...]（cue 索引 + 估算标记）"""
    segs = []
    with open(path, encoding='utf-8-sig') as fh:
        for line in fh:
            line = line.strip()
            m = re.match(r'^(\d+)\|c(\d+)(~?)(?:-c(\d+)(~?))?\|', line)
            if not m:
                continue
            seg_no = int(m.group(1))
            cs, cs_est = int(m.group(2)), (m.group(3) == '~')
            if m.group(4):
                ce, ce_est = int(m.group(4)), (m.group(5) == '~')
            else:
                ce, ce_est = cs, False
            segs.append((seg_no, cs, cs_est, ce, ce_est))
    return segs


def parse_srt(path):
    """返回 [(start, end), ...]（毫秒）"""
    out = []
    with open(path, encoding='utf-8-sig') as fh:
        text = fh.read()
    for block in re.split(r'\n\s*\n', text.strip()):
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        m = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', lines[1])
        if m:
            out.append((parse_time(m.group(1)), parse_time(m.group(2))))
    return out


orig_bounds, orig_cues = parse_orig(args.orig)
if not orig_cues:
    sys.exit('原字幕解析失败：%s' % args.orig)

errors, warnings_ = [], []


def is_md(path):
    with open(path, encoding='utf-8-sig') as fh:
        head = fh.read(4096)
    return bool(re.search(r'^\d+\|c\d+', head, re.MULTILINE))


if is_md(args.target):
    segs = parse_md(args.target)
    if not segs:
        sys.exit('目标解析失败（既非 03_segments.md 也非 SRT）：%s' % args.target)
    n_cues = max(orig_cues)
    prev = None
    for seg_no, cs, cs_est, ce, ce_est in segs:
        if cs not in orig_cues or ce not in orig_cues:
            errors.append('段 %d: cue 索引越界/缺失 c%d-c%d' % (seg_no, cs, ce))
            continue
        if cs > ce:
            errors.append('段 %d: start>end c%d-c%d' % (seg_no, cs, ce))
            continue
        # 相邻段共享 cue = 时间重叠；除非该边界是估算切分点（标注 ~）
        if prev is not None:
            p_seg, p_cs, p_cs_est, p_ce, p_ce_est = prev
            if cs < p_ce:
                errors.append('段 %d 与段 %d 交叉：本段 start c%d < 前段 end c%d' % (seg_no, p_seg, cs, p_ce))
            elif cs == p_ce and not (p_ce_est or cs_est):
                errors.append('段 %d 与段 %d 共享 cue c%d（时间重叠）；若为估算切分点须在该边界标注 ~' % (seg_no, p_seg, cs))
        prev = (seg_no, cs, cs_est, ce, ce_est)
    # cue 覆盖完整
    covered = [False] * (n_cues + 1)
    for seg_no, cs, cs_est, ce, ce_est in segs:
        for c in range(cs, ce + 1):
            if c <= n_cues:
                covered[c] = True
    missing = [c for c in range(1, n_cues + 1) if not covered[c]]
    if missing:
        errors.append('未覆盖 cue: %s%s' % (missing[:50], '...' if len(missing) > 50 else ''))
    # 段号连续
    expected = 1
    for seg_no, *_ in segs:
        if seg_no != expected:
            errors.append('段号不连续：期望 %d，实际 %d' % (expected, seg_no))
        expected = seg_no + 1
    print('目标: %s（03_segments.md）  段数: %d  原字幕 cue 数: %d'
          % (args.target, len(segs), n_cues))

else:
    segs = parse_srt(args.target)
    if not segs:
        sys.exit('目标解析失败（既非 03_segments.md 也非 SRT）：%s' % args.target)
    prev_end = None
    for i, (s, e) in enumerate(segs, 1):
        if s is None or e is None:
            errors.append('段 %d: 时间行无法解析' % i)
            continue
        if s > e:
            errors.append('段 %d: start>end %s > %s' % (i, fmt(s), fmt(e)))
            continue
        for label, t in (('start', s), ('end', e)):
            if t not in orig_bounds:
                msg = '段 %d: %s %s 不在原字幕边界集（新造时间点）' % (i, label, fmt(t))
                if args.allow_estimated:
                    warnings_.append(msg)
                else:
                    errors.append(msg)
        if prev_end is not None and s < prev_end:
            errors.append('段 %d 与段 %d 时间重叠: 前段 end=%s, 本段 start=%s'
                          % (i, i - 1, fmt(prev_end), fmt(s)))
        prev_end = e
    print('目标: %s（SRT）  段数: %d  原字幕时间边界数: %d'
          % (args.target, len(segs), len(orig_bounds)))

for w in warnings_:
    print('  !! %s' % w)
if errors:
    print('校验失败（%d 处）：' % len(errors))
    for e in errors[:60]:
        print('  - %s' % e)
    sys.exit(1)
print('校验通过：时间不重叠、边界 ⊆ 原边界集、段序不逆序' +
      ('（含估算切分点告警 %d 条）' % len(warnings_) if warnings_ else ''))
