# -*- coding: utf-8 -*-
"""校验分段方案/成稿 SRT 的时间约束（对照原字幕）：

  1. 相邻段时间不重叠：end_i <= start_{i+1}  —— 硬规则（允许相接，不允许交叉）
  2. 所有时间边界 ⊆ 原字幕边界集（不允许新造时间点）
     - 03_segments.md 中标注 `~` 的估算切分点跳过此检查（受控例外，见
       segment-subtitles「中间断句与估算时间」）；成稿 SRT 模式用 --allow-estimated 降级为告警
  3. 段序不逆序：start/end 单调不减
  4. （03_segments.md 模式）cue 覆盖完整、段号连续

用法:
  python scripts/srt_check_segments.py <目标> --orig <原字幕.srt> [--allow-estimated] [--cue-exact]

<目标> 两种输入：
  - 03_segments.md（行格式 `段号|cstart[-cend][~]|文本`；`~` 标注该侧边界为估算切分点）
  - 成稿 SRT（04_translation_draft.srt 等）

--cue-exact（SRT 模式专用，用于 01 修正字幕）：
  目标为逐 cue 流（如 01_subtitle_asr_fixed.srt），要求 cue 数与原始一致、
  且逐 cue 时间戳与原始完全一致（01 只改文本、保留原时间码、不增删 cue）。
  时间轴错位会一路传给 03/04（表现为"字幕比语音快/慢"），须在断句前发现。

--missing-ctx <N>（搭配 --cue-exact）：cue 数不一致（字幕缺失/多余）时输出
  每条缺失 cue 的标号+时间+文本 + 每侧 N 条上下句，供 agent 直接定位（无需
  自写定位脚本）；0=只报缺失/多余总数（默认，防输出过多挤爆上下文）。

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
ap.add_argument('--cue-exact', action='store_true',
                help='SRT 模式：目标为逐 cue 流（如 01 修正字幕），要求 cue 数一致且逐 cue 时间戳与原始完全一致')
ap.add_argument('--missing-ctx', type=int, default=0, metavar='N',
                help='cue 数不一致时输出缺失 cue 明细（标号+时间+文本+每侧 N 条上下句）；0=只报缺失/多余总数，防输出挤爆上下文')
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


def clip(text, limit=80):
    """截断显示文本（防明细输出过多挤爆上下文）"""
    text = (text or '').replace('\n', ' ').strip()
    return text if len(text) <= limit else text[:limit] + '…'


def parse_orig(path):
    """返回 (边界毫秒集合, {cue_idx: (start, end, text)})"""
    bounds = set()
    cues = {}
    idx = None
    last_cue_idx = None
    with open(path, encoding='utf-8-sig') as fh:
        for line in fh:
            stripped = line.strip()
            m = re.fullmatch(r'\d+', stripped)
            if m:
                idx = int(m.group(0))
                last_cue_idx = None
                continue
            m = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', stripped)
            if m and idx is not None:
                s = parse_time(m.group(1))
                e = parse_time(m.group(2))
                bounds.add(s)
                bounds.add(e)
                cues[idx] = (s, e, '')
                last_cue_idx = idx
                continue
            if stripped and last_cue_idx is not None:
                s, e, t = cues[last_cue_idx]
                cues[last_cue_idx] = (s, e, (t + ' ' + stripped).strip())
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
    """返回 [(idx, start, end, text), ...]（SRT 序号 + 毫秒 + 文本）"""
    out = []
    with open(path, encoding='utf-8-sig') as fh:
        text = fh.read()
    for block in re.split(r'\n\s*\n', text.strip()):
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        if not re.fullmatch(r'\d+', lines[0]):
            continue
        m = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', lines[1])
        if m:
            out.append((int(lines[0]), parse_time(m.group(1)), parse_time(m.group(2)), ' '.join(lines[2:])))
    return out


orig_bounds, orig_cues = parse_orig(args.orig)
if not orig_cues:
    sys.exit('原字幕解析失败：%s' % args.orig)

errors, warnings_, missing_details = [], [], []


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
    for n, (idx, s, e, _) in enumerate(segs, 1):
        if s is None or e is None:
            errors.append('段 %d: 时间行无法解析' % n)
            continue
        if s > e:
            errors.append('段 %d: start>end %s > %s' % (n, fmt(s), fmt(e)))
            continue
        for label, t in (('start', s), ('end', e)):
            if t not in orig_bounds:
                msg = '段 %d: %s %s 不在原字幕边界集（新造时间点）' % (n, label, fmt(t))
                if args.allow_estimated:
                    warnings_.append(msg)
                else:
                    errors.append(msg)
        if prev_end is not None and s < prev_end:
            errors.append('段 %d 与段 %d 时间重叠: 前段 end=%s, 本段 start=%s'
                          % (n, n - 1, fmt(prev_end), fmt(s)))
        prev_end = e
    # --cue-exact：目标为逐 cue 流（如 01 修正字幕），要求 cue 数一致且逐 cue 时间戳与原始一致
    if args.cue_exact:
        target_ids = {idx for idx, *_ in segs}
        orig_ids = set(orig_cues)
        if len(segs) != len(orig_cues):
            n_missing = len(orig_ids - target_ids)
            n_extra = len(target_ids - orig_ids)
            errors.append('cue 数不一致：目标=%d，原始=%d（缺失 %d、多余 %d；01 应保留原时间码、不增删 cue）'
                          % (len(segs), len(orig_cues), n_missing, n_extra))
            if args.missing_ctx:
                for c in sorted(orig_ids - target_ids):
                    cs, ce, ctext = orig_cues[c]
                    missing_details.append('缺失 c%d [%s-%s] %s'
                                           % (c, fmt(cs), fmt(ce), clip(ctext)))
                    for p in range(c - args.missing_ctx, c):
                        if p in orig_cues:
                            ps, pe, ptext = orig_cues[p]
                            missing_details.append('  上句 c%d [%s-%s] %s'
                                                   % (p, fmt(ps), fmt(pe), clip(ptext)))
                    for q in range(c + 1, c + 1 + args.missing_ctx):
                        if q in orig_cues:
                            qs, qe, qtext = orig_cues[q]
                            missing_details.append('  下句 c%d [%s-%s] %s'
                                                   % (q, fmt(qs), fmt(qe), clip(qtext)))
        for idx, s, e, _ in segs:
            oc = orig_cues.get(idx)
            if oc is None:
                errors.append('cue %d: 原始字幕无此序号（目标序号错位）' % idx)
                continue
            os_, oe, _ = oc
            if s != os_ or e != oe:
                errors.append('cue %d: 时间错位  目标=%s-%s  原始=%s-%s'
                              % (idx, fmt(s), fmt(e), fmt(os_), fmt(oe)))
    print('目标: %s（SRT%s）  段数: %d  原字幕 cue 数: %d'
          % (args.target, '，逐 cue 对齐' if args.cue_exact else '', len(segs), len(orig_cues)))

for w in warnings_:
    print('  !! %s' % w)
if errors:
    print('校验失败（%d 处）：' % len(errors))
    for e in errors[:60]:
        print('  - %s' % e)
    if missing_details:
        print('缺失 cue 明细（--missing-ctx %d）：' % args.missing_ctx)
        for d in missing_details:
            print('  %s' % d)
    sys.exit(1)
print('校验通过：时间不重叠、边界 ⊆ 原边界集、段序不逆序' +
      ('（含估算切分点告警 %d 条）' % len(warnings_) if warnings_ else ''))
