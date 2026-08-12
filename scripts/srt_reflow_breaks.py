# -*- coding: utf-8 -*-
"""r01 硬性断句（输入层）：扫描 01 空隙 → 生成 r01_breaks.md

产出两类内容：
1. 断句点清单：空隙点（前 cue 尾 → 后 cue 首）+ 强制断句约束 + **Agent 复核字段**
   （性质判定 / 断句方式 / 游离停顿词提示）——每个空隙点由 Agent 复核回填，供 r01 补标点与 r03 归属参考。
2. 补标点输入文本：按 cue 顺序拼接、空隙处注入【强制断句】标记的输入文本——
   直接交给 LLM 补标点（结构强制，非软指令）；补标点后必须跑 `srt_check_r01_breaks.py` 校验。

背景：S56 事故实证「合句逻辑胜过分割逻辑」——只给文本无时间信息时 LLM 必然合句，
剪辑空隙被文本连续性吞掉。软指令（prompt 里写"空隙处强制断句"）不足，
必须把空隙点作为结构约束注入输入。非语音标记 cue（[Music] 等，去括号后为空）不参与空隙判定。

阈值与 reflow-redstone SKILL 一致：长停顿 >5s；剪辑跳转 >10s。
用法（命令根 = Project_Main/）：
  python scripts/srt_r01_breaks.py <01.srt> [-o reflow/r01_breaks.md]
"""
import argparse
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

LONG_GAP_MS = 5000      # 长停顿阈值（与 srt_gap_scan.py / 步骤 2/5 一致）
JUMP_GAP_MS = 10000     # 剪辑跳转阈值
BRACKET_RE = re.compile(r"\[[^\]]*\]")


def is_pure_marker(text):
    """纯非语音标记 cue：去掉全部 [xxx] 后无可见字符（[Music]/[Applause] 等）——
    动态识别、不硬编码枚举；此类 cue 两侧不参与空隙判定"""
    return BRACKET_RE.sub("", text).strip() == ""


def parse_time(s):
    h, m, rest = s.split(":")
    return int(h) * 3600000 + int(m) * 60000 + int(rest.replace(",", ".").split(".")[0]) * 1000 + int(rest.replace(",", ".").split(".")[1])


def fmt(ms):
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, msr = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{msr:03d}"


def parse_srt(path):
    text = open(path, encoding="utf-8-sig").read()
    cues = []
    for block in text.strip().split("\n\n"):
        lines = [l for l in block.splitlines() if l.strip()]
        # 空文本 cue 只有索引行+时间行（2 行）；只要含有效时间行即保留，保证 cues 与 SRT 原始索引一一对齐
        if len(lines) < 2:
            continue
        idx = int(re.match(r"\d+", lines[0]).group())
        m = re.match(r"(\d\d:\d\d:\d\d,\d\d\d) --> (\d\d:\d\d:\d\d,\d\d\d)", lines[1])
        if not m:
            continue
        txt = " ".join(lines[2:]).strip()
        # 保留全部 cue（含 [Music] 空文本）以保原始索引；方括号标记在拼接/显示时剔除
        cues.append({"idx": idx, "start": parse_time(m.group(1)), "end": parse_time(m.group(2)), "text": txt})
    return cues


