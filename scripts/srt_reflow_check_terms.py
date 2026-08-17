# -*- coding: utf-8 -*-
"""r02 术语全量核对：逐条遍历 02_terms.md 术语表——01 定位原文出现块 → 该块 r02 译文必须含确认译名（变体容错）

回填工作流（reflow-redstone）步骤 4 校验：翻译后全量核对译文术语是否按 02_terms.md 确认译名落地，替代人工抽查。

逻辑（逐术语）：
1. 原文定位：01 各块 OWNED cue 拼接文本中搜原文候选词（词边界、大小写不敏感；块级拼接天然覆盖 ASR 跨 cue 拆词）→ 命中块集合
2. 译名检查：命中块对应 r02 译文（剥离【承接句】/【延伸句】标记）搜译名候选（整体 + 去括号切分变体，任一命中即 ✅）
3. 结果分类：✅ 命中 / ⚠️ 译文未见译名（Agent 复核：意译/漏译/漂移/命令参数名保留原文）/ ℹ️ 原文未命中 01（查 ASR 修正列或词形变体）

匹配鲁棒性（消误报，与 02_terms.md 实际条目对齐）：
- 原文词形变体：`aggro;aggroing`（分号）/ `LSB / MSB`（斜杠）→ 多词形；`world edit`↔`WorldEdit`↔`world-edit`（空格/连字符互转变体）
- 原文复数容忍：`column`→`columns`、`box`→`boxes`（正则追加可选 `(?:es|s)?` 后缀）
- 译名变体：`可堆叠/拼接的`（斜杠）/ `、`（顿号）→ 多变体；`探出（潜影贝开壳行为）` 括号 = 注释（去括号后主词也参与匹配）
- 译名匹配归一：双方去空格（中英混排 `Carpet 模组`↔`Carpet模组`）+ 剔"的"（`2×2×9 的单元`↔`2×2×9 单元` 虚词插入容忍）
- 长术语优先覆盖：子词词条（`column`）所在块的 01 原文若全部被更长术语（`water column`）覆盖，且该更长术语译文已 ✅ → 子词放行；仅剩余未覆盖出现仍参与译名检查
- 括号（全角/半角）一律视为注释剥离，不参与匹配；英文词形用 `\b` 词边界，中文译名子串匹配（大小写不敏感）

用法（命令根 = Project_Main/）：
  python scripts/srt_reflow_check_terms.py <01.srt> <02_terms.md> <r02_results/> --chunks <chunks/> [--verbose]
默认只打印 ⚠️/ℹ️ 与汇总（✅ 折叠）；--verbose 展开全部 ✅。
退出码：0 = 全部命中；1 = 有未命中（⚠️ 或 ℹ️，Agent 复核后才可放行）。
"""
import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

from srt_reflow_common import collect_chunk_files, parse_owned_cue_range, strip_stitch_marks

FORM_SEP = re.compile(r"[\/／;；]")        # 原文词形分隔（/ ／ ; ；）
TRAN_SEP = re.compile(r"[\/／、;；]")      # 译名变体分隔（/ ／ 、 ; ；）
PAREN = re.compile(r"[（(][^）)]*[）)]")   # 括号注释（全角/半角，剥离用）


def parse_srt(path):
    """解析 SRT → [(idx, text), ...]；纯标记 cue（[Music] 等）文本置空。"""
    raw = open(path, encoding="utf-8-sig").read()
    cues = []
    for block in raw.strip().split("\n\n"):
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) < 3:
            continue
        m = re.match(r"\d+", lines[0])
        if not m:
            continue
        body = " ".join(lines[2:]).strip()
        if re.sub(r"\[[^\]]*\]", "", body).strip() == "":
            body = ""
        cues.append((int(m.group()), body))
    return cues


def parse_terms(path):
    """解析 02_terms.md 术语映射表 → [(原文, 译名, 行号), ...]。

    按表头定位「原文」「译名」列（表头固定，兼容多列/列序差异）；
    仅解析含两列的表头行所在的表格（ASR 误识别修正表表头为「原 ASR/修正为」，自动跳过）；
    跳过表头/分隔行；原文或译名为空的行忽略。行号 = 02_terms.md 内 1-based（告警定位用）。
    """
    terms = []
    header = None
    for lineno, raw in enumerate(open(path, encoding="utf-8-sig").read().splitlines(), 1):
        line = raw.strip()
        if not line.startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if "原文" in cells and "译名" in cells:
            header = (
                next(i for i, c in enumerate(cells) if "原文" in c),
                next(i for i, c in enumerate(cells) if "译名" in c),
            )
            continue
        if header is None:
            continue
        if all(set(c) <= set("-: ") for c in cells if c):
            continue  # 分隔行
        if len(cells) <= max(header):
            continue
        en, zh = cells[header[0]], cells[header[1]]
        if en and zh:
            terms.append((en, zh, lineno))
    return terms


