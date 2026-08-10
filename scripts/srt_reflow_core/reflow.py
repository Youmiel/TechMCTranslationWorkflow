# -*- coding: utf-8 -*-
"""reflow 主流程编排：r03 方案 + 01 -> r04 时间轴 + r04_alerts + r03_anchored.json"""
from .io import parse_srt, build_full, norm, fmt
from .plan import parse_r03
from .anchor import anchor, resolve_shared_cues, unit_anchor_in_sentence
from .allocate import allocate_unit_cues, allocate_by_ratio
from .alerts import build_alerts, write_outputs, write_anchored_json


def reflow(r03_path, srt_path, out_path, alert_path, anchored_path, snap_ms):
    sentences = parse_r03(r03_path)
    cues = parse_srt(srt_path)
    full, mapping, cue_offsets = build_full(cues)
    alerts = []

    # 拆句互斥性校验：子单元 EN 拼接（归一化）== 整句 EN（归一化）
    for s in sentences:
        if s.rel == "1:n" and s.units:
            joined = "".join(norm(u[1]) for u in s.units)
            if joined != norm(s.en):
                alerts.append(
                    f"⚠️ 拆句 {s.key} 英文片段拼接 ≠ 整句（互斥性破坏），脚本将按整句锚定但双语英文行可能错位"
                )

    # 逐整句锚定（resolve_shared_cues 会修改 start/end，故存 dict）
    anchored = []
    for s in sentences:
        r = anchor(s, full, mapping, cues, alerts)
        if r is None:
            # 兜底：顺序分配（用上一句 end 作 start，无 cue 则 0）
            prev_end = anchored[-1]["end"] if anchored else 0
            anchored.append({"s": s, "status": "failed", "start": prev_end, "end": prev_end,
                             "si": None, "ei": None, "pos": None, "pos_end": None})
            continue
        anchored.append({"s": s, **r})

    # 共享 cue 中间断句估算切分（跨整句重叠消除）
    resolve_shared_cues(anchored, cues, cue_offsets, alerts)

    real_bounds = set()
    for c in cues:
        real_bounds.add(c["start"])
        real_bounds.add(c["end"])

    # 句内分配（单元级 cue 锚定优先，字数比例兜底）
    timeline = []      # (unit_key, start, end, zh, en_frag, is_pred_start, is_pred_end)
    anchor_detail = [] # 逐整句锚定明细 → r03_anchored.json
    for a in anchored:
        s, start, end = a["s"], a["start"], a["end"]
        units = s.units or [(s.key, s.en, s.zh)]
        unit_cues = None
        if len(units) > 1 and a.get("pos") is not None:
            unit_cues = unit_anchor_in_sentence(s, a, full, mapping, cues)
        if unit_cues is not None:
            timeline.extend(allocate_unit_cues(s, a, units, unit_cues, cues, cue_offsets, alerts))
            unit_hits = [{"hit": True, "cues": [cues[uc[0]]["idx"], cues[uc[1]]["idx"]]} for uc in unit_cues]
        else:
            timeline.extend(allocate_by_ratio(units, start, end, real_bounds, snap_ms))
            if len(units) == 1:
                unit_hits = [{"hit": a.get("status") != "failed", "cues": None}]
            else:
                unit_hits = [{"hit": False, "cues": None} for _ in units]
        anchor_detail.append({
            "key": s.key,
            "rel": s.rel,
            "en": s.en,
            "zh": s.zh,
            "anchor": a.get("status", "unique"),
            "start": fmt(start),
            "end": fmt(end),
            "span_ms": end - start,
            "units": [
                {"key": u[0], "en": u[1], "zh": u[2], "hit": uh["hit"], "cues": uh["cues"]}
                for u, uh in zip(units, unit_hits)
            ],
        })

    # 告警 + 落盘
    build_alerts(alerts, timeline, anchored, cues)
    write_outputs(timeline, alerts, out_path, alert_path)
    write_anchored_json(anchor_detail, anchored_path)
    return timeline
