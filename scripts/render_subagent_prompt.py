# -*- coding: utf-8 -*-
"""subagent prompt 渲染脚本（会话外组装落盘）。

把「任务模板 + 纪律母版 + 产物格式约定 + 先验知识 + 块数据引用 + 写盘约定」渲染成最终
subagent prompt，落盘 `_work/<视频名>/prompts/<task>-chunk_<k>.txt`。

核心动机：完整 prompt 文本**不进主会话历史**——主 agent 只发本脚本命令（短）+ 派发时只给
引用路径（见 subagent-dispatch「派发引用 prompt」），subagent 自行 read。模板正文零改动
（`<k>`/`<视频名>` 正则替换），纪律母版读 `subagent-dispatch/_discipline.md`（单一权威），
术语直读 02_terms.md 全文。

用法：
  python scripts/render_subagent_prompt.py <task> --video <视频工作目录名> --chunk <k> \
      [--prior-file <额外先验文件>] [--chunks-dir <chunks目录>] [--all]

示例：
  python scripts/render_subagent_prompt.py task-split \
      --video "_work/uVOFckoMdIU_Engineering Minecraft's Fastest Shulker Farm" --chunk 2
  python scripts/render_subagent_prompt.py task-translate --video "<dir>" --all
"""
import argparse
import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(PROJECT_ROOT, ".github", "skills")
DISCIPLINE_PATH = os.path.join(SKILLS_DIR, "subagent-dispatch", "_discipline.md")

# 模板正文中「渲染步骤说明」注释的起点（渲染时剥离——该注释是给 agent/维护者看的元信息，
# 不是 subagent 执行内容，不应出现在最终 prompt）
FILL_MARKER = "> **渲染步骤"

# 任务名 → 渲染配置
TASKS = {
    "task-punctuate": {
        "skill": "reflow-redstone",
        "template": "task-punctuate.md",
        "role": "补标点",
        "format_section": "r01_results/chunk_<k>.txt（补标点块）",
        "inputs": ["reflow/r01_normalized/chunk_<k>.txt"],
        "output": "reflow/r01_results/chunk_<k>.txt",
        "prior": ["breaks", "terms"],
    },
    "task-translate": {
        "skill": "reflow-redstone",
        "template": "task-translate.md",
        "role": "整段翻译",
        "format_section": "r02_results/chunk_<k>.txt（翻译块）",
        "inputs": ["reflow/r01_results/chunk_<k>.txt"],
        "output": "reflow/r02_results/chunk_<k>.txt",
        "prior": ["humanizer", "terms"],
    },
    "task-split": {
        "skill": "reflow-redstone",
        "template": "task-split.md",
        "role": "分句",
        "format_section": "r03_plan.md（## S<n> 整句分组格式；r03_results/chunk_<k>.txt 同此格式）",
        "inputs": ["reflow/r03_normalized_1/chunk_<k>.txt", "reflow/r03_normalized_2/chunk_<k>.txt"],
        "output": "reflow/r03_results/chunk_<k>.txt",
        "prior": ["terms"],
    },
}


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def extract_breaks(breaks_path):
    """从 r01_breaks.md 提取空隙点清单（前/后 cue + 强制 + 复核结论），供补标点先验知识。"""
    text = read(breaks_path)
    if "## 断句点清单" not in text:
        return "（r01_breaks.md 无断句点清单）"
    body = text.split("## 断句点清单", 1)[1]
    blocks = re.split(r"(?m)^### ", body)
    items = []
    for blk in blocks:
        if not blk.strip():
            continue
        lines = blk.splitlines()
        title = lines[0].strip()
        pre = nxt = force = concl = ""
        for ln in lines[1:]:
            if ln.startswith("- 前 cue"):
                pre = ln.replace("- 前 cue", "").strip()
            elif ln.startswith("- 后 cue"):
                nxt = ln.replace("- 后 cue", "").strip()
            elif ln.startswith("- 强制"):
                force = ln.split(":", 1)[1].strip()
            elif "复核结论**:" in ln:
                concl = ln.split("复核结论**:", 1)[1].strip()
        line = f"- 空隙点 {title}"
        if pre:
            line += f"；前 {pre}"
        if nxt:
            line += f"；后 {nxt}"
        if force:
            line += f"；{force}"
        if concl:
            line += f"\n  - 复核结论：{concl}"
        items.append(line)
    return "\n".join(items)


