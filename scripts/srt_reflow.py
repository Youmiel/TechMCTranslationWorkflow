# -*- coding: utf-8 -*-
"""时间轴语义回填（Semantic Timeline Refill）— 回填工作流（reflow-redstone）的确定性时间运算

子命令：
  reflow    r03_reflow_plan.md + 01_subtitle_asr_fixed.srt -> r04_refill.srt + r04_alerts.md
            整句锚定 -> 单元级 cue 锚定 -> 分割点就近吸附真实 cue 边界 -> 100ms 取整预测点（兜底）
  attach-en r04_refill.srt + r03_reflow_plan.md -> 双语 SRT（en-zh，英文行 = r03 英文片段）

用法（命令根 = Project_Main/）：
  python scripts/srt_reflow.py reflow r03_reflow_plan.md 01_subtitle_asr_fixed.srt -o r04_refill.srt [--snap-ms 300]
  python scripts/srt_reflow.py attach-en r04_refill.srt r03_reflow_plan.md -o r04_bilingual.srt

语义判断（分句对应、拆/合、切分位置）由 Agent 写入 r03 方案，脚本只做确定性时间运算。
阈值与 reflow-redstone SKILL 一致：长停顿 >5s / 剪辑跳转 >10s / 超长单元 >15s 或 >2×中位。
"""
import argparse
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

TS_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})")
BRACKET_RE = re.compile(r"\[[^\]]*\]")
NORM_RE = re.compile(r"[^a-z0-9']")


def parse_time(s):
    m = TS_RE.match(s.strip())
    if not m:
        raise ValueError(f"bad time: {s}")
    h, mm, ss, ms = (int(x) for x in m.groups())
    return h * 3600000 + mm * 60000 + ss * 1000 + ms


def fmt(ms):
    ms = max(0, int(ms))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)


def norm(s):
    """归一化：小写 + 去非字母数字撇号字符（标点/空白/大小写不影响匹配）"""
    return NORM_RE.sub("", s.lower())


def parse_srt(path):
    """01 解析：返回 [{'idx','start','end','text'}]，剔除 [Music] 等方括号标记 cue"""
    text = Path(path).read_text(encoding="utf-8-sig")
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) < 2 or not re.fullmatch(r"\d+", lines[0]):
            continue
        m = re.match(
            r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})", lines[1]
        )
        if not m:
            continue
        body = " ".join(lines[2:])
        body = BRACKET_RE.sub("", body).strip()
        if not body:
            continue  # [Music] 等非语音 cue 剔除
        cues.append(
            {"idx": int(lines[0]), "start": parse_time(m.group(1)), "end": parse_time(m.group(2)), "text": body}
        )
    return cues


class Sentence:
    """r03 整句组：S<n>（或合句 S<n+m>）"""

    def __init__(self, key, en, zh, rel, units):
        self.key = key          # 如 S1 / S19+20
        self.en = en            # 整句英文全文（锚定用）
        self.zh = zh            # 整句中文（对照）
        self.rel = rel          # 1:1 / 1:n / n:1
        self.units = units      # [(unit_key, en_frag, zh_frag), ...]


