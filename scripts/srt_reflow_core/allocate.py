# -*- coding: utf-8 -*-
"""句内分配：单元级 cue 锚定分支（allocate_unit_cues）+ 阅读感知插值（allocate_by_reading）+ 字数比例兜底（allocate_by_ratio）

时间分配的三个分支（reflow 主流程按序选择）：
1. allocate_unit_cues  —— 单元级 cue 锚定：每单元命中自身英文 cue 区间（贴原轴节奏，默认首选）
2. allocate_by_reading —— 阅读感知插值：cue 锚定成功但「分配时长 < 中文阅读所需×READING_MISMATCH_RATIO」时，
   放弃 cue 时长改按中文阅读速度在整句区间内按比例重分配（倒装语序 / 中英时长差异大时，S6 实证），
   切分点就近吸附真实 cue 边界（≤ snap_ms），无则 100ms 取整预测点。
3. allocate_by_ratio   —— 字数比例兜底：单元文本未命中（文本不一致）时按中文长度比例分配（同吸附规则）。

时长阈值与 reflow-redstone SKILL 一致：单句时长通常 ≥1s（MIN_FRAG_MS，<1s 为「长句碎片」须回报 Agent）；
中文阅读速度默认 5 字/秒（--cjk-speed 可调，0=禁用阅读校验）。
"""
from .io import norm, fmt, text_width

READING_MISMATCH_RATIO = 0.7  # 分配时长 < 阅读所需×该值 → 触发阅读感知插值（倒装/中英时长差）
READING_MIN_GAP_MS = 300      # 显著失配最小毫秒数（避免轻微差异过度触发插值、偏离 cue 锚定）
MIN_FRAG_MS = 1000            # 长句碎片阈值：单条时长 <1s 须回报 Agent 裁决（与 SKILL「单句时长≥1s」一致）


def cjk_reading_ms(text, speed=5.0):
    """中文阅读所需时长估算：视觉宽度 / 阅读速度（字/秒）→ ms。

    默认 5 字/秒（字幕阅读含理解停顿，保守取值）；speed<=0 返回 0（禁用阅读校验）。
    视觉宽度用 io.text_width（全角=1.0 / 拉丁=0.5 / 数字=0.5 / 空格=0.5）——含英文/数字的单元
    （如「在 1994 年」「Ticketmaster」）按实际视觉宽度计，而非纯中文字数。
    """
    if speed <= 0:
        return 0
    return int(text_width(text) * 1000.0 / speed)


def needs_reading_interp(segs, speed, ratio=READING_MISMATCH_RATIO,
                         min_frag_ms=MIN_FRAG_MS, min_gap_ms=READING_MIN_GAP_MS):
    """阅读感知插值触发检测：返回 [(unit_key, 分配时长ms, 阅读所需ms), ...]（须插值的单元）。

    触发条件（满足其一即触发该整句阅读感知插值）：
    a) **长句碎片**（硬约束，用户：单句时长通常 ≥1s）：单元时长 < min_frag_ms（默认 1000ms）
    b) **显著阅读失配**（倒装语序/中英时长差异"很大"才插值，用户问题4）：
       单元时长 < 阅读所需 × ratio（默认 0.7）**且** 失配 ≥ min_gap_ms（默认 300ms）——
       轻微差异（如 3271ms vs 所需 3290ms）不触发，避免时间轴过度偏离 cue 锚定。

    例：13 字单元「亚利桑那州立大学的电气工程硕士学位」阅读需 2.6s，若英文 cue 只分到 0.8s：
    0.8s < 1s（碎片，a 触发）且 0.8 < 2.6×0.7 失配 1.82s ≥ 300ms（b 触发）→ 插值（S6 实证）。
    """
    if speed <= 0:
        return []
    out = []
    for u0, u1, u2, zh, _en, _p1, _p2 in segs:
        d = u2 - u1
        need = cjk_reading_ms(zh, speed)
        if d < min_frag_ms:
            out.append((u0, d, need))
        elif need > 0 and d < need * ratio and (need * ratio - d) >= min_gap_ms:
            out.append((u0, d, need))
    return out


def _allocate_by_weight(units, weights, start, end, real_bounds, snap_ms):
    """通用：按权重比例分配整句区间 → 就近吸附真实 cue 边界（≤ snap_ms，空隙内无边界则吸附前后沿，不吞空隙）
    → 无则 100ms 取整预测点。返回 timeline 片段（结构同 allocate_unit_cues）。"""
    total = sum(weights) or 1
    T = max(0, end - start)
    acc = 0.0
    raw = []
    for w in weights[:-1]:
        acc += w
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


