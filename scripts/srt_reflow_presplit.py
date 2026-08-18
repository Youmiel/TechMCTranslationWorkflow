# -*- coding: utf-8 -*-
"""块目录预分句标号（方案 3，2026-08-18）：EN 按句末标点 .?! / ZH 按句末标点 。！？… 预分句并标号，
供分句 subagent（task-split）作为输入骨架——agent 只做重新拼装 + 中英对照，不再自行逐句分句。

回填工作流（reflow-redstone）步骤 5 分句输入改造（r03 归一化系列，取代 r02 折行副本）：
- **EN 预分句**：`reflow/r01_results/`（补标点整段，衔接归位后）→ `reflow/r03_normalized_1/`
  ——按句末标点 `.?!` 分句（常见缩写 Mr./Fig./e.g. 等保护、跨块句标记剥离），编号 E1..En
- **ZH 预分句**：`reflow/r02_results/`（整段译文原稿，脚本读取不受行宽限制）→ `reflow/r03_normalized_2/`
  ——按句末标点 `。！？…` 分句（括号配平保护），编号 Z1..Zm

设计：
- **不形成中英对照**：EN/ZH 各自独立列表、各自编号；1:1 / 1:n / n:1 关系由分句 subagent 判断
- 预分句是**初分骨架**：游离停顿词归属、长句按语义再切/合并、子单元切分仍是 agent 工作（见 task-split）
- 产物契约 r03 不变；本脚本只生成**分句 subagent 输入**，非校验基准
- 每块独立处理、互不影响；对整个输入目录一次跑完（命令只运行一次）
- 折行用 `wrap_text`（MAX_LINE=1000）——**显示性换行、非语义分行**，subagent 按整段解析、忽略折行

用法（命令根 = Project_Main/）：
  python scripts/srt_reflow_presplit.py reflow/r01_results/ reflow/r02_results/ -o reflow/
    → reflow/r03_normalized_1/chunk_<k>.txt（EN 预分句 E1..En）
    → reflow/r03_normalized_2/chunk_<k>.txt（ZH 预分句 Z1..Zm）
退出码：0 = 全部块预分句完成；1 = 输入目录无块文件。
"""
import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

from srt_reflow_common import wrap_text, collect_chunk_files, strip_stitch_marks, MAX_LINE

# EN 句末标点（可连续：... / !?）；ZH 句末标点（含省略号）
EN_EOS_RE = re.compile(r"[.!?]+")
ZH_EOS_RE = re.compile(r"[。！？…]+")
# EN 常见缩写（缩写点不作句末）：字幕场景常用；匹配须紧邻标点（以 . 结尾）
EN_ABBR_RE = re.compile(
    r"(?i)(?<![A-Za-z])"
    r"(?:Mr|Mrs|Ms|Dr|Prof|Rev|St|Sr|Jr|vs|etc|al|Inc|Ltd|Corp|Co|Dept|"
    r"Fig|Eq|No|Vol|e\.g|i\.e|approx|min|max|hr|sec|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
    r"\.\s*$"
)
ZH_OPEN_RE = "（【「“‘"
ZH_CLOSE_RE = "）】」”’"


def is_en_sentence_end(text, start, end):
    """EN 判定 [start,end) 处标点是否为句末：字幕句首常小写——省略号（...）与缩写点为非句末，
    标点后跟空格/结束即句末（无空格直接续小写 = 异常粘连，非句末）。"""
    seg = text[start:end]
    if "..." in seg:
        return False  # 省略号 = 句内停顿（不切；agent 按语义再切）
    if EN_ABBR_RE.search(text[:end]):
        return False  # 缩写点保护（Mr./Fig./e.g. 等）
    nxt = text[end : end + 1]
    if nxt and nxt.islower():
        return False  # 标点后无空格直接续小写（异常粘连）→ 非句末
    return True


def split_en(text):
    """英文整段按句末标点 .?! 分句（先合并显示折行、剥离跨块句标记）→ [句文本]。"""
    text = re.sub(r"\s+", " ", text.strip())
    text = strip_stitch_marks(text).strip()
    sentences, buf = [], []
    i, n = 0, len(text)
    while i < n:
        m = EN_EOS_RE.search(text, i)
        if not m:
            buf.append(text[i:])
            i = n
            break
        end = m.end()
        if is_en_sentence_end(text, m.start(), end):
            sentences.append("".join(buf) + text[i:end])
            buf = []
        else:
            buf.append(text[i:end])
        i = end
    if buf:
        sentences.append("".join(buf))
    return [s.strip() for s in sentences if s.strip()]