def term_forms(en):
    """原文候选词形 → 变体集合：剥离括号 + 按 /;切分 + 空格/连字符互转变体 + CamelCase 拆分（`world edit`↔`WorldEdit`↔`world-edit`、`disableObserver`→`disable Observer`）。"""
    base = PAREN.sub("", en)
    forms = []
    for f in FORM_SEP.split(base):
        f = f.strip()
        if not f:
            continue
        forms.append(f)
        if " " in f:
            forms.append(f.replace(" ", ""))
            forms.append(f.replace(" ", "-"))
        if "-" in f:
            forms.append(f.replace("-", " "))
            forms.append(f.replace("-", ""))
        cam = camel_split(f)
        if cam:
            forms.append(cam)
    return list(dict.fromkeys(forms))  # 去重保序


def camel_split(f):
    """CamelCase/驼峰词拆出空格变体（WorldEdit→World Edit、disableObserver→disable Observer）；专名（Keygen/Mojang）不分。"""
    if re.search(r"[A-Z]", f) and not re.search(r"\s", f):
        parts = re.split(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", f)
        if len(parts) > 1:
            return " ".join(parts)
    return None


def compact(s):
    """文本紧凑版：去空格/连字符（01 侧与无空格命令名匹配用，如 setblock ↔ 01 的 "set block"）。"""
    return re.sub(r"[ \-\u2010\u2011]", "", s)


def word_pattern(f):
    """词形 → 匹配正则：词边界 + 可选复数后缀（box→boxes/boxs、column→columns）。"""
    return re.compile(r"\b" + re.escape(f) + r"(?:es|s)?\b", re.IGNORECASE)


def compact_pattern(f):
    """无空格拼接词形 → 紧凑版匹配正则（仅排除字母边界：命令名后常跟数字参数，如 set block 139 147 11；同时避免 resetblock 误配 setblock）。"""
    return re.compile(r"(?<![a-zA-Z])" + re.escape(compact(f)) + r"(?![a-zA-Z])", re.IGNORECASE)


def trans_forms(zh):
    """译名候选：整体保留 + 去括号后按 /、、、、;、； 切分变体（任一命中即算）。"""
    forms = [zh]
    base = PAREN.sub("", zh)
    forms.extend(f.strip() for f in TRAN_SEP.split(base) if f.strip())
    return forms


def norm_zh(s):
    """译名/译文归一：去所有空白（含折行换行）+ 剔"的" + 小写（容忍中英混排空格、折行断词、虚词插入）。"""
    return re.sub(r"\s+", "", s).replace("的", "").casefold()


def is_subword(short, long):
    """short 是否以独立词（词边界 + 复数容忍）出现在 long 中——用于长术语覆盖判定。"""
    return word_pattern(short).search(long) is not None


def main():
    ap = argparse.ArgumentParser(description="r02 术语全量核对：02_terms.md 逐条检查译文译名落地（替代人工抽查）")
    ap.add_argument("srt", help="01_subtitle_asr_fixed.srt")
    ap.add_argument("terms", help="02_terms.md（术语映射表，含「原文」「译名」表头）")
    ap.add_argument("r02", help="r02_results 目录（每块一个 chunk_<k>.txt）")
    ap.add_argument("--chunks", required=True, help="chunks 目录（解析块↔cue 区间）")
    ap.add_argument("--verbose", action="store_true", help="展开打印全部 ✅ 命中（默认折叠）")
    args = ap.parse_args()

    cues = parse_srt(args.srt)
    cue_map = {idx: body for idx, body in cues}
    terms = parse_terms(args.terms)
    chunks = collect_chunk_files(args.chunks)
    if not terms:
        sys.exit("❌ 02_terms.md 未解析到术语条目（检查表头是否含「原文」「译名」）")
    if not chunks:
        sys.exit(f"❌ chunks 目录无块文件：{args.chunks}")

    # 块 → OWNED cue 区间 + 拼接文本（跨 cue 拆词的术语在块级拼接下可命中）+ 紧凑版（无空格命令名匹配用）
    chunk_text = {}
    for k in sorted(chunks):
        rng = parse_owned_cue_range(chunks[k])
        if rng is None:
            continue
        cmin, cmax = rng
        parts = [cue_map.get(i, "") for i in range(cmin, cmax + 1)]
        joined = " ".join(p for p in parts if p)
        chunk_text[k] = (cmin, cmax, joined, compact(joined))

    # 预计算：每条术语的"更长术语"索引（其词形以独立词形式包含于更长词形，如 column ⊂ water column）
    term_index = {i: term_forms(en) for i, (en, _, _) in enumerate(terms)}
    longer_terms = {}
    for i, (en, _, _) in enumerate(terms):
        others = []
        for j, (en2, _, _) in enumerate(terms):
            if i == j:
                continue
            if any(is_subword(f, fj) for f in term_index[i] for fj in term_index[j]):
                others.append(j)
        # 按更长词形长度降序（移除覆盖时先长后短，避免嵌套覆盖残留）
        others.sort(key=lambda j: -max(len(f) for f in term_index[j]))
        longer_terms[i] = others

    print(f"=== 术语全量核对（{len(terms)} 条 × {len(chunk_text)} 块） ===")
    n_hit = n_miss = n_absent = n_covered = 0
    for i, (en, zh, tline) in enumerate(terms):
        # 词形 → (词边界正则, 紧凑兜底正则)；无空格/连字符的拼接词形（setblock）额外走紧凑版
        pats, cpat = [], []
        for f in term_index[i]:
            pats.append(word_pattern(f))
            if not re.search(r"[ \-]", f):
                cpat.append(compact_pattern(f))
        if not pats:
            continue
        # ① 原文定位：命中块集合
        hit = [k for k, (_, _, text, ctext) in sorted(chunk_text.items())
               if any(p.search(text) for p in pats) or any(p.search(ctext) for p in cpat)]
        if not hit:
            n_absent += 1
            print(f"ℹ️ {en} → {zh}\n    01 全文未命中——查 ASR 修正列/词形变体（措辞变体或大小写，必要时更新 02_terms.md 行 {tline}）")
            continue
        # ② 长术语优先覆盖：命中块中，01 原文里该词若全部被更长术语覆盖（更长术语译文已✅）则放行
        real = []
        for k in hit:
            txt_snip = chunk_text[k][2]
            covered = False
            for j in longer_terms[i]:
                for fj in term_index[j]:
                    txt_snip = word_pattern(fj).sub(" ", txt_snip)
                if not (any(p.search(txt_snip) for p in pats) or any(p.search(compact(txt_snip)) for p in cpat)):
                    covered = True
                    break
            if not covered:
                real.append(k)
        if not real:
            n_covered += 1
            if args.verbose:
                print(f"✅ {en} → {zh}  （原文出现均被更长术语覆盖，无需单独核对）")
            continue
        # ③ 译名检查：逐真实命中块读 r02 译文（逐行定位，告警带文件行号+上下文）
        tforms = trans_forms(zh)
        miss = []
        for k in real:
            rp = os.path.join(args.r02, "chunk_%03d.txt" % k)
            if not os.path.exists(rp):
                miss.append((k, "无 r02 块文件", []))
                continue
            raw = strip_stitch_marks(open(rp, encoding="utf-8").read())
            if not raw.strip():
                miss.append((k, "r02 块为空", []))
                continue
            if not any(norm_zh(tf) in norm_zh(raw) for tf in tforms):
                # 定位：含英文的行（命令/参数/专名保留嫌疑）+ 该行上下文；无英文则给整块行号范围
                en_lines = [(ln, ln_text) for ln, ln_text in enumerate(raw.split("\n"), 1)
                            if re.search(r"[A-Za-z]", ln_text)]
                ctx = [f"行 {ln}｜{ln_text[:60]}{'…' if len(ln_text) > 60 else ''}"
                       for ln, ln_text in en_lines[:3]]
                if not ctx:
                    nlines = len(raw.split("\n"))
                    ctx = [f"行 1-{nlines}｜{raw.split(chr(10))[0][:60]}（整块无英文，疑意译/漏译，需打开块核对）"]
                miss.append((k, "", ctx))
        if miss:
            n_miss += 1
            # 01 原句：术语在首个真实命中块内的首现 cue 文本（供 Agent 对照原文判断意译/漂移）
            first_k = miss[0][0]
            src_snip = ""
            for p in pats:
                m = p.search(chunk_text[first_k][2])
                if m:
                    s = max(0, m.start() - 25)
                    src_snip = chunk_text[first_k][2][s:m.end() + 25]
                    break
            print(f"⚠️ {en} → {zh}")
            for k, why, ctx in miss:
                fname = os.path.basename(os.path.join(args.r02, "chunk_%03d.txt" % k))
                extra = f"（{why}）" if why else ""
                print(f"    {fname}{extra} 译文未见确认译名")
                for c in ctx:
                    print(f"        · {c}")
            if src_snip:
                print(f"    01 原句（块 {first_k}）: …{src_snip}…")
            print(f"    02_terms.md 行 {tline}：`{en}` → `{zh}`")
            ok = "/".join(str(k) for k in real if k not in [m[0] for m in miss])
            print(f"    Agent 复核：意译 / 漏译 / 漂移（漂移回写 r02 对应块）" +
                  (f"（其余命中块 {ok} 已正确）" if ok else ""))
        else:
            n_hit += 1
            if args.verbose:
                print(f"✅ {en} → {zh}  （块 {'/'.join(str(k) for k in real)} 均含译名）")

    print(f"\n汇总：{len(terms)} 条术语 / ✅ {n_hit} / ⚠️ {n_miss} / ℹ️ {n_absent} / 🔒长术语覆盖 {n_covered}")
    if n_miss or n_absent:
        print("❌ 退出码 1：有未命中项，Agent 复核后才可放行")
        sys.exit(1)
    print("✅ 术语全量核对通过：全部术语在对应块译文中使用了确认译名")
    return 0


if __name__ == "__main__":
    main()
