# -*- coding: utf-8 -*-
"""搭建 ASR 实测脚手架：提取配对样本 + 隔离测试材料。

## 目的

回答「**LLM 能否在无词表帮助下修正 ASR 误听**」——这是术语表注入的**唯一不可替代用途**
（翻译映射有 `glossary_lookup` + wiki agent 兜底，不需要术语表）。

## 方法（子任务 ③ 单组无词表实测）

对每个配对视频：

1. 取**原始 ASR**（文本未改的输入）
2. 分块 → 生成**隔离测试材料**（只给英文原文，**不给任何词表/对照物**）
3. 子代理**无词表**自由修正（可用词典知识、可用语义/音近推理，但不得查表）
4. **派发 agent 读取对照物**（`asr_fixes.md` 等）核对产物 → 产出差异清单
5. 汇总 → 回答「无词表时能修多少 / 会不会改坏」

## 隔离（关键）

`asr_fixes.md` 就在仓库里。为降低子代理"顺手打开抄答案"的概率：

- 测试材料落到**独立目录** `_work/_asr_bench/`
- agent 提示只给**该目录内的输入文件路径**
- agent 的 `tools` 压到 `[read, edit]`（无 search）——见 `asr-fixer.agent.md`

## 语料配对（实测）

| 项 | 数量 |
|---|---|
| 原始 ASR | 25 个视频 |
| `01_subtitle_asr_fixed.srt`（修正稿） | 21 个 |
| **可配对** | **19 个** |
| 有局部 `asr_fixes.md` | 18 个 |

用法（命令根 = Project_Main/）：
  python scripts/asr_bench.py gen [--videos N] [--chunk-cues 400]
  python scripts/asr_bench.py merge       # 合并子代理产出
"""
import argparse
import csv
import glob
import os
import re
import sys
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(BASE)
WORK = os.path.join(BASE, "_work", "_asr_bench")

SNAPPED = "00_subtitle_snapped.srt"
FIXED = "01_subtitle_asr_fixed.srt"
RAW_PAT = re.compile(r"(【原始字幕】|\[English \(auto-generated\)\]|DownSub|^[A-Za-z0-9_-]{11}_)")
PRODUCT_PAT = re.compile(
    r"(【字幕】|【断句字幕】|^output|^split_output|^task-|_bilingual|relfow2|refow2|"
    r"_bak_|\.en\.srt$|\.zh\.srt$)", re.IGNORECASE)


def vid_id(name):
    m = re.search(r"[A-Za-z0-9_-]{11}", name)
    return m.group(0) if m else None


def collect_pairs():
    """→ [(视频名, 原始ASR路径, 01修正稿路径, 局部asr_fixes路径|None)]。"""
    raws = {}
    for root in (os.path.join(BASE, "_input"), os.path.join(WORKSPACE, "_Sandbox"),
                 os.path.join(WORKSPACE, "_Archive")):
        if not os.path.isdir(root):
            continue
        for p in glob.glob(os.path.join(root, "**", "*.srt"), recursive=True):
            b = os.path.basename(p)
            if b == SNAPPED or (RAW_PAT.search(b) and not PRODUCT_PAT.search(b)):
                v = vid_id(b)
                if v and v not in raws:
                    raws[v] = p
    fixeds, locals_ = {}, {}
    for root in (os.path.join(BASE, "_work"), os.path.join(WORKSPACE, "_Archive"),
                 os.path.join(WORKSPACE, "_Sandbox")):
        if not os.path.isdir(root):
            continue
        for p in glob.glob(os.path.join(root, "**", FIXED), recursive=True):
            v = vid_id(os.path.basename(os.path.dirname(p)))
            if v and v not in fixeds:
                fixeds[v] = p
        for p in glob.glob(os.path.join(root, "**", "asr_fixes.md"), recursive=True):
            v = vid_id(os.path.basename(os.path.dirname(p)))
            if v and v not in locals_:
                locals_[v] = p
    out = []
    for v in sorted(set(raws) & set(fixeds)):
        out.append((v, raws[v], fixeds[v], locals_.get(v)))
    return out


