# -*- coding: utf-8 -*-
"""脚本断句填回（机械断句路径，2026-08-21）：由「匹配文件 + EN 预分句 + ZH 模板骨架」机械生成 r03_results。

reflow 工作流（reflow-redstone）步骤 5 的「脚本断句」平行路径（LLM 只做句子匹配，断句/填回全机械）：
- **匹配文件**：`reflow/r03_matches/chunk_<k>.txt`（LLM 句子匹配 subagent 产物）——每行一个整句，
  左 = 合并成整句的 ZH 句 Z 组、右 = 对应 EN 句 E 组（组内 `+` 连接）：
      `Z5+Z6+Z7+Z8 = E5+E6+E7+E8`
- **EN 预分句**：`reflow/r03_normalized_1/chunk_<k>.txt`（presplit 产物，E1..En）
- **ZH 模板骨架**：`reflow/r03_normalized_2/chunk_<k>.txt`（presplit 产物，Z 句 + 子句段预填）

生成逻辑（零 LLM、全确定性）：
- **子单元 = 复用模板骨架的子句段**（presplit 机械断句结果：只在标点处切、宽度 ≤ hard_max、
  段拼接 == Z 原文 == r02——忠实铁律由结构保证）；单段 Z 句（模板 1:1）整句成单元
- **EN 整句 = 匹配的 E 组按号顺序拼接**；**子单元 EN = 按 ZH 子单元宽度比例机械切 EN 整句**
  （词边界就近切，互斥拼接 == 整句，check-r03 ② 可过；语义对齐是近似的、须人工核对）
- **关系 = 1:1（单子单元）/ 1:n（多子单元）**，S 号块内从 1 连续
- **漏句留空**（本脚本核心收益）：匹配未覆盖的 Z 句 / E 句**不静默消失**，产物写 `> ⚠️` 标记
  + 主会话报告（脚本断句允许不完整，缺处人工/LLM 兜底；对比 task-split 直接写 r03 漏句会消失）
- 每块独立处理、互不影响；对整个输入目录一次跑完（命令只运行一次）
- 产物契约 r03（`## S<n>` 格式）不变，与 task-split 路径产物同格式、同消费端（check-r03/回填）

用法（命令根 = Project_Main/）：
  python scripts/srt_reflow_build_r03.py reflow/r03_matches/ reflow/r03_normalized_1/ reflow/r03_normalized_2/ -o reflow/r03_results/
退出码：0 = 全部块生成（含漏句标记，属正常）；1 = 输入目录无块 / 匹配文件解析失败。
"""
import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

from srt_reflow_common import collect_chunk_files, text_width

# 匹配文件每行格式：`Z5+Z6+Z7+Z8 = E5+E6+E7+E8`（左 Z 组 / 右 E 组，组内 `+` 连接、每组元素带 Z/E 前缀）
MATCH_RE = re.compile(r"^\s*([ZE][\d+]*(?:\+[ZE][\d+]*)*)\s*=\s*([ZE][\d+]*(?:\+[ZE][\d+]*)*)\s*$")
# 模板骨架：整句标题 `## S?_Z<n>（默认 E<n>，切 <m> 段）`；子句段标题 `### S?_Z<n><a>`
Z_BLOCK_RE = re.compile(r"^## S\?_Z(\d+)")
Z_SUB_RE = re.compile(r"^### S\?_Z\d+[a-z]")
# EN 预分句：`- E<n>: <文本>`（句内显示折行续行顶格，须并入当前句）
EN_LINE_RE = re.compile(r"^- E(\d+):\s?(.*)$")
# r03 产物留空标记（漏句/漏 EN），主会话/人工按 `> ⚠️` 定位
MISS_TAG = "> ⚠️ 脚本断句·未匹配"


def parse_en(text):
    """EN 预分句（r03_normalized_1）→ {e号: 句文本}；显示折行（续行顶格、非 `- E` 开头）并入当前句。"""
    out = {}
    cur = None
    for ln in text.splitlines():
        m = EN_LINE_RE.match(ln)
        if m:
            cur = int(m.group(1))
            out[cur] = m.group(2)
        elif cur is not None and ln.strip():
            out[cur] += ln.strip()
    return out