def collect_priors(cfg, video_dir, chunk, prior_files):
    """按任务配置注入先验知识。确定性部分（breaks/humanizer/terms）脚本直读；--prior-file 追加。"""
    parts = []
    video_name = os.path.basename(os.path.normpath(video_dir))

    if "breaks" in cfg["prior"]:
        breaks_path = os.path.join(video_dir, "reflow", "r01_breaks.md")
        if os.path.exists(breaks_path):
            parts.append(
                "### 空隙断句标记（r01_breaks 复核结果，补标点强制断句依据）\n\n"
                + extract_breaks(breaks_path)
            )
        else:
            parts.append("### 空隙断句标记\n\n（未找到 r01_breaks.md）")

    if "humanizer" in cfg["prior"]:
        inject_path = os.path.join(SKILLS_DIR, cfg["skill"], "humanizer-inject.md")
        if os.path.exists(inject_path):
            parts.append("### 去翻译腔（humanizer 注入版，风格参照）\n\n" + read(inject_path))

    if "terms" in cfg["prior"]:
        terms_path = os.path.join(video_dir, "02_terms.md")
        if os.path.exists(terms_path):
            parts.append(
                "### 术语表（本视频已确认译名，翻译必须严格使用；分句只许切不许译，"
                "遇未收录词按 [待审核: 原词] 标注）\n\n" + read(terms_path)
            )
        else:
            parts.append("### 术语表\n\n（未找到 02_terms.md）")

    for pf in prior_files:
        parts.append("### 本块特殊说明（主会话复核结论）\n\n" + read(pf))

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
    """生成 `## 本块数据`：输入数据文件引用（相对 Project_Main）+ 前后块衔接 + 输出路径。"""
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
        # 衔接参考指向本任务第一个输入的目录（如 split → r03_normalized_1、translate → r01_results）
        ctx_template = cfg["inputs"][0].replace("<k>", "{k:03d}")
        prev_txt = f"前块 `_work/{video_name}/{ctx_template.format(k=prev_k)}`（仅语境）" if prev_k else "无（首块）"
        next_txt = f"后块 `_work/{video_name}/{ctx_template.format(k=next_k)}`（仅语境）" if next_k else "无（末块）"
        lines.append(f"- 衔接参考（只读）：{prev_txt}／{next_txt}")
    out_path = cfg["output"].replace("<k>", f"{chunk:03d}")
    lines.append(f"- 输出文件（写入）：`_work/{video_name}/{out_path}`（目录已存在，直接新建）")
    lines.append("")
    lines.append("只读上述数据文件，写后报告 `已写入 " + ck + ".txt`")
    return "\n".join(lines)


def render(task, video_dir, chunk, prior_files, chunks_dir):
    cfg = TASKS[task]
    video_name = os.path.basename(os.path.normpath(video_dir))

    # 1. 模板正文（剥离「主 agent 填充说明」注释）
    template_path = os.path.join(SKILLS_DIR, cfg["skill"], cfg["template"])
    text = read(template_path)
    if FILL_MARKER in text:
        text = text.split(FILL_MARKER)[0].rstrip()
    # 2. 占位替换（模板正文零改动，仅正则替换）
    text = text.replace("<视频名>", video_name)
    text = text.replace("chunk_<k>", f"chunk_{chunk:03d}")
    text = text.replace("<k>", f"{chunk:03d}")

    # 3. 纪律母版（单一权威 _discipline.md，TASK_ROLE 按任务替换）
    #    剥离维护性头部（文件标题 + 说明行，到首个 "## " section 标题之前）——那部分给脚本维护者看，
    #    不注入 subagent 提示词；正文 5 类纪律 + 结果格式契约说明原样注入。
    discipline = read(DISCIPLINE_PATH)
    discipline = discipline[discipline.find("## "):].replace("{TASK_ROLE}", cfg["role"])

    # 4. 产物格式约定（subagent 唯一允许的外部读取）
    fmt_section = cfg["format_section"].replace("<k>", f"{chunk:03d}")
    fmt_block = (
        f"> **产物格式约定**（唯一允许的外部读取）：见 `docs/PRODUCT_FORMATS.md` 的 `{fmt_section}` 节"
    )

    # 5. 先验知识
    priors = collect_priors(cfg, video_dir, chunk, prior_files)

    # 6. 本块数据
    data = collect_data(cfg, video_dir, chunk, chunks_dir)

    out = (
        f"{text}\n\n---\n\n## 纪律母版（执行型 subagent 全局纪律，必须遵守）\n\n{discipline}\n\n"
        f"---\n\n{fmt_block}\n\n---\n\n## 先验知识\n\n{priors}\n\n"
        f"---\n\n## 本块数据\n\n{data}\n"
    )

    prompts_dir = os.path.join(video_dir, "prompts")
    os.makedirs(prompts_dir, exist_ok=True)
    out_path = os.path.join(prompts_dir, f"{task}-chunk_{chunk:03d}.txt")
    write(out_path, out)
    return out_path


def main():
    ap = argparse.ArgumentParser(description="渲染 subagent prompt 到 _work/<视频名>/prompts/")
    ap.add_argument("task", choices=sorted(TASKS.keys()), help="任务模板名")
    ap.add_argument("--video", required=True, help="视频工作目录（相对 Project_Main，如 _work/<视频名>）")
    ap.add_argument("--chunk", type=int, help="块号（1 起）")
    ap.add_argument("--all", action="store_true", help="渲染全部块")
    ap.add_argument("--prior-file", action="append", default=[], help="额外先验知识文件（可多次，追加到 ## 先验知识）")
    ap.add_argument("--chunks-dir", default=None, help="chunks 目录（默认 <video>/reflow/chunks）")
    args = ap.parse_args()

    video_dir = os.path.join(PROJECT_ROOT, args.video) if not os.path.isabs(args.video) else args.video
    chunks_dir = args.chunks_dir or os.path.join(video_dir, "reflow", "chunks")

    if args.all:
        nums = list_chunks(chunks_dir)
        if not nums:
            print("错误：--all 需要 chunks 目录存在（或用 --chunks-dir 指定）", file=sys.stderr)
            sys.exit(1)
        for k in nums:
            print(f"生成 {render(args.task, video_dir, k, args.prior_file, chunks_dir)}")
    else:
        if not args.chunk:
            ap.error("需指定 --chunk <k> 或 --all")
        print(f"生成 {render(args.task, video_dir, args.chunk, args.prior_file, chunks_dir)}")


if __name__ == "__main__":
    main()