def read_srt_cues(path):
    """→ [cue 文本]（跳过段号与时间码）。"""
    try:
        text = open(path, encoding="utf-8-sig").read()
    except OSError:
        return []
    out = []
    for block in re.split(r"\n\s*\n", text):
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) >= 3 and "-->" in lines[1]:
            out.append(" ".join(lines[2:]))
    return out


_CUE_CACHE = {}


def _cue_counts(pair):
    """配对样本 → (源 cue 数, 参考 cue 数)，带缓存。"""
    v, raw, fixed, _loc = pair
    if v not in _CUE_CACHE:
        _CUE_CACHE[v] = (len(read_srt_cues(raw)), len(read_srt_cues(fixed)))
    return _CUE_CACHE[v]


def cmd_gen(args):
    all_pairs = collect_pairs()
    # 核对子任务按**行号**对照「子代理产出 ↔ 参考稿」，要求 cue 数相等。
    # 参考稿可能做了合并/拆分（实测 3/19 个样本 cue 数不等）→ 只取对齐样本，
    # 避免行号错位污染核对结论（用户裁定 2026-10-03）。
    pairs = [p for p in all_pairs if _cue_counts(p)[0] == _cue_counts(p)[1]]
    skipped = [p for p in all_pairs if _cue_counts(p)[0] != _cue_counts(p)[1]]
    pairs = pairs[:args.videos]
    if not pairs:
        sys.exit("未找到可配对样本（原始 ASR + 01 修正稿）")
    os.makedirs(WORK, exist_ok=True)
    manifest = []
    meta_rows = []
    for v, raw, fixed, loc in pairs:
        src_cues = read_srt_cues(raw)
        tgt_cues = read_srt_cues(fixed)
        # 分块（按 cue 数）
        n = 0
        for i in range(0, len(src_cues), args.chunk_cues):
            part = src_cues[i:i + args.chunk_cues]
            if not part:
                continue
            n += 1
            out = os.path.join(WORK, f"{v}_chunk_{n:03d}.md")
            L = [f"# ASR 修正任务（{v}，第 {n} 块，共 {len(part)} 条）", ""]
            L.append("## 任务")
            L.append("")
            L.append("下表的英文句子来自 **YouTube 自动字幕（ASR）**，"
                     "其中**部分词被误识别**。请逐条判断并修正。")
            L.append("")
            L.append("**纪律**：")
            L.append("")
            L.append("- 只修正**明显的 ASR 误听**（同音/近音误识别、漏字母、词边界错误）")
            L.append("- **不要改写措辞、不要润色、不要翻译**")
            L.append("- **不要查任何词表/文件/网络**——本任务测的是你**自身的判断能力**")
            L.append("- 如果某条你觉得没问题，就**原样保留**")
            L.append("")
            L.append("## 输出")
            L.append("")
            L.append(f"写盘到 `_work/_asr_bench/{v}_fixed_{n:03d}.tsv`，"
                     "每行：`<行号>\\t<修正后英文>`（制表符分隔，无表头）。")
            L.append("")
            L.append("行数 = 本块条数，行号与下表一致。**无改动也要输出该行**（原样）。")
            L.append("")
            L.append(f"写盘后报告 `已写入 {v}_fixed_{n:03d}.tsv`。")
            L.append("")
            L.append("## 待修正对照表")
            L.append("")
            for k, cue in enumerate(part, 1):
                L.append(f"{k}. {cue}")
            L.append("")
            with open(out, "w", encoding="utf-8") as f:
                f.write("\n".join(L) + "\n")
        manifest.append((v, len(src_cues), len(tgt_cues), n))
        meta_rows.append({
            "video": v, "raw": os.path.relpath(raw, BASE).replace("\\", "/"),
            "fixed": os.path.relpath(fixed, BASE).replace("\\", "/"),
            "local_fixes": (os.path.relpath(loc, BASE).replace("\\", "/") if loc else ""),
            "src_cues": len(src_cues), "tgt_cues": len(tgt_cues),
            "aligned": int(len(src_cues) == len(tgt_cues)),
            "chunks": n,
        })
    # 清单（**给派发 agent 用**，含对照物路径）
    with open(os.path.join(WORK, "_manifest.csv"), "w", encoding="utf-8-sig",
              newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(meta_rows[0].keys()))
        w.writeheader()
        w.writerows(meta_rows)
    print(f"已生成测试材料 → {os.path.relpath(WORK, BASE)}/")
    print(f"  视频 {len(pairs)} 个（**已过滤为 cue 数对齐的样本**）；"
          f"块 {sum(m[3] for m in manifest)} 个；共 {sum(m[1] for m in manifest):,} 条源 cue")
    skipped = [p for p in collect_pairs()
               if _cue_counts(p)[0] != _cue_counts(p)[1]]
    if skipped:
        print(f"  已排除 {len(skipped)} 个错位样本（cue 数不等，按行号对照会错位）：")
        for v, _r, _f, _l in skipped:
            a, b = _cue_counts((v, _r, _f, _l))
            print(f"    {v}  源 {a} / 参考 {b}")
    for v, ns, nt, nc in manifest[:8]:
        print(f"    {v}  源 {ns:5d} cue / 参考 {nt:5d} cue / {nc} 块")
    print("  清单：_manifest.csv（含对照物路径，**勿给子代理**）")


