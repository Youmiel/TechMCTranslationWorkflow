# -*- coding: utf-8 -*-
"""继承时间 + 回填（新 reflow2 工作流核心）：中文 Z 句继承 E 固化时间 → 拆子段 → r04

背景（2026-09-09 设计「时间轴源头固化」）：E 句时间已在源头固化（en_timeline，只读真值锚），
Z 句（中文）通过对齐（align，Z组=E组）**继承** E 固化时间——不再「整句 EN 全文搜索猜时间 +
共享 cue 切分 + 预测点」（现 reflow 的回填机制）。

本脚本做两件事：
1. **继承**：每 Z 组 = 一个中文整句，对应 E 组 → 时间 = E 组覆盖范围 [首 E.start, 末 E.end]
   （E 固化时间已含共享 cue 字符占比切分，故继承天然零重叠）
2. **拆子段**：Z 句文本超宽（>hard_max）或时长碎片（<min_ms）时按中文阅读速度/宽度比例在
   E 组区间内细分（复用 allocate._allocate_by_weight 逻辑：吸附真实 cue 边界 ≤snap_ms，
   无则 100ms 取整预测点）——阅读舒适优先（≤22 字），不因「尊重原轴」保留超长句。
   拆段标点分级 = 句末标点（。！？…）优先 → 句内标点（，；：—、）；由标点切不动仍超宽的单句
   保留原样并计入告警（此类需回 r02 改写句子，加句内标点）

产物：
- `r04_draft.srt`：标准 SRT 单语中文（显示单元 = Z 整句或子段）
- `r04_alerts.md`：告警（长句碎片/超长/行宽预警），供 Agent 复核（对齐现 reflow 的 r04_alerts）

输入（新工作流独立产物目录 reflow2/）：
- `zh_sentences/chunk_<k>.txt`：Z 句文本列表（`Z<n> <文本>`，脚本切 r02）
- `align/chunk_<k>.txt`：Z 组=E 组 纯号对齐（`Z1 = E1+E2`，task-match LLM 产物）
- `en_timeline/chunk_<k>.txt`：E 句固化时间（`E<n>\t<start> --> <end>...`，源头固化脚本产物）

用法（命令根 = Project_Main/）：
  python scripts/srt_reflow2_backfill.py reflow2/zh_sentences/ reflow2/align/ reflow2/en_timeline/ -o reflow2/r04_draft.srt [--alert reflow2/r04_alerts.md]
退出码：0 = 全部块继承完成；1 = 有块缺 E/Z（对齐不完整，漏句留空标记）。
"""
import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

from srt_reflow_common import collect_chunk_files, fmt, text_width
from srt_reflow_presplit import split_zh, split_recursive, pack_candidates
from srt_reflow_build_r03 import split_en_by_weights

PM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PM not in sys.path:
    sys.path.insert(0, PM)
from scripts.srt_reflow_core.allocate import _allocate_by_weight, cjk_reading_ms

# 行宽阈值（与 reflow check-r03/check-width 一致：软 22 / 硬 26）
SOFT_MAX = 22.0
HARD_MAX = 26.0
# 最小单元时长（< 此值 = 长句碎片，触发拆/并决策）
MIN_FRAG_MS = 1000
# 阅读速度（字/秒，allocate 同款）
CJK_SPEED = 5.0
SNAP_MS = 300

MATCH_RE = re.compile(r"^\s*([ZE][\d+]*(?:\+[ZE][\d+]*)*)\s*=\s*([ZE][\d+]*(?:\+[ZE][\d+]*)*)\s*$")
ET_RE = re.compile(r"^E(\d+)\t(.+?)\t.+?\t(.*)$")   # en_timeline 行：E<n>\t<start> --> <end>\tc..\t文本


def parse_align(text):
    """align → [(Z 号升序, E 号升序)]；跳过空行/# 注释。非法行收集。"""
    out, problems = [], []
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        m = MATCH_RE.match(s)
        if not m:
            problems.append(f"无法解析「{ln.strip()}」")
            continue
        zg = [int(x) for x in re.findall(r"Z(\d+)", m.group(1))]
        eg = [int(x) for x in re.findall(r"E(\d+)", m.group(2))]
        if not zg or not eg:
            problems.append(f"组内无号「{ln.strip()}」")
            continue
        out.append((sorted(zg), sorted(eg)))
    return out, problems


