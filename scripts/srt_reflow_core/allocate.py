# -*- coding: utf-8 -*-
"""句内分配：单元级 cue 锚定分支（allocate_unit_cues）+ 字数比例兜底（allocate_by_ratio）"""
from .io import norm, fmt


def allocate_unit_cues(s, a, units, unit_cues, cues, cue_offsets, alerts):
    """句内分配·单元级 cue 锚定分支：每单元命中自身 cue 区间 → 首末裁剪到整句边界
    → 相邻单元共享 cue 按字符比例中间断句估算 → 时间重叠顺延。返回 timeline 片段。
    """
    segs = []
    for i, (u, uc) in enumerate(zip(units, unit_cues)):
        usi, uei, upos = uc
        segs.append([u[0], cues[usi]["start"], cues[uei]["end"], u[2], u[1], False, False])
    if segs:
        segs[0][1] = max(segs[0][1], a["start"])
        segs[-1][2] = min(segs[-1][2], a["end"])
    # 相邻单元共享 cue（prev.ei == cur.si）→ 中间断句估算切分
    for i in range(1, len(segs)):
        if unit_cues[i - 1][1] == unit_cues[i][0]:
            j = unit_cues[i][0]
            cue = cues[j]
            cj_off = cue_offsets[j]
            cj_len = len(norm(cue["text"]))
            a_chars = unit_cues[i - 1][2] + len(norm(units[i - 1][1])) - cj_off
            b_chars = (cj_off + cj_len) - unit_cues[i][2]
            if a_chars > 0 and b_chars > 0:
                t = cue["start"] + (cue["end"] - cue["start"]) * a_chars / (a_chars + b_chars)
            else:
                t = cue["end"]
            t = int(t)
            segs[i - 1][2] = t
            segs[i][1] = t
            alerts.append(
                f"🔗 单元共享 cue c{cue['idx']}（{cue['text'][:30]}...）中间断句估算切分 {fmt(t)}"
            )
    # 相邻单元时间重叠兜底（非共享）：后单元顺延
    for i in range(1, len(segs)):
        if segs[i][1] < segs[i - 1][2]:
            segs[i][1] = segs[i - 1][2]
    return [(u0, int(u1), int(u2), zh, en, p1, p2) for u0, u1, u2, zh, en, p1, p2 in segs]


def allocate_by_ratio(units, start, end, real_bounds, snap_ms):
    """句内分配·字数比例兜底：按中文长度比例算切分点 → 就近吸附真实 cue 边界（≤ snap_ms，
    空隙内无边界则吸附空隙前后沿，不吞空隙，S56 实证）→ 无则 100ms 取整预测点。返回 timeline 片段。
    """
    total = sum(len(u[2]) for u in units) or 1
    T = max(0, end - start)
    acc = 0.0
    raw = []
    for u in units[:-1]:
        acc += len(u[2])
        raw.append(start + T * acc / total)
    bounds = [start]
    pred_bounds = []
    for b in raw:
        snapped, best = None, None
        for rb in real_bounds:
            d = abs(rb - b)
            if best is None or d < best:
                best = d
                snapped = rb
        if snapped is not None and best is not None and best <= snap_ms and snapped > bounds[-1] + 100 and snapped < end - 100:
            bounds.append(int(snapped))
            pred_bounds.append(False)
            continue
        p = int(round(b / 100.0)) * 100
        if p <= bounds[-1]:
            p = bounds[-1] + 100
        if p >= end - 100:
            p = end - 100
        bounds.append(p)
        pred_bounds.append(True)
    bounds.append(end)
    # 末边界递增保证
    if bounds[-2] >= bounds[-1]:
        bounds[-2] = end - 100
        if pred_bounds:
            pred_bounds[-1] = True
    return [(u[0], int(bounds[i]), int(bounds[i + 1]), u[2], u[1],
             i > 0 and pred_bounds[i - 1], i < len(units) - 1 and pred_bounds[i])
            for i, u in enumerate(units)]