def cmd_merge(args):
    """合并子代理产出 → 与参考稿对照，产差异清单。"""
    man = os.path.join(WORK, "_manifest.csv")
    if not os.path.exists(man):
        sys.exit("请先 gen")
    rows = list(csv.DictReader(open(man, encoding="utf-8-sig")))
    L = ["# ASR 实测：产物汇总", ""]
    L.append("| 视频 | cue（源/参考） | 对齐 | 块数 | 已产出 | 产出行数 |")
    L.append("|---|---|---|---|---|---|")
    tot_out = tot_diff = 0
    for r in rows:
        outs = glob.glob(os.path.join(WORK, f"{r['video']}_fixed_*.tsv"))
        n_out = len(outs)
        diff = 0
        for p in outs:
            try:
                lines = [ln.rstrip("\n") for ln in open(p, encoding="utf-8") if ln.strip()]
            except OSError:
                continue
            diff += sum(1 for ln in lines if "\t" in ln)
        tot_out += n_out
        tot_diff += diff
        al = "✅" if r.get("aligned", "1") == "1" else "**❌ 错位（跳过核对）**"
        L.append(f"| {r['video']} | {r['src_cues']}/{r['tgt_cues']} | {al} | "
                 f"{r['chunks']} | {n_out} | {diff} |")
    L.append("")
    L.append(f"产出块 **{tot_out}**；总行数 **{tot_diff}**")
    L.append("")
    L.append("> ⚠️ `对齐 = ❌` 的视频**不要核对**——参考稿做了合并/拆分，"
             "按行号对照会错位。")
    L.append("")
    out = os.path.join(WORK, "asr_bench_summary.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"已写入 {os.path.relpath(out, BASE)}")
    print(f"  产出块 {tot_out}；总行 {tot_diff}")


def main():
    ap = argparse.ArgumentParser(description="ASR 实测脚手架（单组无词表）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen", help="生成隔离测试材料")
    g.add_argument("--videos", type=int, default=8, help="取前几个配对视频（默认 8）")
    g.add_argument("--chunk-cues", type=int, default=400, help="每块 cue 数（默认 400）")
    sub.add_parser("merge", help="合并产物并出汇总")
    args = ap.parse_args()
    if args.cmd == "gen":
        cmd_gen(args)
    else:
        cmd_merge(args)


if __name__ == "__main__":
    main()
