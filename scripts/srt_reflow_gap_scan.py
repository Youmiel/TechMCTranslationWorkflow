# -*- coding: utf-8 -*-
"""空隙探测（回填工作流前置）：扫描 01 的 cue 时间戳，生成 r00_gaps.md + r00_gaps_active.tsv

供 reflow/reflow2 步骤 1 合并补标点前参考——大空隙 = 强制分割点提示（不跨空隙合句）。
阈值：长停顿 >5s；剪辑跳转 >10s。
非语音标记 cue（[Music]/[Applause] 等方括号标记单独成 cue，去括号后无可见字符）动态识别、
不参与空隙判定（空隙在相邻真实语音 cue 间计算、跨标记），并单独列出供 r01 对齐参考。

**2026-09-21 新增：疑似源切分缺陷识别（疑点探测，只报告不改行为）**

判据（**两条强信号同时成立**，高置信、不扰民——用户 2026-09-21 定调）：
  1. 前 cue 末尾**无句末标点**（`.?!。！？…`）
  2. 后 cue **首字母小写**（正常字幕不会以小写开新 cue）

典型成因：原字幕把**同一句**切成两条 cue、中间空出一段时长——被误判为「作者长停顿」后，
一条缺陷会沿链条放大（空隙探测 → 强制断句 → 强制切块 → 补标点断句 → E 句被切开 → 旁注挂错句）。
实例：mv3OAZGKfs4 c88→c89 空 5.2s（`...duplicates exactly once` / `over its lifetime.`）。

**处置与生效通道（取代「改 md 标题骗过正则」的 hack）**：
- `r00_gaps.md`：人读报告，按「疑似源切分缺陷」/「长停顿」分节，每处标 `[生效·待裁决]`/`[已排除]`
- `r00_gaps_active.tsv`：**机器产物 + 人工可编辑的单一事实源**（下游统一读它，不再各自探测）
  列：`a_idx` `b_idx` `gap_ms` `kind` `status` `note`
  - `status = active`    真实空隙（生效：分块硬边界 + 断句点 + 校验）
  - `status = suspect`   疑似源切分缺陷（**默认仍生效**——脚本只报告、不改行为，待人工裁决）
  - `status = excluded`  人工确认排除（不生效：不分块、不断句、校验跳过）
- **人工裁决方式**：把 tsv 中该行 `status` 改为 `excluded`（排除）或 `active`（生效）。
  **重跑本脚本不覆盖人工决定**——已存在 tsv 中同 `(a_idx,b_idx)` 的 status/note 会被保留。

用法（命令根 = Project_Main/）：
  python scripts/srt_reflow_gap_scan.py <01.srt> [-o reflow/r00_gaps.md] [--tsv reflow/r00_gaps_active.tsv]
"""
import argparse
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from srt_reflow_common import is_pure_marker, parse_time, fmt, BRACKET_RE as MARKER_RE

LONG_GAP_MS = 5000      # 长停顿阈值（与步骤 2/5 一致）
JUMP_GAP_MS = 10000     # 剪辑跳转阈值

# 句末标点（判「前 cue 是否已收句」用；中英全角半角都收，因 01 可能混排）
EOS_CHARS = ".?!。！？…"
# status 取值
ST_ACTIVE = "active"        # 真实空隙（生效）
ST_SUSPECT = "suspect"      # 疑似源切分缺陷（默认仍生效，待人工裁决）
ST_EXCLUDED = "excluded"    # 人工确认排除（不生效）
STATUS_SET = (ST_ACTIVE, ST_SUSPECT, ST_EXCLUDED)

# tsv 表头（`#` 开头，消费端跳过；列序即契约）
TSV_HEADER = "# a_idx\tb_idx\tgap_ms\tkind\tstatus\tnote"


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
        cues.append({"idx": idx, "start": parse_time(m.group(1)), "end": parse_time(m.group(2)), "text": txt})
    return cues


