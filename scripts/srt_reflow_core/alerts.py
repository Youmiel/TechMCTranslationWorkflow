# -*- coding: utf-8 -*-
"""回填告警（build_alerts）与落盘（write_outputs / write_anchored_json）"""
import json
from pathlib import Path

from .io import fmt, text_width


def build_alerts(alerts, timeline, anchored, cues):
    """回填告警：时长分布/超长超短/内部空隙/剪辑跳转/预测点/行宽（追加到 alerts）"""
    durs = sorted(t[2] - t[1] for t in timeline)
    median = durs[len(durs) // 2] if durs else 0
    alerts.append(f"单元数: {len(timeline)}  时长中位: {median}ms")
    long_th = max(15000, 2 * median)
    for t in timeline:
        d = t[2] - t[1]
        if d > long_th:
            alerts.append(f"⏱️ 超长单元 {t[0]} {d}ms（>{long_th}ms）: {t[3]}")
        elif d < 300:
            alerts.append(f"⏱️ 超短单元 {t[0]} {d}ms: {t[3]}")

    # 单元内 gap > 5s（锚定 cue 范围内相邻 cue 间隔）
    for a in anchored:
        s, si, ei = a["s"], a["si"], a["ei"]
        if si is None or ei is None:
            continue
        for k in range(si, ei):
            gap = cues[k + 1]["start"] - cues[k]["end"]
            if gap > 5000:
                alerts.append(
                    f"⏱️ 整句 {s.key} 内部空隙 {gap}ms（c{cues[k]['idx']}→c{cues[k+1]['idx']}）: {cues[k]['text'][:30]}... / {cues[k+1]['text'][:30]}..."
                )

    # 相邻单元边界间隔 > 10s（剪辑跳转）
    for i in range(1, len(timeline)):
        gap = timeline[i][1] - timeline[i - 1][2]
        if gap > 10000:
            alerts.append(
                f"✂️ 剪辑跳转点 {fmt(timeline[i-1][2])}→{fmt(timeline[i][1])}（间隔 {gap}ms）：{timeline[i-1][0]} → {timeline[i][0]}"
            )

    # 预测点清单（去重）+ 汇总
    preds = sorted({t[1] for t in timeline if t[5]} | {t[2] for t in timeline if t[6]})
    alerts.append(f"预测点（100ms 取整、未吸附）: {len(preds)} 处 -> " + ", ".join(fmt(p) for p in preds))
    alerts.append(f"剪辑跳转点: {sum(1 for i in range(1, len(timeline)) if timeline[i][1] - timeline[i-1][2] > 10000)} 处")
    alerts.append(f"超长单元: {sum(1 for t in timeline if t[2]-t[1] > max(15000, 2*median))} 处")
    alerts.append(f"超短单元(<300ms): {sum(1 for t in timeline if t[2]-t[1] < 300)} 处")

    # 行宽预警（中文 >20）
    for t in timeline:
        w = text_width(t[3])
        if w > 20:
            alerts.append(f"📏 行宽 {w:.1f}（>{20}）{t[0]}: {t[3]}")


def write_outputs(timeline, alerts, out_path, alert_path):
    """落盘 r04 SRT（中文单语预览）+ 告警清单，并打印摘要"""
    blocks = []
    for i, t in enumerate(timeline, 1):
        blocks.append(f"{i}\n{fmt(t[1])} --> {fmt(t[2])}\n{t[3]}")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    Path(alert_path).write_text("\n".join(alerts) + "\n", encoding="utf-8")
    print(f"已写入 {out_path}（{len(timeline)} cue）")
    print(f"已写入 {alert_path}")
    for a in alerts:
        print("  " + a)


def write_anchored_json(detail, path):
    """落盘锚定明细（r03_anchored.json）：逐整句锚定状态 + 单元 cue 命中情况（机器可读、可审）"""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(detail, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已写入 {path}（{len(detail)} 整句锚定明细）")