def parse_etimeline(text):
    """en_timeline → {E 号: (start_ms, end_ms, text)}；MISS/- 行跳过（无时间）。"""
    out = {}
    for ln in text.splitlines():
        if ln.startswith("#") or not ln.strip():
            continue
        parts = ln.split("\t")
        if len(parts) < 4 or not parts[0].startswith("E"):
            continue
        eid = int(parts[0][1:])
        ts = parts[1]
        m = re.match(r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})", ts)
        if not m:
            continue  # MISS / 跳过行
        out[eid] = (fmt_to_ms(m.group(1)), fmt_to_ms(m.group(2)), parts[3])
    return out


def fmt_to_ms(s):
    h, mm, ss, ms = (int(x) for x in re.split(r"[:,]", s))
    return h * 3600000 + mm * 60000 + ss * 1000 + ms


def parse_zsent(text):
    """zh_sentences → {Z 号: 文本}（行 `Z<n> <文本>`）。"""
    out = {}
    for ln in text.splitlines():
        if ln.startswith("#") or not ln.strip():
            continue
        m = re.match(r"^Z(\d+)\s+(.*)$", ln)
        if m:
            out[int(m.group(1))] = m.group(2).strip()
    return out


def split_zh_units(text, punct_levels):
    """Z 句按标点切候选段 + 贪心拼合（复用 presplit：只在标点处切、段拼接 == Z 原文）。
    返回 (units, notes)；units = [(文本, 宽度)]；超硬上限/碎片由调用方决策。"""
    cands = split_recursive(text, punct_levels, HARD_MAX)
    units = pack_candidates(cands, HARD_MAX, 5)
    return units


