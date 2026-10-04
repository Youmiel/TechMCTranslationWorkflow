# -*- coding: utf-8 -*-
"""asr_fixes 归档筛选清单：按「变体出现的视频数」分组，输出**可勾选** Markdown。

## 用法

生成的 `_work/_asr_scope.md` 里每条前有 `- [ ]` 复选框：

- **勾上 `[x]` = 归档**（该条移到 `_work/<视频名>/asr_fixes.md`）
- 不勾 = 保留在全局表

## 判据与其局限（重要）

判据 = 变体在多少个视频的**原始 ASR** 里出现（变体是误听产物，只存在于未修正文本）。

| 视频数 | 类 |
|---|---|
| ≥2 | 跨视频（大概率通用） |
| 1 | 单视频（**候选**，需人工判） |
| 0 | 语料未出现（无法判断） |

⚠️ **“单视频”≠“视频专属”**：19 个视频只是**现有语料**，某条只出现一次可能只是
“别的视频还没遇到该话题”。故单视频类**必须人工筛**，脚本不自动归档。

用法（命令根 = Project_Main/）：
  python scripts/_dev/asr_fixes_scope.py
  python scripts/_dev/asr_fixes_scope.py --out _work/_asr_scope.md
  python scripts/_dev/asr_fixes_scope.py --apply      # 按清单的 [x] 执行归档
"""
import argparse
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 兄弟开发脚本（同目录）+ scripts/（生产脚本与 shared/）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

import asr_bench as AB                              # noqa: E402
import asr_fixes_audit as A                         # noqa: E402


def norm_text(s):
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower())


def collect(all_videos=True):
    """→ (corpus: {视频: 归一化原文}, pairs)。"""
    pairs = AB.collect_pairs()
    corpus = {}
    for v, raw, _f, _l in pairs:
        try:
            text = open(raw, encoding="utf-8-sig", errors="replace").read()
        except OSError:
            continue
        corpus[v] = norm_text(text)
    return corpus, pairs


def scan(corpus):
    """→ {'cross'|'single'|'unknown': [(正确词, 变体, 说明, [视频])]}。"""
    rows = A.parse_fixes(A.ASR_FIXES)
    merged = {}
    for w, variants, desc in rows:
        merged.setdefault(w.lower(), [w, [], desc])[1].extend(variants)

    buckets = {"cross": [], "single": [], "unknown": []}
    for w, variants, desc in merged.values():
        hits = []
        for v, text in corpus.items():
            found = [vv for vv in variants
                     if re.search(r"(?<![a-z])" + re.escape(vv.lower().strip())
                                  + r"(?![a-z])", text)]
            if found:
                hits.append((v, found))
        vids = sorted({v for v, _ in hits})
        rec = (w, variants, desc, vids)
        key = "cross" if len(vids) >= 2 else ("single" if len(vids) == 1 else "unknown")
        buckets[key].append(rec)
    return buckets