def parse_r03(path):
    """解析 r03_reflow_plan.md → [Sentence]"""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    sentences = []
    cur = None
    for line in lines:
        line = line.rstrip()
        m = re.match(r"^##\s*(S[\d+]+)\s*$", line)
        if m:
            cur = {"key": m.group(1), "en": None, "zh": None, "rel": None, "units": []}
            sentences.append(cur)
            continue
        if cur is None:
            continue
        m = re.match(r"^- EN:\s?(.*)$", line)
        if m and cur["en"] is None and not cur["units"]:
            cur["en"] = m.group(1)
            continue
        m = re.match(r"^- ZH:\s?(.*)$", line)
        if m and cur["zh"] is None and not cur["units"]:
            cur["zh"] = m.group(1)
            continue
        m = re.match(r"^- 关系:\s?(.*)$", line)
        if m and cur["rel"] is None:
            cur["rel"] = m.group(1).strip()
            continue
        m = re.match(r"^###\s*(S[\d+]+[a-z])$", line)
        if m:
            cur["units"].append({"key": m.group(1), "en": None, "zh": None})
            continue
        if cur["units"]:
            u = cur["units"][-1]
            m = re.match(r"^- EN:\s?(.*)$", line)
            if m and u["en"] is None:
                u["en"] = m.group(1)
                continue
            m = re.match(r"^- ZH:\s?(.*)$", line)
            if m and u["zh"] is None:
                u["zh"] = m.group(1)

    out = []
    for s in sentences:
        if s["en"] is None or s["rel"] is None:
            raise ValueError(f"r03 解析失败（缺 EN/关系）: {s['key']}")
        units = []
        for u in s["units"]:
            if u["en"] is None or u["zh"] is None:
                raise ValueError(f"r03 解析失败（子单元缺 EN/ZH）: {u['key']}")
            units.append((u["key"], u["en"], u["zh"]))
        out.append(Sentence(s["key"], s["en"], s["zh"], s["rel"], units))
    return out


def build_full(cues):
    """拼接全文（归一化）+ char→cue_index 映射 + 每 cue 在 full 中的起始偏移"""
    full_chars = []
    mapping = []
    cue_offsets = []  # cue 索引 -> full 中字符偏移
    off = 0
    for ci, c in enumerate(cues):
        n = norm(c["text"])
        cue_offsets.append(off)
        full_chars.append(n)
        mapping.extend([ci] * len(n))
        off += len(n)
    return "".join(full_chars), mapping, cue_offsets


def anchor(sentence, full, mapping, cues, alerts):
    """整句锚定：归一化子串搜索 → cue 范围 → [start, end] + 匹配偏移"""
    n = norm(sentence.en)
    pos = full.find(n)
    if pos == -1:
        alerts.append(f"⚠️ 整句 {sentence.key} 锚定失败（全文未找到），按顺序相邻锚定兜底")
        return None
    pos2 = full.find(n, pos + 1)
    if pos2 != -1:
        alerts.append(f"⚠️ 整句 {sentence.key} 非唯一命中（全文出现 ≥2 次），取第一处")
    start_idx = mapping[pos]
    end_idx = mapping[pos + len(n) - 1]
    return {
        "start": cues[start_idx]["start"], "end": cues[end_idx]["end"],
        "si": start_idx, "ei": end_idx,
        "pos": pos, "pos_end": pos + len(n) - 1,
    }


def resolve_shared_cues(anchored, cues, cue_offsets, alerts):
    """相邻整句共享 cue 处理：cue 内部按两侧字符数比例估算切分点（中间断句估算切分）

    anchored 元素为 dict{key,start,end,si,ei,pos,pos_end}，本函数直接修改 start/end。
    """
    for i in range(1, len(anchored)):
        prev, cur = anchored[i - 1], anchored[i]
        if cur["start"] < prev["end"] and prev["ei"] == cur["si"]:
            j = prev["ei"]
            cue = cues[j]
            cj_off = cue_offsets[j]
            cj_len = len(norm(cue["text"]))
            a_chars = prev["pos_end"] - cj_off + 1      # 前句在 cue 内的字符数
            b_chars = (cj_off + cj_len) - cur["pos"]    # 后句在 cue 内的字符数
            if a_chars > 0 and b_chars > 0:
                t = cue["start"] + (cue["end"] - cue["start"]) * a_chars / (a_chars + b_chars)
            else:
                t = cue["end"]
            if not (prev["end"] - 1 < t < cur["start"] + 1 or t > prev["start"]):
                pass
            prev["end"] = int(t)
            cur["start"] = int(t)
            alerts.append(
                f"🔗 共享 cue c{cue['idx']}（{cue['text'][:30]}...）中间断句估算切分 {fmt(int(t))}"
            )
        elif cur["start"] < prev["end"]:
            # 非共享重叠兜底：后句顺延
            cur["start"] = prev["end"]
            alerts.append(f"⚠️ {prev['key']}→{cur['key']} 锚定重叠兜底顺延 {fmt(prev['end'])}")


