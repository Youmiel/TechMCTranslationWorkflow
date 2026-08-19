# -*- coding: utf-8 -*-
"""preprocess 阶段一 subagent prompt 渲染脚本（会话外组装落盘，独立于 reflow 渲染链路）。

把「任务模板 + 纪律母版 + 产物格式约定 + 先验知识 + 块数据引用 + 写盘约定」渲染成最终
subagent prompt，落盘 `_work/<视频名>/prompts/<task>-chunk_<k>.txt`。

服务任务（preprocess §1.1，translate / reflow 两工作流共享的阶段一）：
  - task-term-recognition：术语识别（输入 `_term_chunks/` → 输出 `_term_results/`）
  - task-en-preprocess：英文预整理·第一次遍历（输入 `_en_chunks/` → 输出 `_en_results/`）

与 `render_subagent_prompt.py`（reflow 阶段二专用）分开：本脚本不读 02_terms.md（阶段一确认前
不存在）、注入的是阶段一先验（scan 命中项按块过滤 / asr_fixes 映射 / 领域术语集），而非
humanizer/术语表；两链路产物目录互不重叠。

核心动机与 reflow 渲染脚本一致：完整 prompt 文本**不进主会话历史**——主 agent 只发本脚本命令
（短）+ 派发时只给引用路径（见 subagent-dispatch「派发引用 prompt」），subagent 自行 read。
模板正文零改动（`<k>`/`<视频名>` 正则替换），纪律母版读 `subagent-dispatch/_discipline.md`。

用法（命令根 = Project_Main/）：
  python scripts/render_preprocess_prompt.py <task> --video <视频工作目录> [--chunk <k> | --all]
      [--scan <scan_terms.txt>] [--glossary <csv...>] [--asr-fixes <局部asr_fixes.md>]
      [--chunks-dir <目录>]

示例：
  python scripts/render_preprocess_prompt.py task-term-recognition \
      --video "_work/<视频名>" --all --scan _work/<视频名>/scan_terms.txt
  python scripts/render_preprocess_prompt.py task-en-preprocess \
      --video "_work/<视频名>" --all --glossary .cache/glossary/general.csv
"""
import argparse
import csv
import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(PROJECT_ROOT, ".github", "skills")
DISCIPLINE_PATH = os.path.join(SKILLS_DIR, "subagent-dispatch", "_discipline.md")
ASR_FIXES_GLOBAL = os.path.join(PROJECT_ROOT, ".github", "experience", "asr_fixes.md")

# 模板正文中「渲染步骤说明」注释的起点（渲染时剥离——该注释是给 agent/维护者看的元信息，
# 不是 subagent 执行内容，不应出现在最终 prompt）
FILL_MARKER = "> **渲染步骤"

# 任务名 → 渲染配置（chunks 目录默认 = <视频工作目录>/<chunks_key>）
TASKS = {
    "task-term-recognition": {
        "skill": "term-scan",
        "template": "task-term-recognition.md",
        "role": "术语识别",
        "format_section": None,  # 无外部格式权威，任务文件「输出」节已内联
        "inputs": ["_term_chunks/chunk_<k>.txt"],
        "output": "_term_results/chunk_<k>.txt",
        "chunks_key": "_term_chunks",
        "priors": ["scan", "glossary", "asr"],
    },
    "task-en-preprocess": {
        "skill": "term-scan",
        "template": "task-en-preprocess.md",
        "role": "英文预整理",
        "format_section": None,
        "inputs": ["_en_chunks/chunk_<k>.txt"],
        "output": "_en_results/chunk_<k>.srt",
        "chunks_key": "_en_chunks",
        "priors": ["asr", "glossary"],
    },
}

# 注：§1.2 术语查证（task-term-resolve）为研究型单次任务（agent = term-researcher），
# 不走本渲染脚本——任务规则静态内联于任务文件，派发时「任务文件 + term_pending.md 双引用」，见
# redstone-preprocess §1.2 / subagent-dispatch 任务导航表。


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def parse_owned_cues(chunk_path):
    """从块文件解析 OWNED 分区 cue 号集合（text_chunk.py 块格式：`c<idx>\\t<时间码>\\t<文本>`）。"""
    cues = set()
    in_owned = False
    for ln in read(chunk_path).splitlines():
        if re.match(r"^## (BEFORE|OWNED|AFTER)", ln):
            in_owned = ln.startswith("## OWNED")
            continue
        if in_owned:
            m = re.match(r"^c(\d+)\t", ln)
            if m:
                cues.add(int(m.group(1)))
    return cues


def parse_scan_terms(scan_path):
    """解析 scan_terms.txt：每行 `c<idx>\\t<时间戳> | <词> | <译名> | <来源> | <层级>`。"""
    items = []
    with open(scan_path, encoding="utf-8-sig") as f:
        for ln in f:
            ln = ln.rstrip("\n")
            if not ln.strip():
                continue
            if "\t" in ln:
                cue_s, rest = ln.split("\t", 1)
            else:
                cue_s, rest = ln.split(None, 1)
            m = re.match(r"^c(\d+)$", cue_s.strip())
            if not m:
                continue
            parts = [p.strip() for p in rest.split(" | ")]
            if len(parts) >= 4:
                items.append((int(m.group(1)), ln))
    return items


