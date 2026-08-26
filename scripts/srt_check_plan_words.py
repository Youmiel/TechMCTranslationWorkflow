# -*- coding: utf-8 -*-
"""断句措辞一致性校验（translate 阶段二）：s03_plan.md 各段英文词序列 == 01 对应 cue 区间的词序列。

断句只合并/分割（不得改措辞）——ASR 修正已在组装期应用（02_terms.md 的 ASR 修正列），
01 侧先应用**明确修正**（含 `→` 的映射）再对比，其余差异 = 断句违规（错词/缺词/多词）。

difflib 一次列出每段全部分歧（沿用 `srt_reflow_check_words.py` 思路，不再只报第一处）；
带段号 + plan 行号 + 01 cue 定位；默认只输出「问题数 + 提示」（各分歧段一行统计，不输出错误内容），--expand 展开每处上下文。

用法（命令根 = Project_Main/）：
  python scripts/srt_check_plan_words.py <01.srt> <s03_plan.md> [--asr-fixes <02_terms.md>] [--expand]
退出码：0 = 词序列一致；1 = 存在分歧（打回）。
"""
import argparse
import difflib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ASR_FIX_RE = re.compile(r"([^→;；,，]+)→([^→;；,，]+)")
WORD_RE = re.compile(r"[a-z0-9']+")


def is_pure_marker(text):
    """纯方括号标记（[Music] 等，去括号后为空）动态识别。"""
    return not re.sub(r"\[[^\]]*\]", "", text).strip()


def parse_srt_cues(path):
    """解析 01 → {idx: text}（纯标记 cue 置空，不参与词序列）。"""
    cues = {}
    for block in open(path, encoding="utf-8-sig").read().strip().split("\n\n"):
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) < 3:
            continue
        m = re.match(r"\d+", lines[0])
        if not m:
            continue
        body = " ".join(lines[2:]).strip()
        if is_pure_marker(body):
            body = ""
        cues[int(m.group())] = body
    return cues


def parse_plan(path):
    """解析 s03_plan.md → [(行号, 段号, cmin, cmax, 文本), ...]（行格式 `段号|cstart[-cend][~]|文本`）。"""
    segs = []
    for lineno, raw in enumerate(open(path, encoding="utf-8-sig"), 1):
        line = raw.strip()
        m = re.match(r"^(\d+)\|c(\d+)(~?)(?:-c(\d+)(~?))?\|(.*)$", line)
        if not m:
            continue
        seg = int(m.group(1))
        cs = int(m.group(2))
        ce = int(m.group(4)) if m.group(4) else cs
        text = m.group(6).strip()
        segs.append((lineno, seg, cs, ce, text))
    return segs


def parse_asr_fixes(path):
    """从 02_terms.md 的「ASR 修正」列解析修正映射 [(orig, fixed), ...]（仅含 `→` 的明确映射）。

    无箭头的条目（如 `Terra/Tara 等多处`）无方向信息、无法自动容错 → 跳过，交由 Agent 复核差异。
    """
    fixes = []
    header = None
    for line in open(path, encoding="utf-8-sig"):
        line = line.strip()
        if not line.startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if "ASR 修正" in cells:
            header = next((i for i, c in enumerate(cells) if "ASR 修正" in c), None)
            continue
        if header is None or len(cells) <= header:
            continue
        for m in ASR_FIX_RE.finditer(cells[header]):
            orig, fixed = m.group(1).strip(), m.group(2).strip()
            if orig and fixed:
                fixes.append((orig, fixed))
    return fixes


def words_of(text):
    return WORD_RE.findall(text.lower())


def apply_fixes(ws, fixes):
    """01 侧词序列应用修正映射（支持多词 orig/fixed）→ 修正后词序列。"""
    out = []
    i = 0
    n = len(ws)
    while i < n:
        for orig, fixed in fixes:
            ow = words_of(orig)
            if ow and ws[i:i + len(ow)] == ow:
                out.extend(words_of(fixed))
                i += len(ow)
                break
        else:
            out.append(ws[i])
            i += 1
    return out