def is_suspect_split(a_text, b_text):
    """两条强信号同时成立 → 疑似源字幕切分缺陷（返回 (bool, 判据说明)）。

    1. 前 cue 末尾无句末标点（去方括号标记后判）
    2. 后 cue 首字母小写
    """
    a = MARKER_RE.sub("", a_text).strip()
    b = MARKER_RE.sub("", b_text).strip()
    if not a or not b:
        return False, ""
    reasons = []
    if a[-1] not in EOS_CHARS:
        reasons.append("前 cue 末尾无句末标点")
    first_alpha = next((ch for ch in b if ch.isalpha()), "")
    if first_alpha and first_alpha.islower():
        reasons.append("后 cue 首字母小写")
    if len(reasons) == 2:
        return True, " + ".join(reasons) + "（疑似源字幕切分缺陷：同一句被切成两条 cue，建议合并）"
    return False, ""


def load_prev_status(tsv_path):
    """读已存在 tsv 的人工裁决 → {(a_idx, b_idx): (status, note)}（重跑不覆盖人工决定）。"""
    return {(_int_idx(r["ia"]), _int_idx(r["ib"])): (r["status"], r["note"])
            for r in load_breaks_tsv(tsv_path)}


def _int_idx(s):
    """`c88` → 88（容忍纯数字）。"""
    m = re.search(r"\d+", str(s) or "")
    return int(m.group()) if m else 0


def load_breaks_tsv(tsv_path):
    """读 r00_gaps_active.tsv → [dict(ia, ib, gap_ms, kind, status, note)]（下游统一入口）。

    - 表头 `#` 行与空行跳过；列序契约：a_idx / b_idx / gap_ms / kind / status / note
    - `status == excluded` 的条目**仍返回**（供调用方决定：gap_scan 保留人工决定、
      breaks/check_breaks 过滤掉、text_chunk 不切块——语义由调用方按需处理）
    - 文件不存在 → 返回 []（调用方回退自行探测）
    """
    out = []
    if not tsv_path or not os.path.exists(tsv_path):
        return out
    try:
        for ln in open(tsv_path, encoding="utf-8"):
            s = ln.rstrip("\n")
            if not s.strip() or s.startswith("#"):
                continue
            parts = s.split("\t")
            if len(parts) < 5:
                continue
            status = parts[4].strip()
            if status not in STATUS_SET:
                continue
            gap = int(re.sub(r"\D", "", parts[2]) or 0) if len(parts) > 2 else 0
            out.append({"ia": _int_idx(parts[0]), "ib": _int_idx(parts[1]), "gap_ms": gap,
                        "kind": parts[3].strip(), "status": status,
                        "note": parts[5].strip() if len(parts) > 5 else "",
                        "a_idx": parts[0].strip(), "b_idx": parts[1].strip()})
    except OSError:
        pass
    return out


