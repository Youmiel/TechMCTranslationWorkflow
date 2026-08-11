# -*- coding: utf-8 -*-
"""回填告警（build_alerts）/ 回填后时长复核（check_duration）与落盘（write_outputs / write_anchored_json）"""
import json
from pathlib import Path

from .io import fmt, text_width, parse_srt
from .plan import parse_r03
from .allocate import cjk_reading_ms, MIN_FRAG_MS, READING_MISMATCH_RATIO, READING_MIN_GAP_MS


def _unit_span_index(anchored):
    """构建 单元 key → (整句 key, 子单元数) 映射（长句碎片 vs 独立短句分类）"""
    sent_count, sent_key = {}, {}
    for a in anchored:
        s = a["s"]
        units = s.units or [(s.key, s.en, s.zh)]
        n = len(units)
        for u in units:
            sent_count[u[0]] = n
            sent_key[u[0]] = s.key
    return sent_count, sent_key


def build_alerts(alerts, timeline, anchored, cues):
    """回填告警：时长分布/超长极短/长句碎片/内部空隙/剪辑跳转/预测点/行宽（追加到 alerts）"""
    durs = sorted(t[2] - t[1] for t in timeline)
    median = durs[len(durs) // 2] if durs else 0
    alerts.append(f"单元数: {len(timeline)}  时长中位: {median}ms")
    long_th = max(15000, 2 * median)
    sent_count, sent_key = _unit_span_index(anchored)
    n_frag = 0
    for t in timeline:
        d = t[2] - t[1]
        if d > long_th:
            alerts.append(f"⏱️ 超长单元 {t[0]} {d}ms（>{long_th}ms）: {t[3]}")
        elif d < 300:
            alerts.append(f"⏱️ 极短单元 {t[0]} {d}ms: {t[3]}")
        elif d < MIN_FRAG_MS:
            n = sent_count.get(t[0], 1)
            if n >= 2:
                n_frag += 1
                alerts.append(
                    f"🔪 长句碎片 {t[0]} {d}ms（整句 {sent_key.get(t[0], '?')} 切成 {n} 段，"
                    f"此段 <{MIN_FRAG_MS}ms）: {t[3]} —— 回报 Agent 裁决（合并 / 调整切分点 / 接受）"
                )
            else:
                alerts.append(f"⏱️ 短句单元 {t[0]} {d}ms: {t[3]}（独立短句，人工复核可接受性）")

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
    alerts.append(f"极短单元(<300ms): {sum(1 for t in timeline if t[2]-t[1] < 300)} 处")
    alerts.append(f"长句碎片(<{MIN_FRAG_MS}ms): {n_frag} 处")

    # 行宽预警（软 22 / 硬 26；>26 硬违规已由 check-r03 拦截）
    for t in timeline:
        w = text_width(t[3])
        if w > 22:
            alerts.append(f"📏 行宽 {w:.1f}（>22 软预警）{t[0]}: {t[3]}")


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
    """落盘锚定明细（r03_anchored.jsonl，JSONL）：每行一个整句对象——逐整句锚定状态 + 单元 cue 命中情况
    （机器可读、可审；JSONL 按行读取/grep 单句，避免大块 JSON 数组一次解析）"""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(obj, ensure_ascii=False) for obj in detail]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已写入 {path}（{len(detail)} 整句锚定明细，JSONL 每行一句）")


def check_duration(r04_path, r03_path, min_ms=MIN_FRAG_MS, cjk_speed=5.0,
                   mismatch_ratio=READING_MISMATCH_RATIO, min_gap_ms=READING_MIN_GAP_MS):
    """回填后时长复核（Agent 智能判断辅助，不重算时间轴）：长句碎片 + 独立短句 + 阅读失配检测。

    读 r03（单元→整句/子单元数）与 r04（时间轴），按序对齐，输出三类清单：
    - 🔪 长句碎片：同一整句拆出的子单元中时长 < min_ms（默认 1s）的——须 Agent 裁决（合并/调整切分点/接受）
    - ⏱️ 独立短句：单单元句时长 < min_ms（语义自足，仅复核可接受性）
    - 📖 阅读失配：单元时长 < 中文阅读所需×mismatch_ratio 且失配 ≥ min_gap_ms（倒装/中英时长差；
      与回填插值口径一致，轻微差异不报）

    退出码：有长句碎片返回 1（提示需处理，Agent 回 r03 调整后重跑）；否则 0。
    """
    sentences = parse_r03(r03_path)
    cues = parse_srt(r04_path)
    units = []
    for s in sentences:
        units.extend(s.units or [(s.key, s.en, s.zh)])
    if len(cues) != len(units):
        print(f"❌ r04 cue 数 {len(cues)} ≠ r03 单元数 {len(units)}，中止")
        return 1
    sent_count, sent_key = {}, {}
    for s in sentences:
        us = s.units or [(s.key, s.en, s.zh)]
        for u in us:
            sent_count[u[0]] = len(us)
            sent_key[u[0]] = s.key

    frags, shorts, mism = [], [], []
    for c, u in zip(cues, units):
        d = c["end"] - c["start"]
        n = sent_count.get(u[0], 1)
        if d < min_ms:
            (frags if n >= 2 else shorts).append(
                (u[0], d, c["text"], n, sent_key.get(u[0], "?")))
        need = cjk_reading_ms(c["text"], cjk_speed)
        if cjk_speed > 0 and need > 0 and d < need * mismatch_ratio \
                and (need * mismatch_ratio - d) >= min_gap_ms:
            mism.append((u[0], d, need, c["text"]))

    print(f"r04: {r04_path}  r03: {r03_path}  单元数: {len(units)}")
    print(f"阈值: 长句碎片 <{min_ms}ms；阅读失配 < 阅读所需×{mismatch_ratio} 且失配 ≥{min_gap_ms}ms（{cjk_speed} 字/秒）")
    print("-" * 60)
    for uk, d, txt, n, sk in frags:
        print(f"🔪 长句碎片 {uk} {d}ms（整句 {sk} 切成 {n} 段）: {txt}")
        print(f"    → 裁决: 合并到相邻单元 / 调整 r03 切分点 / 接受（独立语义块但读得快）")
    for uk, d, txt, n, sk in shorts:
        print(f"⏱️ 独立短句 {uk} {d}ms: {txt}（单单元句，语义自足，复核可接受性）")
    for uk, d, need, txt in mism:
        print(f"📖 阅读失配 {uk} {d}ms < 阅读所需×{mismatch_ratio}（需 {need}ms）: {txt}")
        print(f"    → 建议: 回填走阅读插值（--cjk-speed）或人工调切分点（倒装语序/中英时长差）")
    print("-" * 60)
    print(f"结果: 长句碎片 {len(frags)} / 独立短句 {len(shorts)} / 阅读失配 {len(mism)}")
    if frags:
        print("❌ 存在长句碎片 —— 建议回 r03 调整切分点（合并或改切）后重跑 reflow 复核")
        return 1
    if shorts:
        print("⚠️ 存在独立短句 —— 语义自足可接受，人工复核确认")
    if mism:
        print("⚠️ 存在阅读失配 —— 已由阅读插值覆盖则忽略；未覆盖须人工判断")
    print("✅ check-duration 通过（无长句碎片）")
    return 0
