# -*- coding: utf-8 -*-
"""双语组装（attach-en）：r04 单语 + r03 英文片段 -> 双语 SRT（en-zh）"""
import re
from pathlib import Path

from .plan import parse_r03_any


def attach_en(r04_path, r03_path, out_path):
    sentences = parse_r03_any(r03_path)
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
