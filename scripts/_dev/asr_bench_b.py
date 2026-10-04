# -*- coding: utf-8 -*-
"""生成 ASR 对照实验材料（B 组 = 仅词表 / C 组 = 词表 + asr_fixes）。

## 实验设计（三组对照）

| 组 | 条件 | 材料 | 回答 |
|---|---|---|---|
| **A（裸）** | 既无词表也无映射 | `_work/_asr_bench/`（既有） | 模型自身能力 |
| **B（仅词表）** | 注入常驻集词表 | `_work/_asr_bench_b/` | 词表的增量价值 |
| **C（生产）** | 词表 + `asr_fixes` 映射 | `_work/_asr_bench_c/` | **映射在词表之上还有多少价值** |

**C 组的意义**：B 组只能说明“无词表时模型能否改对”，**不能**说明删掉映射是否安全——
因为映射的价值不止补知识，还有**提供精确词形 + 抑制乱猜**。实测：`titics` 在 B 组
被改成 `ticks`（丢中间词），在 C 组才是完整的 `tile ticks`。故**删任何映射前必须跑 C 组**。

**唯一变量**：注入内容。其余（分块、cue 范围、任务措辞、输出格式）与 A/B **逐字一致**。

## 注入格式（与生产一致）

- 词表：`- 英文 = 缩写 = 译名`（常驻集）
- 映射：`- 正确词 ← 变体1 / 变体2`（`asr_fixes.md` 解析，格式对齐
  `render_preprocess_prompt.parse_asr_fixes`）

用法（命令根 = Project_Main/）：
  python scripts/_dev/asr_bench_b.py gen [--videos N] [--only <视频,视频>] [--with-fixes]
"""
import argparse
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE, "scripts"))

import glossary_load_plan as GLP                    # noqa: E402
from shared.glossary_sources import iter_terms      # noqa: E402
import asr_bench as AB                              # noqa: E402

A_DIR = os.path.join(BASE, "_work", "_asr_bench")
B_DIR = os.path.join(BASE, "_work", "_asr_bench_b")
C_DIR = os.path.join(BASE, "_work", "_asr_bench_c")
ASR_FIXES = os.path.join(BASE, ".github", "experience", "asr_fixes.md")


def asr_fix_rows(path=ASR_FIXES):
    """`asr_fixes.md` → 注入行 `- 正确词 ← 变体（说明）`（与生产解析一致）。"""
    rows = []
    if not os.path.exists(path):
        return rows
    for ln in open(path, encoding="utf-8"):
        s = ln.strip()
        if not (s.startswith("|") and s.endswith("|")):
            continue
        cols = [c.strip() for c in s.strip("|").split("|")]
        if len(cols) < 2 or not cols[0]:
            continue
        if cols[0].lower() in ("正确词", "correct") or not cols[0].strip("-: "):
            continue
        variants = cols[1] if len(cols) > 1 else ""
        note = cols[2] if len(cols) > 2 else ""
        line = f"- {cols[0]} ← {variants}" if variants else f"- {cols[0]}"
        if note and note != variants:
            line += f"（{note}）"
        rows.append(line)
    return rows


def resident_rows():
    """常驻集 → 注入行（与 render_preprocess_prompt 同格式）。"""
    rows = []
    seen = set()
    for rel in GLP.RESIDENT:
        p = GLP.resolve(rel)
        if not p:
            continue
        for terms, zh, shorts in iter_terms(p):
            abbr = "/".join(shorts) if shorts else ""
            for t in terms:
                key = t.lower()
                if key in seen:
                    continue
                seen.add(key)
                rows.append(f"- {t} = {abbr} = {zh}" if (abbr and zh)
                            else (f"- {t} = {zh}" if zh else f"- {t}"))
    return rows