def unit_anchor_in_sentence(s, a, full, mapping, cues):
    """单元级 cue 锚定：在整句锚定字符区间 [pos, pos_end] 内顺序搜索各单元文本

    返回 [(si, ei, pos), ...]（每单元起止 cue 索引 + full 内起始偏移）；
    任一单元未命中（文本不一致）返回 None，调用方降级为字数比例兜底。
    """
    pos, pos_end = a["pos"], a["pos_end"]
    cursor = pos
    out = []
    for u in s.units:
        n = norm(u[1])
        if not n:
            return None
        p = full.find(n, cursor, pos_end + 1)
        if p == -1:
            return None
        out.append((mapping[p], mapping[p + len(n) - 1], p))
        cursor = p + len(n)
    return out


def reflow(r03_path, srt_path, out_path, alert_path, snap_ms):
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
            anchored.append({"s": s, "start": prev_end, "end": prev_end, "si": None, "ei": None,
                             "pos": None, "pos_end": None})
            continue
        anchored.append({"s": s, **r})

    # 共享 cue 中间断句估算切分（跨整句重叠消除）
    resolve_shared_cues(anchored, cues, cue_offsets, alerts)

    real_bounds = set()
    for c in cues:
        real_bounds.add(c["start"])
        real_bounds.add(c["end"])

    # 句内分配
    timeline = []  # (unit_key, start, end, zh, en_frag, is_pred_start, is_pred_end)
    for a in anchored:
        s, start, end, si, ei = a["s"], a["start"], a["end"], a["si"], a["ei"]
        units = s.units or [(s.key, s.en, s.zh)]
        # 单元级 cue 锚定（优先）：整句锚定区间内顺序搜索各单元文本 → 每单元直接取自身 cue 区间
        unit_cues = None
        if len(units) > 1 and a.get("pos") is not None:
            unit_cues = unit_anchor_in_sentence(s, a, full, mapping, cues)
        if unit_cues is not None:
            segs = []
            for i, (u, uc) in enumerate(zip(units, unit_cues)):
                usi, uei, upos = uc
                segs.append([u[0], cues[usi]["start"], cues[uei]["end"], u[2], u[1], False, False])
            # 首单元 start / 末单元 end 裁剪到整句锚定区间（兼容共享 cue 中间断句切分）
            if segs:
                segs[0][1] = max(segs[0][1], start)
                segs[-1][2] = min(segs[-1][2], end)
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
            for u0, u1, u2, zh, en, p1, p2 in segs:
                timeline.append((u0, int(u1), int(u2), zh, en, p1, p2))
            continue
        # 兜底：字数比例分配（分割点就近吸附真实 cue 边界 / 100ms 预测点）
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
            # 1) 吸附最近真实 cue 边界（≤ snap_ms；空隙内无边界则吸附空隙前/后的真实边界，不吞空隙，S56 实证）
            snapped, best = None, None
            for rb in real_bounds:
                d = abs(rb - b)
                if best is None or d < best:
                    best = d
                    snapped = rb
            if best is not None and best <= snap_ms and snapped > bounds[-1] + 100 and snapped < end - 100:
                bounds.append(int(snapped))
                pred_bounds.append(False)
                continue
            # 2) 100ms 取整预测点
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
            pred_bounds[-1] = True
        for i, u in enumerate(units):
            timeline.append(
                (u[0], int(bounds[i]), int(bounds[i + 1]), u[2], u[1],
                 i > 0 and pred_bounds[i - 1], i < len(units) - 1 and pred_bounds[i])
            )

    # 时长分布与告警
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

    # 预测点清单（去重）
    preds = sorted({t[1] for t in timeline if t[5]} | {t[2] for t in timeline if t[6]})
    alerts.append(f"预测点（100ms 取整、未吸附）: {len(preds)} 处 -> " + ", ".join(fmt(p) for p in preds))
    alerts.append(f"剪辑跳转点: {sum(1 for i in range(1, len(timeline)) if timeline[i][1] - timeline[i-1][2] > 10000)} 处")
    alerts.append(f"超长单元: {sum(1 for t in timeline if t[2]-t[1] > max(15000, 2*median))} 处")
    alerts.append(f"超短单元(<300ms): {sum(1 for t in timeline if t[2]-t[1] < 300)} 处")

    # 行宽预警（中文 >20）
    for t in timeline:
        w = zh_width(t[3])
        if w > 20:
            alerts.append(f"📏 行宽 {w:.1f}（>{20}）{t[0]}: {t[3]}")

    # 输出 r04 SRT（中文单语预览）
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
    return timeline


