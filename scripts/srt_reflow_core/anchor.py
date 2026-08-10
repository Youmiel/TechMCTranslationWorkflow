# -*- coding: utf-8 -*-
"""锚定：整句锚定（anchor）/ 共享 cue 中间断句估算（resolve_shared_cues）/ 单元级 cue 锚定（unit_anchor_in_sentence）"""
from .io import norm, fmt


def anchor(sentence, full, mapping, cues, alerts):
    """整句锚定：归一化子串搜索 → cue 范围 → [start, end] + 匹配偏移"""
    n = norm(sentence.en)
    pos = full.find(n)
    if pos == -1:
        alerts.append(f"⚠️ 整句 {sentence.key} 锚定失败（全文未找到），按顺序相邻锚定兜底")
        return None
    status = "unique"
    pos2 = full.find(n, pos + 1)
    if pos2 != -1:
        status = "non-unique"
        alerts.append(f"⚠️ 整句 {sentence.key} 非唯一命中（全文出现 ≥2 次），取第一处")
    start_idx = mapping[pos]
    end_idx = mapping[pos + len(n) - 1]
    return {
        "key": sentence.key,
        "status": status,
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