def write_checklist(buckets, out, n_corpus):
    L = ["# asr_fixes 归档筛选清单", "",
         "> **勾选 `[x]` = 归档**（移到该视频的局部 `asr_fixes.md`）；不勾 = 保留在全局表。",
         "> 筛完保存，然后跑 `python scripts/_dev/asr_fixes_scope.py --apply` 执行。",
         "",
         f"- 语料：**{n_corpus}** 个视频的原始 ASR",
         f"- 条目：**{sum(len(b) for b in buckets.values())}** 个正确词",
         "",
         "| 类 | 数 | 建议 |", "|---|---|---|",
         f"| 跨视频（≥2 视频命中） | {len(buckets['cross'])} | 保留（无需筛） |",
         f"| **单视频（仅 1 视频命中）** | {len(buckets['single'])} | **逐条筛** |",
         f"| 语料未出现 | {len(buckets['unknown'])} | 保留（无法判断） |",
         "",
         "> ⚠️ **「单视频」≠「视频专属」**：现有语料只有这么多视频，某条只出现一次可能只是",
         "> 「别的视频还没遇到该话题」。判断标准 = **这条是否只服务于该视频的特定语境**。",
         ">",
         "> 典型该归档：一次性的口语/社区梗/整句漏词（`unlucky hopper`、`scared you'll mess my stuff up`）",
         ">",
         "> 典型该保留：通用机制的误听（`waterlogged blocks`、`nether portal`、`beacon`）——"
         "任何视频都可能遇到",
         ""]

    # 单视频类：按视频分组（方便你按视频判）
    by_video = {}
    for w, variants, desc, vids in buckets["single"]:
        by_video.setdefault(vids[0], []).append((w, variants, desc))
    L += ["## 一、单视频条目（逐条筛）", ""]
    for v in sorted(by_video):
        rows = sorted(by_video[v], key=lambda x: x[0].lower())
        L += [f"### `{v}`（{len(rows)} 条）", ""]
        for w, variants, desc in rows:
            L.append(f"- [ ] `{w}` ← {' / '.join(variants)}"
                     + (f"　　（{desc}）" if desc and desc != "—" else ""))
        L.append("")

    L += ["## 二、跨视频条目（建议保留）", "",
          "列出供参考；如认为某条其实该归档，也可勾选。", ""]
    for w, variants, _d, vids in sorted(buckets["cross"], key=lambda x: -len(x[3])):
        L.append(f"- [ ] `{w}` ← {' / '.join(variants[:5])}"
                 f"{' …' if len(variants) > 5 else ''}　　（{len(vids)} 视频）")
    L.append("")

    L += ["## 三、语料未出现（建议保留）", "",
          "现有语料找不到该变体（可能历史积累或已被修正）——**无证据，不建议归档**。", ""]
    for w, variants, desc, _v in sorted(buckets["unknown"], key=lambda x: x[0].lower()):
        L.append(f"- [ ] `{w}` ← {' / '.join(variants[:4])}"
                 + (f"　　（{desc}）" if desc and desc != "—" else ""))
    L.append("")

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


def parse_checked(path):
    """读清单 → 勾选的正词集合（`[x]` 或 `[X]`）。"""
    out = set()
    if not os.path.exists(path):
        return out
    for ln in open(path, encoding="utf-8"):
        if re.match(r"^\s*-\s*\[[xX]\]", ln):
            m = re.search(r"`([^`]+)`\s*←", ln)
            if m:
                out.add(m.group(1).lower())
    return out


def apply_archive(buckets, checked):
    """把勾选项从全局表移出，报告结果（**不自动写盘**，先看方案）。"""
    if not checked:
        print("清单里没有勾选项")
        return []
    allrec = {}
    for b in buckets.values():
        for w, variants, desc, vids in b:
            allrec[w.lower()] = (w, variants, desc, vids)
    acts = []
    for key in sorted(checked):
        if key in allrec:
            w, variants, desc, vids = allrec[key]
            acts.append((w, variants, vids))
        else:
            print(f"  ⚠️ 清单外的条目（忽略）: {key}")
    return acts


def main():
    ap = argparse.ArgumentParser(description="asr_fixes 归档筛选清单（可勾选）")
    ap.add_argument("--out", default=os.path.join(BASE, "_work", "_asr_scope.md"),
                    help="清单路径（默认 _work/_asr_scope.md）")
    ap.add_argument("--apply", action="store_true",
                    help="读清单的勾选项，打印归档方案（不自动改文件）")
    args = ap.parse_args()

    if args.apply:
        buckets = scan(collect()[0])
        checked = parse_checked(args.out)
        acts = apply_archive(buckets, checked)
        print(f"勾选 {len(checked)} 条；可归档 {len(acts)} 条\n")
        for w, variants, vids in acts:
            tgt = f"_work/{vids[0]}/asr_fixes.md" if vids else "（无归属视频）"
            print(f"  {w}  →  {tgt}")
        print()
        print("⚠️ 本命令只打印方案。实际移动作业需人工确认（AGENTS.md 核心原则 #6）")
        return

    corpus, pairs = collect()
    buckets = scan(corpus)
    write_checklist(buckets, args.out, len(corpus))
    print(f"已写入 {args.out}")
    print(f"  语料 {len(corpus)} 视频；单视频候选 {len(buckets['single'])}；"
          f"跨视频 {len(buckets['cross'])}；未出现 {len(buckets['unknown'])}")
    print(f"  筛完保存 → python scripts/_dev/asr_fixes_scope.py --apply")


if __name__ == "__main__":
    main()