def word_diff_entries(a, b):
    """difflib 找出 a 与 b 词序列全部分歧 → [(tag, i1, i2, j1, j2, a_slice, b_slice), ...]。"""
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return [(tag, i1, i2, j1, j2, a[i1:i2], b[j1:j2])
            for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal"]


def diff_describe(entry):
    tag, i1, i2, j1, j2, a, b = entry
    if tag == "replace" and len(a) == 1 and len(b) == 1:
        return f"第 {i1} 词: 01=[{a[0]}] s03=[{b[0]}]"
    if tag == "replace":
        return f"01[{i1}:{i2}]={{{' '.join(a) or '∅'}}} ↔ s03[{j1}:{j2}]={{{' '.join(b) or '∅'}}}"
    if tag == "delete":
        return f"01 独有 01[{i1}:{i2}]={{{' '.join(a)}}}（s03 缺 {len(a)} 词）"
    return f"s03 独有 s03[{j1}:{j2}]={{{' '.join(b)}}}（01 缺 {len(b)} 词）"


def main():
    ap = argparse.ArgumentParser(
        description="断句措辞一致性：s03_plan.md 各段词序列 == 01 对应 cue（断句只合并/分割，不改措辞）")
    ap.add_argument("srt", help="01_subtitle_asr_fixed.srt")
    ap.add_argument("plan", help="s03_plan.md（每行 `段号|cstart[-cend][~]|文本`）")
    ap.add_argument("--asr-fixes", default=None,
                    help="02_terms.md（可选：ASR 修正列含 → 的映射应用到 01 侧再对比，容错组装期修正）")
    ap.add_argument("--expand", action="store_true",
                    help="展开每处分歧的上下文/行号/cue 定位（默认只给问题数+提示）")
    args = ap.parse_args()

    cues = parse_srt_cues(args.srt)
    segs = parse_plan(args.plan)
    if not segs:
        sys.exit(f"❌ s03_plan.md 未解析到分段：{args.plan}")
    fixes = parse_asr_fixes(args.asr_fixes) if args.asr_fixes else []
    if fixes:
        shown = "；".join(f"{o}→{f}" for o, f in fixes[:5])
        print(f"（已应用 ASR 修正映射 {len(fixes)} 条：{shown}{'…' if len(fixes) > 5 else ''}）")

    print(f"=== 断句措辞一致性校验（{len(segs)} 段） ===")
    n_err = n_ok = 0
    for lineno, seg, cs, ce, text in segs:
        # 01 对应 cue 区间词序列（剔除标记 cue）
        srt_terms = []
        for i in range(cs, ce + 1):
            body = cues.get(i, "")
            if body:
                srt_terms.extend(words_of(body))
        if fixes:
            srt_terms = apply_fixes(srt_terms, fixes)
        plan_terms = words_of(text)
        if srt_terms == plan_terms:
            n_ok += 1
            continue
        n_err += 1
        entries = word_diff_entries(srt_terms, plan_terms)
        if args.expand:
            print(f"❌ 段 {seg} (c{cs}-c{ce}) s03_plan.md:行{lineno}: 词序列分歧 {len(entries)} 处"
                  f"（01={len(srt_terms)} s03={len(plan_terms)}）")
            for idx, e in enumerate(entries, 1):
                print(f"   [{idx}/{len(entries)}] {diff_describe(e)}")
            for idx, (tag, i1, i2, j1, j2, a, b) in enumerate(entries, 1):
                print(f"   ── [{idx}/{len(entries)}] {diff_describe((tag, i1, i2, j1, j2, a, b))} ──")
                ctx1 = " ".join(srt_terms[max(0, i1 - 6):i2 + 8])
                ctx2 = " ".join(plan_terms[max(0, j1 - 6):j2 + 8])
                print(f"   01 上下文: ...{ctx1}...")
                print(f"   s03 上下文: ...{ctx2}...")
                if i1 < len(srt_terms):
                    c = None
                    acc = 0
                    for cc in range(cs, ce + 1):
                        body = cues.get(cc, "")
                        if body:
                            ws = words_of(body)
                            if acc + len(ws) > i1:
                                c = cc
                                break
                            acc += len(ws)
                    if c:
                        print(f"   01 cue c{c}: `{cues.get(c, '')}`")
        else:
            print(f"❌ 段 {seg} (c{cs}-c{ce}) s03_plan.md:行{lineno}: 词序列分歧 {len(entries)} 处（01={len(srt_terms)} s03={len(plan_terms)}）")

    if n_err:
        print(f"\n❌ 断句措辞校验失败：{n_err} 段措辞不一致（打回）")
        if not args.expand:
            print("   提示：--expand 展开每处详细上下文（词差异/行号/cue 定位）")
        sys.exit(1)
    print(f"\n✅ 断句措辞校验通过：{n_ok} 段词序列一致")
    return 0


if __name__ == "__main__":
    main()