def _is_cjk(ch):
    """CJK/全角（含全角标点）判定——折行合并时空格保留策略用（与 srt_reflow_core/io.py FULLWIDTH_RE 一致）。"""
    return (
        "\u2e80" <= ch <= "\u9fff"
        or "\uac00" <= ch <= "\ud7af"
        or "\u3040" <= ch <= "\u30ff"
        or "\uf900" <= ch <= "\ufaff"
        or "\uff00" <= ch <= "\uffef"
    )


def _collapse_ws(text):
    """折行合并（显示性换行折叠）：空白两侧均为 CJK/全角 → 删除；否则折叠为单空格
    （保留中英/数字混排空格——`Carpet 的 fillUpdates`、`139 147 11` 不受影响）。"""
    out = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            j = i
            while j < n and text[j].isspace():
                j += 1
            prev = out[-1] if out else ""
            nxt = text[j] if j < n else ""
            if not (prev and nxt and _is_cjk(prev) and _is_cjk(nxt)):
                out.append(" ")
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out).strip()


def split_zh(text):
    """中文整段按句末标点 。！？… 分句（折行合并保留中英/数字空格、括号配平保护）→ [句文本]。"""
    text = _collapse_ws(text)
    sentences, buf = [], []
    i, n = 0, len(text)
    depth = 0
    while i < n:
        c = text[i]
        if c in ZH_OPEN_RE:
            depth += 1
        elif c in ZH_CLOSE_RE:
            depth = max(0, depth - 1)
        m = ZH_EOS_RE.match(text, i)
        if m and depth == 0:
            sentences.append("".join(buf) + text[i : m.end()])
            buf = []
            i = m.end()
        else:
            buf.append(c)
            i += 1
    if buf:
        sentences.append("".join(buf))
    return [s.strip() for s in sentences if s.strip()]


def render(prefix, sentences):
    """渲染预分句文件：`- E1: 句文本`（ZH 用 Z 前缀）；句内 wrap_text 折行、续行顶格（显示性换行）。"""
    if not sentences:
        return f"# {prefix} 预分句（空块，无句末标点）\n"
    lines = [f"# {prefix} 预分句 — 按句末标点分句，编号 {prefix}1..{prefix}{len(sentences)}；句内显示折行按整段解析"]
    for idx, s in enumerate(sentences, 1):
        wrapped = wrap_text(s, MAX_LINE).split("\n")
        lines.append(f"- {prefix}{idx}: {wrapped[0]}")
        lines.extend(wrapped[1:])
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(
        description="块目录预分句标号：EN（r01_results）按 .?! 分句 → r03_normalized_1/；ZH（r02_results）按 。！？ 分句 → r03_normalized_2/"
    )
    ap.add_argument("en_dir", help="EN 输入目录：reflow/r01_results/（补标点整段）")
    ap.add_argument("zh_dir", help="ZH 输入目录：reflow/r02_results/（整段译文原稿）")
    ap.add_argument("-o", "--out", required=True, help="输出基目录（生成 r03_normalized_1/ 与 r03_normalized_2/）")
    ap.add_argument("--verbose", action="store_true", help="展开打印每块句数")
    args = ap.parse_args()

    en_blocks = collect_chunk_files(args.en_dir)
    zh_blocks = collect_chunk_files(args.zh_dir)
    if not en_blocks and not zh_blocks:
        sys.exit("❌ 输入目录无块文件")
    en_out = os.path.join(args.out, "r03_normalized_1")
    zh_out = os.path.join(args.out, "r03_normalized_2")
    os.makedirs(en_out, exist_ok=True)
    os.makedirs(zh_out, exist_ok=True)

    keys = sorted(set(en_blocks) | set(zh_blocks))
    n_en = n_zh = 0
    for k in keys:
        if k in en_blocks:
            with open(en_blocks[k], encoding="utf-8") as fh:
                sents = split_en(fh.read())
            n_en += len(sents)
            with open(os.path.join(en_out, "chunk_%03d.txt" % k), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(render("E", sents))
            if args.verbose:
                print(f"   chunk_{k:03d}（EN）: {len(sents)} 句")
        if k in zh_blocks:
            with open(zh_blocks[k], encoding="utf-8") as fh:
                sents = split_zh(fh.read())
            n_zh += len(sents)
            with open(os.path.join(zh_out, "chunk_%03d.txt" % k), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(render("Z", sents))
            if args.verbose:
                print(f"   chunk_{k:03d}（ZH）: {len(sents)} 句")
    print(f"✅ 预分句完成：EN {len(en_blocks)} 块 / {n_en} 句 → {en_out}；ZH {len(zh_blocks)} 块 / {n_zh} 句 → {zh_out}")
    return 0


if __name__ == "__main__":
    main()