def main():
    ap = argparse.ArgumentParser(description="空隙探测：扫描 01 时间戳 → r00_gaps.md（人读）+ r00_gaps_active.tsv（机器/人工裁决）")
    ap.add_argument("src", help="01_subtitle_asr_fixed.srt")
    ap.add_argument("-o", dest="out", default=None, help="输出 r00_gaps.md（默认 01 同目录 reflow/r00_gaps.md）")
    ap.add_argument("--tsv", dest="tsv", default=None,
                    help="输出生效空隙点 tsv（默认与 r00_gaps.md 同目录 r00_gaps_active.tsv）；已存在则保留其人工裁决")
    args = ap.parse_args()
    out = args.out or str(Path(args.src).parent / "reflow" / "r00_gaps.md")
    tsv_path = args.tsv or str(Path(out).parent / "r00_gaps_active.tsv")

    cues = parse_srt(args.src)
    speech = [c for c in cues if not is_pure_marker(c["text"])]  # 语音 cue（空隙只在语音之间算）
    markers = [c for c in cues if is_pure_marker(c["text"])]     # 非语音标记 cue（[Music] 等）
    prev_status = load_prev_status(tsv_path)

    gaps = []  # dict：gap / ia / ib / 时间 / 文本 / kind / status / note
    for k in range(len(speech) - 1):
        a, b = speech[k], speech[k + 1]
        gap = b["start"] - a["end"]
        if gap <= LONG_GAP_MS:
            continue
        at = MARKER_RE.sub("", a["text"]).strip()
        bt = MARKER_RE.sub("", b["text"]).strip()
        suspect, why = is_suspect_split(a["text"], b["text"])
        if suspect:
            kind, status, note = "suspect", ST_SUSPECT, why
        else:
            kind = "jump" if gap > JUMP_GAP_MS else "gap"
            status = ST_ACTIVE
            note = "剪辑跳转" if kind == "jump" else "真实长停顿"
        # 人工裁决优先（重跑不覆盖）
        if (a["idx"], b["idx"]) in prev_status:
            status, pnote = prev_status[(a["idx"], b["idx"])]
            note = pnote or note
        gaps.append({"gap": gap, "ia": a["idx"], "ib": b["idx"],
                     "a_start": a["start"], "a_end": a["end"], "b_start": b["start"], "b_end": b["end"],
                     "at": at, "bt": bt, "kind": kind, "status": status, "note": note})
    gaps.sort(key=lambda g: -g["gap"])

    suspects = [g for g in gaps if g["kind"] == "suspect"]
    n_jump = sum(1 for g in gaps if g["kind"] == "jump")
    n_excluded = sum(1 for g in gaps if g["status"] == ST_EXCLUDED)
    n_effective = len(gaps) - n_excluded

    lines = []
    lines.append(f"# r00 空隙探测报告 — {args.src}")
    lines.append("")
    lines.append(f"- 输入: `{args.src}`（{len(cues)} cue，其中非语音标记 {len(markers)} 条）")
    lines.append(f"- 阈值: 长停顿 >{LONG_GAP_MS/1000:.0f}s；剪辑跳转 >{JUMP_GAP_MS/1000:.0f}s")
    lines.append(f"- 非语音标记 cue（[Music] 等，去方括号后为空）: {len(markers)} 条——不参与空隙判定与回填，仅保留时间骨架（见下节）")
    lines.append(f"- 长停顿总数: {len(gaps)} 处（剪辑跳转 {n_jump} / **疑似源切分缺陷 {len(suspects)}**）；"
                 f"其中**已排除 {n_excluded}** 处 → **实际生效空隙点 {n_effective}** 处")
    lines.append("")
    lines.append("> **生效空隙点集 = `r00_gaps_active.tsv`（单一事实源，人工可编辑）**——")
    lines.append("> 下游分块（`text_chunk.py --gaps-file`）与断句校验（`srt_reflow_check_breaks.py --gaps`）统一读它，不再各自探测。")
    lines.append("> 裁决方式：把 tsv 中该行 `status` 改为 `excluded`（排除）或 `active`（生效）；**重跑本脚本不覆盖人工决定**。")
    lines.append("")

    if suspects:
        lines.append(f"## ⚠️ 疑似源切分缺陷（{len(suspects)} 处，建议人工裁决）")
        lines.append("")
        lines.append("判据（两条强信号**同时**成立）: ① 前 cue 末尾无句末标点；② 后 cue 首字母小写。")
        lines.append("此类空隙**多因原字幕把同一句切成两条 cue**，非作者真实停顿——")
        lines.append("按停顿处理会沿链条放大（强制断句 → 强制切块 → E 句被切开 → 旁注挂错句）。")
        lines.append("**当前默认仍生效**（脚本只报告不改行为）：确认是源缺陷后，把 tsv 中该行 status 改为 `excluded`。")
        lines.append("")
        for i, g in enumerate(suspects, 1):
            tag = "[已排除]" if g["status"] == ST_EXCLUDED else "[生效·待裁决]"
            lines.append(f"### {i}. c{g['ia']} → c{g['ib']}（{g['gap']/1000:.1f}s）{tag}")
            lines.append(f"- 判据: {g['note']}")
            lines.append(f"- 区间: {fmt(g['a_end'])} → {fmt(g['b_start'])}")
            lines.append(f"- 前 cue c{g['ia']}: `{g['at'][:60]}{'…' if len(g['at'])>60 else ''}`（{fmt(g['a_start'])}→{fmt(g['a_end'])}）")
            lines.append(f"- 后 cue c{g['ib']}: `{g['bt'][:60]}{'…' if len(g['bt'])>60 else ''}`（{fmt(g['b_start'])}→{fmt(g['b_end'])}）")
            lines.append("- 处置: 确认源缺陷 → 跨该停顿**合并为一句**（不断句、不切块）；"
                         "在 tsv 中把 status 由 `suspect` 改为 `excluded` 即为正式排除")
            lines.append("")

    other = [g for g in gaps if g["kind"] != "suspect"]
    lines.append(f"## 长停顿清单（>{LONG_GAP_MS/1000:.0f}s，共 {len(other)} 处，按时长降序）")
    lines.append("")
    lines.append(f"- 其中剪辑跳转（>{JUMP_GAP_MS/1000:.0f}s）: {sum(1 for g in other if g['kind'] == 'jump')} 处")
    lines.append("")
    for i, g in enumerate(other, 1):
        tag = "⚠️ 剪辑跳转" if g["kind"] == "jump" else "长停顿"
        ext = "  [已排除]" if g["status"] == ST_EXCLUDED else ""
        lines.append(f"### {i}. c{g['ia']} → c{g['ib']}（{g['gap']/1000:.1f}s）{tag}{ext}")
        lines.append(f"- 区间: {fmt(g['a_end'])} → {fmt(g['b_start'])}")
        lines.append(f"- 前 cue c{g['ia']}: `{g['at'][:60]}{'…' if len(g['at'])>60 else ''}`（{fmt(g['a_start'])}→{fmt(g['a_end'])}）")
        lines.append(f"- 后 cue c{g['ib']}: `{g['bt'][:60]}{'…' if len(g['bt'])>60 else ''}`（{fmt(g['b_start'])}→{fmt(g['b_end'])}）")
        lines.append("- 用途: r01 合并补标点的强制分割点提示；r03 分句/游离停顿词归属参考")
        lines.append("")
    lines.append("## 非语音标记 cue（方括号标记单独成 cue）")
    lines.append("")
    lines.append(f"- 共 {len(markers)} 条：去方括号后无可见字符（[Music]/[Applause] 等，动态识别不枚举）。")
    lines.append("- 已跳过空隙判定（不成为断句锚点）与回填；仅保留时间骨架供 r01 合并/对齐参考。")
    lines.append("")
    for m in markers:
        lines.append(f"- c{m['idx']} `{m['text'][:40]}`（{fmt(m['start'])}→{fmt(m['end'])}）")
    lines.append("")
    lines.append("## 使用说明")
    lines.append("")
    lines.append("1. **步骤 1 合并补标点**：本清单为空隙位置提供时间依据——补标点时在**生效**空隙处强制断句"
                 "（不跨空隙合句），空隙两侧 cue 文本各自成句/成段。")
    lines.append("2. **疑似源缺陷的处置**：人工确认后改 `r00_gaps_active.tsv` 该行 status 为 `excluded`——"
                 "分块与校验随之不再把它当空隙（正文须跨它合并为一句）。")
    lines.append("3. **步骤 3 分句对应**：游离停顿词 cue（单词级 so/okay/and）两侧若有大空隙，应独立成单元或归前句句尾，"
                 "不与后句主体合并（避免跨空隙单元）。")
    lines.append("4. **复盘**：r04 回填告警（内部空隙/剪辑跳转/超长单元）应与本清单对照——"
                 "理论上 r04 不应出现本清单之外的新空隙。")

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")

    # ---- tsv：生效空隙点集（单一事实源，人工可编辑；重跑保留人工裁决）----
    Path(tsv_path).parent.mkdir(parents=True, exist_ok=True)
    with open(tsv_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(TSV_HEADER + "\n")
        for g in sorted(gaps, key=lambda x: x["ia"]):
            f.write(f"c{g['ia']}\tc{g['ib']}\t{g['gap']}\t{g['kind']}\t{g['status']}\t{g['note']}\n")

    print(f"OK: {len(gaps)} 处长停顿（{n_jump} 剪辑跳转；**疑似源缺陷 {len(suspects)}**；已排除 {n_excluded} → 生效 {n_effective}）")
    print(f"    → {out}")
    print(f"    → {tsv_path}（生效空隙点集，下游统一读取；人工裁决改 status 列）")
    for g in gaps:
        marks = "⚠️跳转" if g["kind"] == "jump" else ("❓疑似源缺陷" if g["kind"] == "suspect" else "停顿")
        ext = "  [已排除]" if g["status"] == ST_EXCLUDED else ""
        print(f"  c{g['ia']}→c{g['ib']} {g['gap']/1000:.1f}s {marks}{ext}  {g['at'][:26]} / {g['bt'][:26]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