def parse_asr_fixes(path):
    """解析 asr_fixes.md 表格（`| 正确词 | 变体 | 说明 |`）→ 注入文本行 `正确词 ← 变体`。"""
    if not os.path.exists(path):
        return []
    lines = []
    for ln in read(path).splitlines():
        s = ln.strip()
        if not (s.startswith("|") and s.endswith("|")):
            continue
        cols = [c.strip() for c in s.strip("|").split("|")]
        if len(cols) < 2 or not cols[0]:
            continue
        if cols[0].startswith("===") or cols[0].lower() in ("正确词", "correct"):
            continue  # 表头
        if not cols[0].strip("-: "):
            continue  # 分隔行（| --- | --- | --- |）
        variants = cols[1] if len(cols) > 1 else ""
        note = cols[2] if len(cols) > 2 else ""
        line = f"- {cols[0]} ← {variants}" if variants else f"- {cols[0]}"
        if note and note != variants:
            line += f"（{note}）"
        lines.append(line)
    return lines


def load_glossary(csv_paths):
    """读领域术语集 csv（英文=Full Form (English) 列、中文=Chinese 列）→ `英文 = 中文` 注入行。"""
    rows = []
    for path in csv_paths:
        with open(path, encoding="utf-8-sig", newline="") as f:
            for rec in csv.reader(f):
                if len(rec) < 8:
                    continue
                en = (rec[2] or "").strip()
                zh = (rec[7] or "").strip()
                if en and zh:
                    rows.append(f"- {en} = {zh}")
    return rows


def collect_priors(cfg, video_dir, chunk, scan_path, glossary_paths, asr_fixes_paths, chunk_files):
    """按任务配置注入阶段一先验知识。"""
    parts = []
    video_name = os.path.basename(os.path.normpath(video_dir))
    priors = cfg["priors"]

    if "scan" in priors and scan_path and os.path.exists(scan_path):
        owned = parse_owned_cues(chunk_files[chunk])
        hits = [ln for cue, ln in parse_scan_terms(scan_path) if cue in owned]
        body = "\n".join(hits) if hits else "（本块 OWNED cue 无 scan 命中）"
        parts.append(
            "### scan 命中项（已登记术语表，命中项强制确认译名；已标注 ⚠️ 的为误报排除项）\n\n"
            + body
        )

    if "glossary" in priors and glossary_paths:
        rows = load_glossary(glossary_paths)
        if rows:
            parts.append(
                "### 领域术语集（阶段〇判定分类，ASR 解码候选空间 / 术语译名参考）\n\n"
                + "\n".join(rows)
            )

    if "asr" in priors:
        global_lines = parse_asr_fixes(ASR_FIXES_GLOBAL)
        local_lines = []
        for p in asr_fixes_paths:
            local_lines.extend(parse_asr_fixes(p))
        body = []
        if global_lines:
            body.append("（全局映射，跨视频通用）\n" + "\n".join(global_lines))
        if local_lines:
            body.append("（本视频局部映射，优先于全局）\n" + "\n".join(local_lines))
        parts.append("### ASR 修正映射（怪词先查全局 → 再查本视频局部）\n\n" + ("\n".join(body) if body else "（无）"))

    return "\n\n".join(parts) if parts else "（无）"


def list_chunks(chunks_dir):
    """列出 chunks 目录的块号集合（chunk_<k>.txt）。"""
    if not chunks_dir or not os.path.isdir(chunks_dir):
        return []
    nums = []
    for name in os.listdir(chunks_dir):
        m = re.match(r"chunk_(\d+)\.txt$", name)
        if m:
            nums.append(int(m.group(1)))
    return sorted(nums)


def collect_data(cfg, video_dir, chunk, chunks_dir):
    """生成 `## 本块数据`：输入数据文件引用 + 前后块衔接 + 输出路径。"""
    video_name = os.path.basename(os.path.normpath(video_dir))
    ck = f"chunk_{chunk:03d}"
    lines = []
    for inp in cfg["inputs"]:
        path = inp.replace("<k>", f"{chunk:03d}")
        lines.append(f"- 输入（只读）：`_work/{video_name}/{path}`")
    nums = list_chunks(chunks_dir)
    if nums:
        prev_k = chunk - 1 if chunk > 1 and (chunk - 1) in nums else None
        next_k = chunk + 1 if chunk < max(nums) and (chunk + 1) in nums else None
        ctx_template = cfg["inputs"][0].replace("<k>", "{k:03d}")
        prev_txt = f"前块 `_work/{video_name}/{ctx_template.format(k=prev_k)}`（仅语境）" if prev_k else "无（首块）"
        next_txt = f"后块 `_work/{video_name}/{ctx_template.format(k=next_k)}`（仅语境）" if next_k else "无（末块）"
        lines.append(f"- 衔接参考（只读）：{prev_txt}／{next_txt}")
    out_path = cfg["output"].replace("<k>", f"{chunk:03d}")
    lines.append(f"- 输出文件（写入）：`_work/{video_name}/{out_path}`（目录已存在，直接新建）")
    lines.append("")
    report = ck + ".srt（ASR 清单另写 chunk_" + f"{chunk:03d}" + ".asr.tsv）" if out_path.endswith(".srt") else ck + ".txt"
    lines.append("只读上述数据文件，写后报告 `已写入 " + report + "`")
    return "\n".join(lines)