def split_shared_cue_bounds(units, unit_cues, cues, cue_offsets):
    """相邻单元共享 cue → 中间按两侧字符比例估算切分点，返回每单元 [start, end]（毫秒 int）。

    共用核心：回填 allocate_unit_cues 与 check-r03 预估 estimate_unit_durations 都调用——
    保证「预估时长」与「回填实际分配」同构（S6b 预估 782ms ≈ 实际 783ms 的根基），避免两套逻辑漂移。
    纯计算、不写告警、不做首末裁剪/重叠兜底（由调用方按需处理）。
    """
    bounds = []
    for _u, uc in zip(units, unit_cues):
        usi, uei, _upos = uc
        bounds.append([cues[usi]["start"], cues[uei]["end"]])
    for i in range(1, len(bounds)):
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
            bounds[i - 1][1] = t
            bounds[i][0] = t
    return bounds


def allocate_unit_cues(s, a, units, unit_cues, cues, cue_offsets, alerts):
    """句内分配·单元级 cue 锚定分支：每单元命中自身 cue 区间（共享 cue 按字符比例切分，split 共用）
    → 首末裁剪到整句边界 → 时间重叠顺延。返回 timeline 片段。
    """
    bounds = split_shared_cue_bounds(units, unit_cues, cues, cue_offsets)
    segs = []
    for i, (u, uc) in enumerate(zip(units, unit_cues)):
        segs.append([u[0], bounds[i][0], bounds[i][1], u[2], u[1], False, False])
    if segs:
        segs[0][1] = max(segs[0][1], a["start"])
        segs[-1][2] = min(segs[-1][2], a["end"])
    # 共享 cue 告警（切分已在 split_shared_cue_bounds 完成，此处只报告）
    for i in range(1, len(segs)):
        if unit_cues[i - 1][1] == unit_cues[i][0]:
            j = unit_cues[i][0]
            alerts.append(
                f"🔗 单元共享 cue c{cues[j]['idx']}（{cues[j]['text'][:30]}...）中间断句估算切分 {fmt(bounds[i][0])}"
            )
    # 相邻单元时间重叠兜底（非共享）：后单元顺延
    for i in range(1, len(segs)):
        if segs[i][1] < segs[i - 1][2]:
            segs[i][1] = segs[i - 1][2]
    return [(u0, int(u1), int(u2), zh, en, p1, p2) for u0, u1, u2, zh, en, p1, p2 in segs]


def allocate_by_ratio(units, start, end, real_bounds, snap_ms):
    """句内分配·字数比例兜底：按中文长度比例算切分点 → 就近吸附真实 cue 边界
    （≤ snap_ms，空隙内无边界则吸附空隙前后沿，不吞空隙，S56 实证）→ 无则 100ms 取整预测点。返回 timeline 片段。
    """
    return _allocate_by_weight(units, [len(u[2]) for u in units], start, end, real_bounds, snap_ms)


def allocate_by_reading(units, start, end, real_bounds, snap_ms, speed=5.0):
    """句内分配·阅读感知插值：按各单元中文阅读所需时长（cjk_reading_ms）比例分配整句区间
    → 就近吸附真实 cue 边界（≤ snap_ms，不吞空隙）→ 无则 100ms 取整预测点。

    与 allocate_by_ratio 同构（比例 + 吸附），但权重 = 阅读时长而非字符数；
    触发条件（阅读失配 needs_reading_interp）由调用方判断。返回 timeline 片段。
    """
    return _allocate_by_weight(units, [max(1, cjk_reading_ms(u[2], speed)) for u in units],
                               start, end, real_bounds, snap_ms)


def estimate_unit_durations(s, a, units, unit_cues, cues, cue_offsets):
    """预估各单元回填后的实际时长（共享 cue 切分 + 首末裁剪，与 allocate_unit_cues 同构、共用 split）。

    供 check-r03 中英失配预估使用——只算时长、不写告警。
    a 需含 pos/pos_end，可选 start/end（有则首末裁剪）。
    返回 [(est_start, est_end), ...]；异常返回 None（调用方跳过）。
    """
    try:
        bounds = split_shared_cue_bounds(units, unit_cues, cues, cue_offsets)
        # 首末单元裁剪到整句边界（与 allocate_unit_cues 一致，预估贴近回填）
        if bounds:
            bounds[0][0] = max(bounds[0][0], a.get("start", bounds[0][0]))
            bounds[-1][1] = min(bounds[-1][1], a.get("end", bounds[-1][1]))
        # 时间重叠兜底（后单元顺延），预估误差兜底
        for i in range(1, len(bounds)):
            if bounds[i][0] < bounds[i - 1][1]:
                bounds[i][0] = bounds[i - 1][1]
        return bounds
    except Exception:
        return None