def parse_template(text):
    """ZH 模板骨架（r03_normalized_2）→ 有序 [{z, text, subs}]（subs = 子句段文本列表）。

    - 单段 Z 句（模板 1:1，无 `###` 子句段）→ subs = [整句]（子单元即整句）
    - 多段 Z 句（模板 1:n）→ subs = 各 `### S?_Z<n><a>` 的 ZH 段（脚本已切好、复用）
    - `- EN: <待填>` / `- 关系:` / `> ` 注释行忽略（填空是脚本职责）
    """
    blocks = []
    cur = None
    in_sub = False
    for ln in text.splitlines():
        m = Z_BLOCK_RE.match(ln)
        if m:
            cur = {"z": int(m.group(1)), "text": None, "subs": []}
            blocks.append(cur)
            in_sub = False
            continue
        if cur is None:
            continue
        if Z_SUB_RE.match(ln):
            in_sub = True
            cur["subs"].append("")
            continue
        m = re.match(r"^- ZH:\s?(.*)$", ln)
        if m:
            if in_sub:
                cur["subs"][-1] = m.group(1)
            elif cur["text"] is None:
                cur["text"] = m.group(1)
    # 单段兜底：无 `###` 子句段时 subs = [整句]
    for b in blocks:
        if not b["subs"] and b["text"] is not None:
            b["subs"] = [b["text"]]
    return blocks


def _parse_group(s, prefix):
    """从组串提取号列表（`Z5+Z6+Z7+Z8` → [5,6,7,8]；`E5+E6` → [5,6]）。"""
    return [int(x) for x in re.findall(r"%s(\d+)" % prefix, s)]


def parse_matches(text):
    """匹配文件 → 有序 [(Z组, E组)]（组内为号列表）；跳过空行/`#` 注释。非法行收集为解析问题。"""
    out = []
    problems = []
    for lineno, ln in enumerate(text.splitlines(), 1):
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        m = MATCH_RE.match(s)
        if not m:
            problems.append(f"行{lineno}: 无法解析「{ln.strip()}」（应为 `Z5+Z6 = E5+E6`）")
            continue
        zg = _parse_group(m.group(1), "Z")
        eg = _parse_group(m.group(2), "E")
        if not zg or not eg:
            problems.append(f"行{lineno}: 组内无有效 Z/E 号「{ln.strip()}」")
            continue
        out.append((zg, eg))
    return out, problems


def split_en_by_weights(en_text, weights):
    """按权重（ZH 子单元宽度）比例把 EN 整句切成互斥片段（词边界就近切；每片段至少 1 词）。

    - 保证 "".join(norm(frag)) == norm(en_text)（check-r03 ② 互斥拼接可过）
    - 词数不足时末尾片段留空（宁空不吞词——留空由人工/LLM 定位，不静默消失）
    - 片段只作 cue 锚定参考，不校验宽度；语义对齐是近似的（脚本断句固有局限）
    """
    words = re.findall(r"\S+", en_text)
    n = len(weights)
    if not words:
        return [""] * n
    total_w = sum(weights) or 1
    # 每片段目标词数（按权重比例，向下取整、至少 1）
    target_words = [max(1, len(words) * w / total_w) for w in weights]
    frags = []
    start = 0
    for i in range(n - 1):
        take = int(round(target_words[i]))
        # 至少留 1 词给每个剩余片段（含当前片段自身 ≥1）
        max_take = max(len(words) - start - (n - i - 1), 1)
        take = min(max(take, 1), max_take)
        frags.append(" ".join(words[start:start + take]))
        start += take
    frags.append(" ".join(words[start:]))
    while len(frags) < n:
        frags.append("")
    return frags


def render_r03(matches, zh_map, en_map):
    """按匹配生成 r03 文本（含 `> ⚠️` 漏句/漏 EN 标记）。返回 (文本, 统计 dict)。"""
    lines = [
        "> 脚本断句产物（build-r03 机械生成）：子单元复用 presplit 模板骨架、EN 按宽度比例机械切分，",
        "> 中英对应以 r03_matches 匹配文件为准（须人工核对；未匹配处见下方 `> ⚠️` 标记）",
    ]
    stats = {"s": 0, "miss_z": 0, "miss_e": 0}
    s_num = 0
    for zg, eg in sorted(matches, key=lambda m: min(m[0])):
        zs = sorted(zg)
        es = sorted(eg)
        # ZH 整句 = 各 Z 句文本按号拼接；子单元 = 复用模板子句段（按 Z 号顺序展开）
        zh_parts, subs = [], []
        for z in zs:
            if z not in zh_map:
                continue  # 匹配引用不存在的 Z（解析问题，前面已报）
            zh_parts.append(zh_map[z]["text"])
            subs.extend(zh_map[z]["subs"])
        zh_full = "".join(zh_parts)
        # EN 整句 = E 组按号拼接（空格连接）；子单元 EN 机械切分
        en_parts = [en_map[e] for e in es if e in en_map]
        en_full = " ".join(en_parts)
        missing_en = [e for e in es if e not in en_map]
        for e in missing_en:
            stats["miss_e"] += 1
            lines.append(f"{MISS_TAG} E{e}: 匹配引用的 E 号在预分句缺失")
        if not subs:
            continue
        en_subs = split_en_by_weights(en_full, [text_width(s) for s in subs])
        s_num += 1
        rel = "1:1" if len(subs) == 1 else "1:n"
        lines.append(f"## S{s_num}")
        lines.append(f"- EN: {en_full}")
        lines.append(f"- ZH: {zh_full}")
        lines.append(f"- 关系: {rel}")
        # 1:1（单子单元）无 `###` 子单元（规范 r03 格式）；1:n 生成子单元
        if len(subs) > 1:
            widths = " / ".join("%.1f" % text_width(s) for s in subs)
            lines.append(f"> 子单元宽（视觉）: {widths}")
            for i, (zu, eu) in enumerate(zip(subs, en_subs), 1):
                lines.append(f"### S{s_num}{chr(96 + i)}")
                lines.append(f"- EN: {eu}")
                lines.append(f"- ZH: {zu}")
        lines.append("")
    # 漏句留空：模板有、匹配未覆盖的 Z 句 → 标记（不静默消失）
    matched_z = {z for zg, _ in matches for z in zg}
    for z in sorted(zh_map):
        if z not in matched_z:
            stats["miss_z"] += 1
            lines.append(f"{MISS_TAG} Z{z}: {zh_map[z]['text']}")
    stats["s"] = s_num
    text = "\n".join(lines).rstrip() + "\n"
    return text, stats


