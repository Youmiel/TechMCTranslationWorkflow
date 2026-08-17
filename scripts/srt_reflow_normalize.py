# -*- coding: utf-8 -*-
"""块目录归一化：两种输入形态统一处理，折行 ≤1000 字符/行（一次命令跑完整个目录）

回填工作流（reflow-redstone）两类归一化共用本脚本：
- **chunks 模式（步骤 3）**：`chunks/`（cue 结构）→ `r01_normalized/`——把每块 `## BEFORE/OWNED/AFTER`
  分区内 cue 文本预先合并成连续文本（subagent 无需自行拼接），供补标点 subagent 输入
- **纯文本模式（步骤 5）**：`r02_results/`（整段译文）→ `r02_normalized/`——**复制 + 长度限制**：
  把译文复制为折行副本（不改 r02 原稿——ZH 忠实/术语核对基准不变），供分句 subagent 输入避免超长单行

自动检测：块文件首行 `# CHUNK` → chunks 模式（解析分区、合并 cue、保留分区结构）；
无块头 → 纯文本模式（整段 wrap_text 折行，内容不变仅限制单行长度）。

设计：
- 每块独立处理、互不影响；对整个输入目录一次跑完（命令只运行一次）
- 折行用 `wrap_text`（MAX_LINE=1000：英文词边界不拆词、中文按字符）——**显示性换行、非语义分行**，
  subagent 读取时按整段解析、忽略折行（任务规则里提示）
- 纯标记块（chunks 模式）输出空块注释；空文本块（纯文本模式）复制原文

用法（命令根 = Project_Main/）：
  python scripts/srt_reflow_normalize.py <chunks_dir> -o reflow/r01_normalized/    # 步骤 3（合并）
  python scripts/srt_reflow_normalize.py <r02_results_dir> -o reflow/r02_normalized/  # 步骤 5（复制+折行）
退出码：0 = 全部块归一化完成；1 = 有块解析失败。
"""
import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

from srt_reflow_common import wrap_text, collect_chunk_files, is_pure_marker, MAX_LINE

CHUNK_HEAD_RE = re.compile(r"^# CHUNK (\d+)/(\d+)\s+(.+)$")
SECTION_RE = re.compile(r"^## (BEFORE|OWNED|AFTER)\s*$")
CUE_RE = re.compile(r"^c\d+\t.+$")   # cue 行：`c<idx>\t[时间]\t文本`（srt）或 `c<idx>\t文本`（text）
COMMENT_RE = re.compile(r"^>")       # 注释行（如 `> 本块无语音整句`）跳过


def parse_chunk(path):
    """chunks 模式：解析块文件 → (head_str, {section: 连续文本})；纯标记 cue 剔除。"""
    head = ""
    sections = {"BEFORE": [], "OWNED": [], "AFTER": []}
    cur = None
    for ln in open(path, encoding="utf-8").read().split("\n"):
        if CHUNK_HEAD_RE.match(ln):
            head = ln
            continue
        m = SECTION_RE.match(ln)
        if m:
            cur = m.group(1)
            continue
        if cur is None or COMMENT_RE.match(ln):
            continue
        if ln.strip() == "":
            continue
        if not CUE_RE.match(ln):
            continue  # 非 cue 行跳过（防御）
        text = ln.split("\t")[-1].strip()
        if not text or is_pure_marker(text):
            continue
        sections[cur].append(text)
    if not any(sections.values()):
        return head, None
    merged = {s: " ".join(txts) for s, txts in sections.items() if txts}
    return head, merged


def parse_plain(path):
    """纯文本模式：读整段原文（r02 译文等）→ 返回去除首尾空白的原文。"""
    return open(path, encoding="utf-8").read().strip()


def main():
    ap = argparse.ArgumentParser(description="块目录归一化：chunks 模式（合并 cue + 折行）或纯文本模式（复制 + 折行），输出 ≤1000 字符/行")
    ap.add_argument("src", help="输入目录：chunks/（步骤 3 合并）或 r02_results/（步骤 5 复制+折行）")
    ap.add_argument("-o", "--out", required=True, help="输出目录（如 reflow/r01_normalized/ 或 reflow/r02_normalized/）")
    ap.add_argument("--verbose", action="store_true", help="展开打印每块细节")
    args = ap.parse_args()

    blocks = collect_chunk_files(args.src)
    if not blocks:
        sys.exit(f"❌ 输入目录无块文件：{args.src}")
    os.makedirs(args.out, exist_ok=True)
    n_chunk = n_plain = 0
    for k in sorted(blocks):
        path = blocks[k]
        out_path = os.path.join(args.out, "chunk_%03d.txt" % k)
        with open(path, encoding="utf-8") as fh:
            first = fh.readline()
        if CHUNK_HEAD_RE.match(first):
            # chunks 模式：合并 cue + 折行，保留分区结构
            n_chunk += 1
            head, merged = parse_chunk(path)
            if merged is None:
                # 全标记块：保留块头 + 空 OWNED 注释（subagent 补标点产物为空块，后续校验跳过）
                with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write((head + "\n") if head else f"# CHUNK {k:02d}  (空块)\n")
                    fh.write("## OWNED\n> 本块无语音 cue（全标记），无需补标点\n")
                if args.verbose:
                    print(f"   ⚠️ chunk_{k:03d}: 全标记空块（仅保留块头）")
                continue
            lines = [head, ""] if head else []
            for s in ("BEFORE", "OWNED", "AFTER"):
                if s in merged:
                    lines += [f"## {s}", ""]
                    lines += [wrap_text(merged[s], MAX_LINE), ""]
            with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("\n".join(lines).rstrip("\n") + "\n")
            if args.verbose:
                lens = {s: len(merged[s]) for s in merged}
                print(f"   chunk_{k:03d}（合并）: {lens}")
        else:
            # 纯文本模式：复制 + 折行（内容不变，仅限制单行长度）
            n_plain += 1
            text = parse_plain(path)
            if not text:
                with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write("\n")
                if args.verbose:
                    print(f"   ⚠️ chunk_{k:03d}: 空文本块（复制原文）")
                continue
            with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(wrap_text(text, MAX_LINE) + "\n")
            if args.verbose:
                print(f"   chunk_{k:03d}（复制+折行）: {len(text)} 字符")
    print(f"✅ 归一化完成：{len(blocks)} 块 → {args.out}"
          f"（chunks 合并 {n_chunk} / 纯文本复制折行 {n_plain}，折行 ≤{MAX_LINE} 字符/行）")
    return 0


if __name__ == "__main__":
    main()