def render(task, video_dir, chunk, scan_path, glossary_paths, asr_fixes_paths, chunks_dir):
    cfg = TASKS[task]
    video_name = os.path.basename(os.path.normpath(video_dir))

    # 1. 模板正文（剥离「渲染步骤说明」注释）
    template_path = os.path.join(SKILLS_DIR, cfg["skill"], cfg["template"])
    text = read(template_path)
    if FILL_MARKER in text:
        text = text.split(FILL_MARKER)[0].rstrip()
    # 2. 占位替换（模板正文零改动，仅正则替换）
    text = text.replace("<视频名>", video_name)
    text = text.replace("chunk_<k>", f"chunk_{chunk:03d}")
    text = text.replace("<k>", f"{chunk:03d}")

    # 3. 纪律母版（单一权威 _discipline.md，TASK_ROLE 按任务替换；剥离维护性头部）
    discipline = read(DISCIPLINE_PATH)
    discipline = discipline[discipline.find("## "):].replace("{TASK_ROLE}", cfg["role"])

    # 4. 产物格式约定（无外部格式权威的任务省略）
    fmt_block = ""
    if cfg["format_section"]:
        fmt_block = (
            f"> **产物格式约定**（唯一允许的外部读取）：见 `docs/PRODUCT_FORMATS.md` 的 "
            f"`{cfg['format_section']}` 节"
        )

    # 5. 先验知识（块文件供 scan 按 OWNED 过滤）
    chunk_files = {}
    for k in list_chunks(chunks_dir):
        p = os.path.join(chunks_dir, f"chunk_{k:03d}.txt")
        if os.path.exists(p):
            chunk_files[k] = p
    priors = collect_priors(cfg, video_dir, chunk, scan_path, glossary_paths, asr_fixes_paths, chunk_files)

    # 6. 本块数据
    data = collect_data(cfg, video_dir, chunk, chunks_dir)

    out = f"{text}\n\n---\n\n## 纪律母版（执行型 subagent 全局纪律，必须遵守）\n\n{discipline}\n\n"
    if fmt_block:
        out += f"---\n\n{fmt_block}\n\n"
    out += f"---\n\n## 先验知识\n\n{priors}\n\n---\n\n## 本块数据\n\n{data}\n"

    prompts_dir = os.path.join(video_dir, "prompts")
    os.makedirs(prompts_dir, exist_ok=True)
    out_path = os.path.join(prompts_dir, f"{task}-chunk_{chunk:03d}.txt")
    write(out_path, out)
    return out_path


def main():
    ap = argparse.ArgumentParser(description="渲染 preprocess 阶段一 subagent prompt 到 _work/<视频名>/prompts/")
    ap.add_argument("task", choices=sorted(TASKS.keys()), help="任务模板名")
    ap.add_argument("--video", required=True, help="视频工作目录（相对 Project_Main，如 _work/<视频名>）")
    ap.add_argument("--chunk", type=int, help="块号（1 起）")
    ap.add_argument("--all", action="store_true", help="渲染全部块")
    ap.add_argument("--scan", default=None, help="scan_terms.txt 路径（term-recognition；默认 <video>/scan_terms.txt）")
    ap.add_argument("--glossary", action="append", default=[], help="领域术语集 csv（可多次；en-preprocess 必需）")
    ap.add_argument("--asr-fixes", action="append", default=[], help="本视频局部 asr_fixes 文件（默认 <video>/asr_fixes.md）")
    ap.add_argument("--chunks-dir", default=None, help="chunks 目录（默认 <video>/<任务 chunks_key>）")
    args = ap.parse_args()

    video_dir = os.path.join(PROJECT_ROOT, args.video) if not os.path.isabs(args.video) else args.video
    cfg = TASKS[args.task]
    video_name = os.path.basename(os.path.normpath(video_dir))
    chunks_dir = args.chunks_dir or os.path.join(video_dir, cfg["chunks_key"])
    scan_path = args.scan or os.path.join(video_dir, "scan_terms.txt")
    asr_fixes_paths = args.asr_fixes or [os.path.join(video_dir, "asr_fixes.md")]

    if args.all:
        nums = list_chunks(chunks_dir)
        if not nums:
            print(f"错误：--all 需要 chunks 目录存在（{chunks_dir}），或用 --chunks-dir 指定", file=sys.stderr)
            sys.exit(1)
        for k in nums:
            print(f"生成 {render(args.task, video_dir, k, scan_path, args.glossary, asr_fixes_paths, chunks_dir)}")
    else:
        if not args.chunk:
            ap.error("需要 --chunk <k> 或 --all")
        print(f"生成 {render(args.task, video_dir, args.chunk, scan_path, args.glossary, asr_fixes_paths, chunks_dir)}")


if __name__ == "__main__":
    main()