def build_block(match_text, en_text, zh_text):
    """单块：匹配 + EN 预分句 + 模板骨架 → (r03 文本, 统计, 解析问题列表)。"""
    zh_blocks = parse_template(zh_text)
    zh_map = {b["z"]: b for b in zh_blocks}
    en_map = parse_en(en_text)
    matches, problems = parse_matches(match_text)
    # 校验匹配引用的 Z 是否在模板（不存在 = LLM 写错号）
    for zg, _ in matches:
        for z in zg:
            if z not in zh_map:
                problems.append(f"匹配引用 Z{z} 不在模板骨架（写错号？）")
    text, stats = render_r03(matches, zh_map, en_map)
    return text, stats, problems


def main():
    ap = argparse.ArgumentParser(
        description="脚本断句填回：匹配文件 + EN 预分句 + ZH 模板骨架 → r03_results（机械断句、漏句留空）"
    )
    ap.add_argument("match_dir", help="匹配文件目录：reflow/r03_matches/（LLM 句子匹配产物）")
    ap.add_argument("en_dir", help="EN 预分句目录：reflow/r03_normalized_1/")
    ap.add_argument("zh_dir", help="ZH 模板骨架目录：reflow/r03_normalized_2/")
    ap.add_argument("-o", "--out", required=True, help="输出目录：reflow/r03_results/")
    ap.add_argument("--verbose", action="store_true", help="展开打印每块统计")
    args = ap.parse_args()

    match_blocks = collect_chunk_files(args.match_dir)
    en_blocks = collect_chunk_files(args.en_dir)
    zh_blocks = collect_chunk_files(args.zh_dir)
    if not match_blocks:
        sys.exit("❌ 匹配目录无块文件")
    os.makedirs(args.out, exist_ok=True)

    keys = sorted(match_blocks)
    tot = {"s": 0, "miss_z": 0, "miss_e": 0}
    exit_code = 0
    for k in keys:
        with open(match_blocks[k], encoding="utf-8") as fh:
            match_text = fh.read()
        en_text = ""
        if k in en_blocks:
            with open(en_blocks[k], encoding="utf-8") as fh:
                en_text = fh.read()
        zh_text = ""
        if k in zh_blocks:
            with open(zh_blocks[k], encoding="utf-8") as fh:
                zh_text = fh.read()
        text, stats, problems = build_block(match_text, en_text, zh_text)
        out_path = os.path.join(args.out, "chunk_%03d.txt" % k)
        with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        tot["s"] += stats["s"]
        tot["miss_z"] += stats["miss_z"]
        tot["miss_e"] += stats["miss_e"]
        if problems:
            exit_code = 1
            print(f"⚠️ chunk_{k:03d} 解析问题（需人工/LLM 核对）:")
            for p in problems:
                print(f"   {p}")
        if args.verbose:
            print(f"   chunk_{k:03d}: {stats['s']} 整句 / 未匹配 Z {stats['miss_z']} / 未匹配 E {stats['miss_e']}")
    print(f"✅ 脚本断句完成：{len(keys)} 块 / {tot['s']} 整句 → {args.out}；未匹配 Z {tot['miss_z']} / 未匹配 E {tot['miss_e']}")
    if tot["miss_z"] or tot["miss_e"]:
        print("   漏句已留空（`> ⚠️` 标记），需人工核对或补派 LLM 语义分句")
    return exit_code


if __name__ == "__main__":
    main()