def main():
    ap = argparse.ArgumentParser(description="r01 硬性断句输入：生成断句点清单 + 注入【强制断句】标记的补标点输入文本")
    ap.add_argument("src", help="01_subtitle_asr_fixed.srt")
    ap.add_argument("-o", dest="out", default=None, help="输出 r01_breaks.md（默认 01 同目录 reflow/r01_breaks.md）")
    args = ap.parse_args()
    out = args.out or str(Path(args.src).parent / "reflow" / "r01_breaks.md")

    cues = parse_srt(args.src)

    # 空隙点（与 srt_gap_scan.py 同一判定：先剔除纯标记 cue，在剩余语音 cue 上按顺序相邻判定——跨标记空隙也算）
    breaks = []  # (ia, ib, gap, is_jump)
    speech = [c for c in cues if not is_pure_marker(c["text"])]
    for k in range(len(speech) - 1):
        gap = speech[k + 1]["start"] - speech[k]["end"]
        if gap > LONG_GAP_MS:
            breaks.append((speech[k]["idx"], speech[k + 1]["idx"], gap, gap > JUMP_GAP_MS))

    # —— 断句点清单 ——
    lines = []
    lines.append(f"# r01 硬性断句点清单 — {args.src}")
    lines.append("")
    lines.append(f"- 输入: `{args.src}`（{len(cues)} cue）；长停顿 >{LONG_GAP_MS/1000:.0f}s；剪辑跳转 >{JUMP_GAP_MS/1000:.0f}s")
    lines.append(f"- 空隙点: {len(breaks)} 处（{sum(1 for b in breaks if b[3])} 处剪辑跳转）")
    lines.append("- 用途: 步骤 1 合并补标点的**硬性断句输入**——用下方「补标点输入文本」直接作为 LLM 输入，")
    lines.append("  空隙处已注入【强制断句】标记，LLM 不得跨空隙合句；补标点后必须跑 `srt_reflow_check_breaks.py` 校验，")
    lines.append("  未通过（跨空隙合句）打回重跑。软指令不足（S56 实证空隙被合句吞掉）。")
    lines.append("")
    lines.append("## 断句点清单")
    lines.append("")
    for i, (ia, ib, gap, is_jump) in enumerate(breaks, 1):
        tag = "⚠️ 剪辑跳转" if is_jump else "长停顿"
        a_text = BRACKET_RE.sub("", next(c["text"] for c in cues if c["idx"] == ia))
        b_text = BRACKET_RE.sub("", next(c["text"] for c in cues if c["idx"] == ib))
        a_words = len(re.findall(r"[a-z0-9']+", a_text.lower()))
        b_words = len(re.findall(r"[a-z0-9']+", b_text.lower()))
        lines.append(f"### {i}. c{ia} → c{ib}（{gap/1000:.1f}s）{tag}")
        lines.append(f"- 区间: {fmt(cues[ia-1]['end'])} → {fmt(cues[ib-1]['start'])}")
        lines.append(f"- 前 cue c{ia}（尾锚）: `{a_text[:60]}{'…' if len(a_text)>60 else ''}`")
        lines.append(f"- 后 cue c{ib}（首锚）: `{b_text[:60]}{'…' if len(b_text)>60 else ''}`")
        lines.append("- 强制: 两锚之间必须断句（句末标点 `.?!` 或段落边界），禁止合并为一句")
        lines.append("- **Agent 复核（每个空隙点必填，回填本清单）**:")
        lines.append("  - 性质判定: [ ] 剪辑跳转（语义真断 → 断死）  [ ] 语义停顿（语义仍连贯 → 可松断）")
        lines.append("  - 断句方式: [ ] 独立成句  [ ] 分段（语义衔接，非硬拆）  [ ] 归前句句尾（仅单词级游离词）")
        if b_words <= 2:
            lines.append(f"  - ⚠️ 后 cue c{ib} 为{'单词' if b_words == 1 else '短语'}级游离停顿词（`{b_text}`）："
                         f"若独立成句，r03 须独立成单元覆盖自身 cue；若归前句句尾，不得与后句主体跨空隙合并")
        if a_words <= 2:
            lines.append(f"  - ⚠️ 前 cue c{ia} 为{'单词' if a_words == 1 else '短语'}级游离停顿词（`{a_text}`）："
                         f"其与后句之间同样不得跨空隙，r03 归属须人工判断")
        lines.append("")

    # —— 补标点输入文本（注入断句标记）——
    lines.append("## 补标点输入文本（直接交给 LLM，保留空隙断句标记）")
    lines.append("")
    lines.append("> 以下为按 cue 顺序拼接的输入，空隙处已插入【强制断句】标记行。")
    lines.append("> LLM 任务：补全标点（仅加标点、不改措辞），**空隙标记行两侧不得合并为一句**；输出可保留空行分隔。")
    lines.append("")
    lines.append("```text")
    bset = {(ia, ib) for ia, ib, _, _ in breaks}
    block_texts = []
    cur = []
    for k, c in enumerate(cues):
        cur.append(BRACKET_RE.sub("", c["text"]).strip())
        if k + 1 < len(cues) and (c["idx"], cues[k + 1]["idx"]) in bset:
            block_texts.append((c["idx"], cues[k + 1]["idx"], " ".join(t for t in cur if t)))
            cur = []
    if cur:
        block_texts.append((None, None, " ".join(t for t in cur if t)))
    for bi, (ia, ib, txt) in enumerate(block_texts):
        lines.append(txt)
        if ib is not None and bi < len(block_texts) - 1:
            gap = next(g for a, b, g, _ in breaks if a == ia and b == ib)
            tag = "剪辑跳转" if gap > JUMP_GAP_MS else "长停顿"
            lines.append("")
            lines.append(f"[空隙 c{ia}→c{ib} {gap/1000:.1f}s {tag} —— 强制断句点，两侧不得合为一句]")
            lines.append("")
    lines.append("```")
    lines.append("")
    lines.append("## 校验（补标点后必跑）")
    lines.append("")
    lines.append("```")
    lines.append(f"python scripts/srt_reflow_check_breaks.py {args.src} reflow/r01_merged_en.txt")
    lines.append("```")
    lines.append("")
    lines.append("> 通过 = 每个空隙点两侧 cue 之间已断句；违规 = 存在跨空隙合句，打回步骤 1 重跑（带断句标记输入）。")

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"OK: {len(breaks)} 处断句点（{sum(1 for b in breaks if b[3])} 剪辑跳转）→ {out}")
    for ia, ib, gap, is_jump in breaks:
        print(f"  c{ia}→c{ib} {gap/1000:.1f}s {'⚠️跳转' if is_jump else '停顿'}")


if __name__ == "__main__":
    main()