def cmd_gen(args):
    rows = resident_rows()
    if not rows:
        sys.exit("常驻集为空——检查 glossary_load_plan.RESIDENT")
    fixes = asr_fix_rows() if args.with_fixes else []
    if args.with_fixes and not fixes:
        sys.exit("asr_fixes.md 为空或解析失败")
    out_dir = C_DIR if args.with_fixes else B_DIR
    out_name = "_asr_bench_c" if args.with_fixes else "_asr_bench_b"

    pairs = AB.collect_pairs()
    pairs = [p for p in pairs if AB._cue_counts(p)[0] == AB._cue_counts(p)[1]]
    if args.only:
        want = {x.strip() for x in args.only.split(",") if x.strip()}
        pairs = [p for p in pairs if p[0] in want]
    pairs = pairs[:args.videos]
    if not pairs:
        sys.exit("无可配对样本")

    os.makedirs(out_dir, exist_ok=True)
    n_files = 0
    for v, _raw, _fixed, _loc in pairs:
        # 复用 A 组的分块边界（逐字对齐），保证唯一变量 = 注入内容
        chunks = sorted(f for f in os.listdir(A_DIR)
                        if f.startswith(f"{v}_chunk_") and f.endswith(".md"))
        for cf in chunks:
            k = re.search(r"_chunk_(\d+)\.md$", cf).group(1)
            a_text = open(os.path.join(A_DIR, cf), encoding="utf-8").read()
            # 取 A 组的待修正表（逐字复制，保证 cue 范围一致）
            m = re.search(r"## 待修正对照表\n\n(.*?)\n?$", a_text, re.S)
            if not m:
                continue
            table = m.group(1).rstrip("\n")
            L = [f"# ASR 修正任务（{v}，第 {int(k)} 块，共 {len(table.splitlines())} 条）",
                 "", "## 任务", "",
                 "下表的英文句子来自 **YouTube 自动字幕（ASR）**，"
                 "其中**部分词被误识别**。请逐条判断并修正。", "",
                 "**纪律**：", "",
                 "- 只修正**明显的 ASR 误听**（同音/近音误识别、漏字母、词边界错误）",
                 "- **不要改写措辞、不要润色、不要翻译**",
                 "- 如果某条你觉得没问题，就**原样保留**", ""]
            if fixes:
                L += ["## ASR 修正映射（怪词先查映射，再考虑联想）", "",
                      "Mapping 是**已知的**误听 → 正确词对应，命中即按正确词替换。", ""]
                L.extend(fixes)
                L.append("")
            L += ["## 术语词集（供 ASR 纠错参考，勿据此改动本身正确的词）", "",
                  "> - 仅当某词**在语境中不成立**才替换",
                  "> - 词集是**候选空间**，不是“替换目标清单”",
                  "> - 通用英文词不在本表内（拼写错误自行纠正，勿查表）", ""]
            L.extend(rows)
            L += ["", "## 输出", "",
                  f"写盘到 `_work/{out_name}/{v}_fixed_{k}.tsv`，"
                  "每行：`<行号>\\t<修正后英文>`（制表符分隔，无表头）。", "",
                  "行数 = 本块条数，行号与下表一致。**无改动也要输出该行**（原样）。", "",
                  f"写盘后报告 `已写入 {v}_fixed_{k}.tsv`。", "",
                  "## 待修正对照表", "", table, ""]
            with open(os.path.join(out_dir, f"{v}_chunk_{k}.md"), "w",
                      encoding="utf-8") as f:
                f.write("\n".join(L))
            n_files += 1
    extra = f"，{len(fixes)} 映射行" if fixes else ""
    print(f"已生成材料 → _work/{out_name}/（{n_files} 块，{len(rows)} 词表行{extra}）")
    print(f"  视频：{', '.join(v for v, *_ in pairs)}")


def main():
    ap = argparse.ArgumentParser(description="生成 ASR 对照实验材料（B 组 / C 组）")
    ap.add_argument("cmd", choices=["gen"], help="gen = 生成材料")
    ap.add_argument("--videos", type=int, default=99, help="最多几个视频")
    ap.add_argument("--only", help="只做指定视频（逗号分隔）")
    ap.add_argument("--with-fixes", action="store_true",
                    help="C 组：额外注入 asr_fixes 映射（= 生产实际条件）")
    args = ap.parse_args()
    cmd_gen(args)


if __name__ == "__main__":
    main()