def main():
    ap = argparse.ArgumentParser(description="继承时间 + 回填：中文 Z 句继承 E 固化时间 → 拆子段 → r04（新 reflow2）")
    ap.add_argument("zsent_dir", help="Z 句文本目录：reflow2/zh_sentences/")
    ap.add_argument("align_dir", help="对齐目录：reflow2/align/（Z组=E组，task-match LLM 产物）")
    ap.add_argument("et_dir", help="E 固化时间目录：reflow2/en_timeline/")
    ap.add_argument("-o", "--out", required=True, help="输出 r04_draft.srt（单语中文）")
    ap.add_argument("--bilingual", default=None, help="输出 r04_bilingual.srt（双语 en-zh；默认与 r04 同目录）")
    ap.add_argument("--alert", default=None, help="输出 r04_alerts.md（默认与 r04 同目录）")
    ap.add_argument("--snap-ms", type=int, default=SNAP_MS, help="吸附真实 cue 边界最大距离（默认 300ms）")
    ap.add_argument("--cjk-speed", type=float, default=CJK_SPEED, help="中文阅读速度 字/秒（默认 5）")
    args = ap.parse_args()

    z_blocks = collect_chunk_files(args.zsent_dir)
    a_blocks = collect_chunk_files(args.align_dir)
    e_blocks = collect_chunk_files(args.et_dir)
    if not z_blocks:
        sys.exit(f"❌ zh_sentences 目录无块文件：{args.zsent_dir}")
    keys = sorted(set(z_blocks) & set(a_blocks) & set(e_blocks))
    if not keys:
        sys.exit("❌ zh_sentences/align/en_timeline 无共同块号（先跑 zsent/etimeline/task-match）")

    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    alert_path = args.alert or os.path.join(out_dir, "r04_alerts.md")

    srt_blocks = []     # 每块 [(idx, start, end, zh, en, is_pred)]（全局 cue 号由外层累加）
    alerts = []
    total_cue = 0
    problems = []
    for k in keys:
        with open(a_blocks[k], encoding="utf-8") as fh:
            aligns, ap = parse_align(fh.read())
        with open(e_blocks[k], encoding="utf-8") as fh:
            et = parse_etimeline(fh.read())
        with open(z_blocks[k], encoding="utf-8") as fh:
            zmap = parse_zsent(fh.read())
        problems += [f"chunk_{k:03d}: {p}" for p in ap]

        # 组内：Z 组 → 继承 E 组时间
        block_cues = []   # (zh_text, en_text, start, end, sub_units[(zh,en,start,end)])
        seen_z, seen_e = set(), set()
        for zg, eg in sorted(aligns, key=lambda x: min(x[0])):
            for z in zg:
                seen_z.add(z)
            for e in eg:
                seen_e.add(e)
            if not eg or not all(e in et for e in eg):
                problems.append(f"chunk_{k:03d}: Z{' + '.join('Z%d' % z for z in zg)} 引用的 E 组在 en_timeline 缺失")
                continue
            # E 组时间范围（E 固化时间已含共享 cue 切分，直接取首末）
            starts = [et[e][0] for e in eg]
            ends = [et[e][1] for e in eg]
            start, end = min(starts), max(ends)
            # Z 组文本拼接
            zh_full = "".join(zmap[z] for z in zg if z in zmap)
            en_full = " ".join(et[e][2] for e in eg)
            if not zh_full:
                problems.append(f"chunk_{k:03d}: Z 组 {'+'.join(map(str,zg))} 无对应 Z 文本（zh_sentences 缺句？）")
                continue
            block_cues.append({"z": zg, "e": eg, "zh": zh_full, "en": en_full,
                               "start": start, "end": end})
        # 漏 Z / 漏 E（对齐不完整）
        for z in sorted(set(zmap) - seen_z):
            problems.append(f"chunk_{k:03d}: Z{z} 未对齐（align 漏句？）—— {zmap[z][:30]}")
        for e in sorted(set(et) - seen_e):
            problems.append(f"chunk_{k:03d}: E{e} 未对齐（align 漏句？）")

        # 拆子段决策：整句 ≤ 软 22 宽 → 单 cue；> 硬 26 宽 → 拆；[软,硬] 间按语义可拆可不拆
        for cu in block_cues:
            zh, start, end = cu["zh"], cu["start"], cu["end"]
            en_full = cu["en"]
            w = text_width(zh)
            span = end - start
            if w <= SOFT_MAX:
                # 单 cue；时长碎片（<1s 但语义自足）→ 告警提示（对齐 reflow 独立短句可接受）
                if span < MIN_FRAG_MS:
                    alerts.append(f"⏱️ 独立短句 {fmt(start)}-{fmt(end)}（{span}ms <1s）: {zh[:30]}")
                total_cue += 1
                srt_blocks.append({"idx": total_cue, "start": start, "end": end,
                                   "zh": zh, "en": en_full, "z": cu["z"]})
            else:
                # 超宽：按中文标点拆候选段 + 宽度拼合 → 子单元；时间 = 整句区间内按阅读比例分配
                # （吸附真实 cue 边界 ≤ snap；无则 100ms 取整预测点——阅读舒适优先，允许必要预测点）
                # 真实 cue 边界 = E 组内各 E 的 start/end 集合
                real_bounds = set()
                for e in cu["e"]:
                    real_bounds.add(et[e][0])
                    real_bounds.add(et[e][1])
                # 候选段按阅读时长权重分配区间
                # 标点分级：句末标点优先（句界是最自然的字幕段界，避免跨句粘连成超宽段），
                # 再降至句内标点；单段切不动仍超宽时保留（由告警暴露）
                cands = split_recursive(zh, ["。！？…", "，；：", "—", "、"], HARD_MAX)
                units = pack_candidates(cands, HARD_MAX, 5)
                weights = [max(1, cjk_reading_ms(u, args.cjk_speed)) for u, _w in units]
                # 子段 EN = 整句 EN 按子段宽度比例机械切（互斥拼接==整句 EN；语义近似）
                en_subs = split_en_by_weights(en_full, [text_width(u) for u, _w in units])
                # 复用 _allocate_by_weight：按权重比例在 [start,end] 内分界 + 吸附
                # units 元素取 u[0](key)/u[2](zh)，u[1] 作 en 占位；此处 zh 子段即显示文本
                segs = _allocate_by_weight([(f"u{i}", en_subs[i] if i < len(en_subs) else "", u)
                                            for i, (u, w) in enumerate(units)],
                                           weights, start, end, real_bounds, args.snap_ms)
                n_pred = 0
                for i, (uk, s, e2, zhtxt, enfrag, p1, p2) in enumerate(segs):
                    total_cue += 1
                    srt_blocks.append({"idx": total_cue, "start": s, "end": e2,
                                       "zh": zhtxt, "en": enfrag, "z": cu["z"]})
                    if p1 or p2:
                        n_pred += 1
                # 长句碎片检测
                for (uk, s, e2, zhtxt, _en, _p1, _p2) in segs:
                    if e2 - s < MIN_FRAG_MS:
                        alerts.append(f"🔪 长句碎片 {fmt(s)}-{fmt(e2)}（{e2-s}ms <1s）: {zhtxt[:30]}——合并/调整切分点")
                if n_pred:
                    alerts.append(f"🎯 预测点 {cu['z']}: 拆 {len(units)} 段含 {n_pred} 个 100ms 预测点（无真实 cue 边界可吸附）")

    # 全局时间重叠防御（生产健壮性）：相邻显示单元 start < 前单元 end → 后单元顺延到前 end。
    # 正常 reflow2 中 E 固化时间已含共享 cue 切分、align 基于同一 en_timeline 生成 → 天然零重叠；
    # 但 align 轻微错位 / 跨块边界误差仍可能造成重叠——SRT 不允许时间重叠，必须在此兜底顺延
    # （后段整体早于前段 = 倒挂，无法顺延 → 告警提示复核 align 对应）。
    n_overlap = 0
    n_invert = 0
    for i in range(1, len(srt_blocks)):
        prev, cur = srt_blocks[i - 1], srt_blocks[i]
        if cur["start"] < prev["end"]:
            if cur["end"] <= prev["start"]:
                # 完全倒挂：cur 整段在 prev 之前（块边界 E 组错位）——无法顺延，须复核 align
                n_invert += 1
                alerts.append(f"⛔ 时间倒挂 {prev['idx']}→{cur['idx']}: 后段 [{fmt(cur['start'])},{fmt(cur['end'])}] "
                              f"早于前段 end {fmt(prev['end'])}——{cur['zh'][:20]} 复核 align 对应（E 组错位）")
            else:
                n_overlap += 1
                cur["start"] = prev["end"]
                alerts.append(f"🔀 时间重叠顺延 {prev['idx']}→{cur['idx']}: "
                              f"{cur['zh'][:20]} start 顺延到 {fmt(prev['end'])}（align/E 边界误差兜底）")
    if n_overlap or n_invert:
        print(f"⚠️ 时间重叠顺延 {n_overlap} 处 / 倒挂 {n_invert} 处（见 r04_alerts）")

    # 落盘 r04_draft.srt（单语中文）
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        for cu in srt_blocks:
            fh.write(f"{cu['idx']}\n{fmt(cu['start'])} --> {fmt(cu['end'])}\n{cu['zh']}\n\n")
    # 落盘 r04_bilingual.srt（双语 en-zh：英文行 = EN 片段，中文行 = 对应译文）
    bilingual_path = args.bilingual or os.path.join(out_dir, "r04_bilingual.srt")
    with open(bilingual_path, "w", encoding="utf-8", newline="\n") as fh:
        for cu in srt_blocks:
            fh.write(f"{cu['idx']}\n{fmt(cu['start'])} --> {fmt(cu['end'])}\n{cu['en']}\n{cu['zh']}\n\n")
    # 落盘 r04_alerts.md
    with open(alert_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# r04_alerts（新 reflow2）— 回填告警\n\n")
        fh.write(f"- 总显示单元: {total_cue}\n")
        fh.write(f"- 超宽拆段整句: {sum(1 for a in alerts if a.startswith('🎯'))}\n")
        fh.write(f"- 长句碎片: {sum(1 for a in alerts if a.startswith('🔪'))}\n")
        fh.write(f"- 时间重叠顺延: {sum(1 for a in alerts if a.startswith('🔀'))}\n")
        fh.write(f"- 时间倒挂: {sum(1 for a in alerts if a.startswith('⛔'))}\n\n")
        if alerts:
            fh.write("## 告警清单\n")
            for a in alerts:
                fh.write(f"- {a}\n")
        else:
            fh.write("（无告警）\n")

    print(f"✅ 继承+回填完成：{len(keys)} 块 / {total_cue} 显示单元 → {args.out}")
    if problems:
        print(f"⚠️ 问题清单（{len(problems)}）:")
        for p in problems[:40]:
            print(f"   {p}")
        return 1
    print("✅ 无问题（对齐完整、E 组时间齐全）")
    return 0


if __name__ == "__main__":
    main()