def zh_width(s):
    CJK = re.compile(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]")
    LATIN = re.compile(r"[A-Za-z]")
    DIGIT = re.compile(r"[0-9]")
    w = 0.0
    for ch in s:
        if CJK.match(ch):
            w += 1.0
        elif LATIN.match(ch):
            w += 1.5
        elif DIGIT.match(ch):
            w += 1.0
        elif ch == " ":
            w += 0.5
        else:
            w += 1.0
    return w


def attach_en(r04_path, r03_path, out_path):
    sentences = parse_r03(r03_path)
    # 全部单元按序
    units = []
    for s in sentences:
        units.extend(s.units or [(s.key, s.en, s.zh)])
    # 解析 r04 cue
    text = Path(r04_path).read_text(encoding="utf-8-sig")
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) < 2 or not re.fullmatch(r"\d+", lines[0]):
            continue
        m = re.match(r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})", lines[1])
        if m:
            cues.append((int(lines[0]), m.group(1) + " --> " + m.group(2), " ".join(lines[2:])))
    if len(cues) != len(units):
        print(f"❌ cue 数 {len(cues)} ≠ 单元数 {len(units)}，中止")
        return
    blocks = []
    warn_dup = []
    for i, (num, ts, zh) in enumerate(cues):
        ukey, en_frag, zh_frag = units[i]
        if zh.strip() != zh_frag.strip():
            warn_dup.append(f"⚠️ 单元 {ukey} 中文与 r03 不一致（r04 回填后文本漂移？）")
        if i > 0 and units[i - 1][1] == en_frag:
            warn_dup.append(f"⚠️ 相邻单元 {units[i-1][0]}→{ukey} 英文片段完全相同（拆句未细分互斥片段？）")
        blocks.append(f"{num}\n{ts}\n{en_frag}\n{zh_frag}")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    print(f"已写入双语 {out_path}（{len(blocks)} cue）")
    for w in warn_dup:
        print("  " + w)


def main():
    ap = argparse.ArgumentParser(description="时间轴语义回填（reflow/attach-en）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("reflow")
    p1.add_argument("r03", help="r03_reflow_plan.md（回填方案）")
    p1.add_argument("srt", help="01_subtitle_asr_fixed.srt（cue 时间戳）")
    p1.add_argument("-o", dest="out", default="r04_reflow.srt")
    p1.add_argument("--alert", dest="alert", default="r04_alerts.md")
    p1.add_argument("--snap-ms", type=int, default=300, help="分割点吸附真实 cue 边界的最大距离（默认 300ms）")

    p2 = sub.add_parser("attach-en")
    p2.add_argument("r04", help="r04_refill.srt（回填后单语）")
    p2.add_argument("r03", help="r03_reflow_plan.md（英文片段）")
    p2.add_argument("-o", dest="out", default="r04_bilingual.srt")

    args = ap.parse_args()
    if args.cmd == "reflow":
        reflow(args.r03, args.srt, args.out, args.alert, args.snap_ms)
    elif args.cmd == "attach-en":
        attach_en(args.r04, args.r03, args.out)


if __name__ == "__main__":
    main()
