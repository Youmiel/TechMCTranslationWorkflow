# -*- coding: utf-8 -*-
"""chunks 块文件归一化：把每块（BEFORE/OWNED/AFTER 分区）的 cue 文本预先合并成连续文本，折行 ≤1000 字符

回填工作流（reflow-redstone）步骤 3 归一化：补标点 subagent 输入从 `chunks/chunk_<k>.txt`（cue 结构）
改为 `r01_normalized/chunk_<k>.txt`（已合并连续文本）——subagent 无需再自行拼接 cue 文本，
只补标点；一次命令处理整个 chunks/ 目录（每块独立合并，各块互不影响）。

设计：
- 输入：text_chunk.py 生成的 chunks 目录（块文件含 `# CHUNK` 块头 + `## BEFORE/OWNED/AFTER` 分区）
- 每块独立处理：各分区内按 cue 顺序拼接文本（剔除 [Music]/[Applause] 等纯标记 cue），
  经 wrap_text 折行（MAX_LINE=1000：英文词边界不拆词、中文按字符）后输出
- 产物保留分区结构（`## BEFORE`/`## OWNED`/`## AFTER`）+ 块头元信息，供 subagent 判断跨块句补全
- **折行是显示性换行、非语义分行**——subagent 读取时按整段解析、忽略折行（任务规则里提示）

用法（命令根 = Project_Main/）：
  python scripts/srt_reflow_normalize.py <chunks_dir> -o <r01_normalized_dir>
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
    """解析块文件 → (head_str, {section: 连续文本})；纯标记 cue 剔除。"""
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


def main():
    ap = argparse.ArgumentParser(description="chunks 块文件归一化：每块 cue 文本预先合并 + 折行 ≤1000，输出 r01_normalized/")
    ap.add_argument("chunks", help="chunks 目录（text_chunk.py 输出，含 chunk_<k>.txt）")
    ap.add_argument("-o", "--out", required=True, help="输出目录（如 reflow/r01_normalized/）")
    ap.add_argument("--verbose", action="store_true", help="展开打印每块细节")
    args = ap.parse_args()

    chunks = collect_chunk_files(args.chunks)
    if not chunks:
        sys.exit(f"❌ chunks 目录无块文件：{args.chunks}")
    os.makedirs(args.out, exist_ok=True)
    n_err = 0
    for k in sorted(chunks):
        head, merged = parse_chunk(chunks[k])
        out_path = os.path.join(args.out, "chunk_%03d.txt" % k)
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
            print(f"   chunk_{k:03d}: {lens}")
    print(f"✅ 归一化完成：{len(chunks)} 块 → {args.out}（每块 OWNED/BEFORE/AFTER 文本已合并，折行 ≤{MAX_LINE} 字符/行）")
    if n_err:
        sys.exit(1)
    return 0


if __name__ == "__main__":
    main()
