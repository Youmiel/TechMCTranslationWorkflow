# -*- coding: utf-8 -*-
"""通用文本合并脚本（A 模式：全自动拼接 + 异常清单）——替代主 Agent 手工读头尾组装。

设计（通用文本分块格式，见 docs/PRODUCT_FORMATS.md「通用文本分块」）：
- 输入：text_chunk.py 的输出目录（chunk_*.txt 含块头元数据）+ subagent 结果目录（chunk_<k>.txt）
- 默认全自动：按块序读各块结果，归位拼接成完整产物，主 Agent 零读取
- 异常时：把【异常块的头尾衔接窗口】导出到报告，主 Agent 只读报告即可决策（A 模式）
- 拼接规则：
  - text 类型：同「组」内多片按片号无缝拼接（不留空行）；不同组之间空行分隔
  - srt 类型：按块序 + 全局段号重排；检查相邻段 cue 重叠 / 缺口（[Music] 空 cue 允许）/ CARRY 结转

用法（命令根 = Project_Main/）:
  python scripts/text_merge.py <chunks_dir> <results_dir> --out <merged> [--report <report.md>] [--window N]
  chunks_dir  = text_chunk.py --out 目录
  results_dir = subagent 结果目录（merge→_merge_results/、translate→_trans_results/ 等）
  --report    = 异常清单 + 异常块头尾窗口（默认 <out>.report.md）
  --window    = 异常块头尾窗口行数（默认 3，仅导出异常块的 OWNED 头 N 行 / 尾 N 行）

输出:
  <merged>            合并后的完整产物
  <report>.md         异常清单（正常则为「无异常」）；异常块附头尾窗口供 Agent 决策
"""
import argparse
import os
import re
import sys
from collections import OrderedDict

sys.stdout.reconfigure(encoding="utf-8")

from srt_reflow_common import wrap_text, collect_chunk_files

CHUNK_HEAD = re.compile(r"^# CHUNK (\d+)/(\d+)\s+SRC: (.+?)\s+TYPE: (srt|text)\s+UNIT: (.+?)\s+OWN: (.+?)\s+CTX: (.+?)$")
SECTION_LINE = re.compile(r"^## (BEFORE|OWNED|AFTER)")
SEG_ROW = re.compile(r"^(\d+)\|c(\d+)(?:-c(\d+))?([~]?)\|(.+)$")   # srt 段行：段号|cue范围|文本
TEXT_ROW = re.compile(r"^(.+?)\t(.+)$")                              # text 行：组-片\t文本


def parse_chunk_head(path):
    """读块文件头，返回 dict：k/total/type/unit/owned（OWNED 单元列表，每单元 = (label, text 多行)）。"""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    head = None
    owned_blocks = []
    ctx_blocks = []
    cur = None      # 当前收集的单元（None=未开始）
    section = None  # 'owned' | 'ctx'
    for ln in text.split("\n"):
        m = CHUNK_HEAD.match(ln)
        if m:
            head = {"k": int(m.group(1)), "total": int(m.group(2)), "src": m.group(3),
                    "type": m.group(4), "unit": m.group(5), "owned": m.group(6),
                    "ctx": m.group(7)}
            continue
        m2 = SECTION_LINE.match(ln)
        if m2:
            section = "owned" if m2.group(1) == "OWNED" else "ctx"
            cur = None
            continue
        if section is None:
            continue
        if ln.strip() == "":
            # 空行 = 单元结束
            if cur is not None:
                (owned_blocks if section == "owned" else ctx_blocks).append(cur)
                cur = None
            continue
        if cur is None:
            cur = [ln]
        else:
            cur.append(ln)
    if cur is not None:
        (owned_blocks if section == "owned" else ctx_blocks).append(cur)
    if head is None:
        sys.exit("块文件无有效块头（需 text_chunk.py 生成）：%s" % path)
    head["owned"] = owned_blocks
    head["ctx"] = ctx_blocks
    return head


def read_results(results_dir, total):
    """读各块结果文件，返回 {k: [单元,...]}；每单元 = [多行文本]；缺块记 None。
    srt 结果每行一个段（无空行分隔），text 结果单元间空行分隔。"""
    out = {}
    for k in range(1, total + 1):
        p = os.path.join(results_dir, "chunk_%03d.txt" % k)
        if not os.path.exists(p):
            out[k] = None
            continue
        raw = open(p, encoding="utf-8").read()
        if "\n\n" in raw:
            blocks = [b.split("\n") for b in raw.split("\n\n")]
        else:
            blocks = [[l] for l in raw.split("\n")]
        out[k] = [b for b in blocks if any(l.strip() for l in b)]
    return out


def _split_label(row_lines):
    """从单元首行解析 label（组-片）与剩余文本。返回 (label, 内容文本 多行) 或 (None, 原样)。"""
    first = row_lines[0]
    m = TEXT_ROW.match(first)
    if m:
        label = m.group(1)
        body = [m.group(2)] + row_lines[1:]
        return label, "\n".join(body)
    return None, "\n".join(row_lines)


def _parse_label(label, k):
    """label → (gid, part)。支持「块0-片2」「块1」「S19+20-片2」「S19+20」；无法解析回退组=label。"""
    if "-片" in label:
        gid, part_s = label.rsplit("-片", 1)
        try:
            return gid, int(part_s)
        except ValueError:
            return label, 1
    return label, 1


def merge_text(chunks, results, report):
    """text 类型：按「组-片」归位拼接；同组多片无缝拼接（中文空连接/英文空格）、组间空行。
    返回 (合并文本, 异常清单[(块号或0, 消息)])。"""
    groups = OrderedDict()
    issues = []

    # 先校验块齐全
    for k in sorted(results):
        if results[k] is None:
            issues.append((k, "缺块: chunk_%03d 无结果文件" % k))
            continue
        rows = results[k]
        head = chunks[k]
        owned = head["owned"]
        if len(rows) != len(owned):
            issues.append((k, "块 %d 结果单元数(%d) ≠ OWNED 单元数(%d)——subagent 未按每单元一条产出，需人工核对；"
                               "若输入为 reflow 整段产物（r01/r02 整段文字、r03 `## S<n>` 结构）或 term，不走 text_merge，勿用本脚本" %
                           (k, len(rows), len(owned))))
            continue
        for own, res in zip(owned, rows):
            o_label, _ = _split_label(own)
            r_label, r_text = _split_label(res)
            label = r_label or o_label or ("块%d-片?" % k)
            gid, part = _parse_label(label, k)
            if gid not in groups:
                groups[gid] = {}
            if part in groups[gid]:
                issues.append((k, "重复产出: %s-片%d 被多个块/行覆盖（保留先到）" % (gid, part)))
            else:
                groups[gid][part] = r_text

    # 按块头 OWNED 顺序校准组序
    ordered_gids = []
    for k in sorted(chunks):
        for own in chunks[k]["owned"]:
            o_label, _ = _split_label(own)
            if o_label:
                gid, _ = _parse_label(o_label, k)
                if gid not in ordered_gids:
                    ordered_gids.append(gid)

    # 组内片号连续性检查
    for gid in groups:
        parts = sorted(groups[gid])
        if parts != list(range(1, len(parts) + 1)):
            issues.append((0, "组 %s 片号不连续: %s（合并仍按序拼接，缺口需人工补）" % (gid, parts)))

    # 拼接：同组片按序拼接（判断中英以组首片为准）；组间空行
    def join_parts(texts):
        first = texts[0] if texts else ""
        if re.search(r"[\u4e00-\u9fff]", first):
            return "".join(texts)          # 中文：空连接（句间不加空格）
        return " ".join(texts)             # 英文：空格连接

    merged_blocks = []
    for gid in ordered_gids:
        if gid in groups:
            seg = join_parts([groups[gid][p] for p in sorted(groups[gid])])
            merged_blocks.append(seg)
    merged = "\n\n".join(merged_blocks)
    return merged, issues


def merge_srt(chunks, results, report):
    """srt 类型：按块序读「段号|cue范围|文本」行，全局重排段号 + 检查重叠/gap/CARRY。"""
    rows = []  # (block_k, seg_no, cue_start, cue_end, est, text, carry)
    issues = []
    for k in sorted(results):
        if results[k] is None:
            issues.append((k, "缺块: chunk_%03d 无结果文件" % k))
            continue
        for unit in results[k]:
            ln = unit[0] if unit else ""
            m = SEG_ROW.match(ln)
            if not m:
                # CARRY 标记单独识别
                if ln.startswith("CARRY:"):
                    rows.append((k, 0, None, None, "", "", ln))
                else:
                    issues.append((k, "块 %d 无法解析的结果行: %r" % (k, ln)))
                continue
            seg = int(m.group(1))
            cs = int(m.group(2))
            ce = int(m.group(3)) if m.group(3) else cs
            est = m.group(4)
            text = m.group(5)
            rows.append((k, seg, cs, ce, est, text, ""))

    # 按块序 + 块内段号排序
    rows.sort(key=lambda r: (r[0], r[1]))
    # 全局重编号（跳过 CARRY 行）
    merged_lines = []
    seq = 0
    prev_end = None  # 上一段 end cue
    prev_k = None
    for k, seg, cs, ce, est, text, carry in rows:
        if carry:
            merged_lines.append(carry)
            continue
        seq += 1
        if prev_end is not None and cs < prev_end:
            issues.append((k, "块 %d 段 %d 与上一段 cue 重叠（start c%d < 前 end c%d）" % (k, seg, cs, prev_end)))
        if prev_end is not None and cs > prev_end + 1:
            issues.append((k, "块 %d 段 %d 存在 cue 缺口（start c%d > 前 end c%d+1）——查是否为 [Music] 等空 cue，是则并入相邻段" %
                           (k, seg, cs, prev_end)))
        prev_end = ce
        prev_k = k
        rng = ("c%d-c%d" % (cs, ce)) if ce != cs else ("c%d" % cs)
        merged_lines.append("%d|%s%s|%s" % (seq, rng, est, text))

    return "\n".join(merged_lines), issues


def main():
    ap = argparse.ArgumentParser(description="通用文本合并（A 模式：全自动拼接 + 异常清单；异常块导出头尾窗口）")
    ap.add_argument("chunks_dir", help="text_chunk.py 输出目录（chunk_*.txt 含块头）")
    ap.add_argument("results_dir", help="subagent 结果目录（chunk_<k>.txt）")
    ap.add_argument("--out", required=True, help="合并产物路径")
    ap.add_argument("--report", default=None, help="异常清单报告路径（默认 <out>.report.md）")
    ap.add_argument("--window", type=int, default=3, help="异常块头尾窗口行数（默认 3，仅导出异常块）")
    ap.add_argument("--wrap", type=int, default=None,
                    help="合并输出就近折行宽度（默认不折行）；text 类型整段产物（r01/r02 全文等）建议 --wrap 1000——"
                         "每 ~N 字符折行（不拆英文词、中文按字符），显示性换行非语义分行；"
                         "结构化产物（r03_plan.md 单行值）禁用")
    args = ap.parse_args()

    report_path = args.report or (args.out + ".report.md")
    window = max(1, args.window)

    # 收集所有块文件，按序号排序
    chunk_files = collect_chunk_files(args.chunks_dir)
    if not chunk_files:
        sys.exit("chunks_dir 下未找到 chunk_*.txt（需 text_chunk.py 生成）")
    total = max(chunk_files)
    chunks = {k: parse_chunk_head(p) for k, p in chunk_files.items()}
    results = read_results(args.results_dir, total)

    # 统一类型（从块头取；若不一致以多数为准）
    types = {chunks[k]["type"] for k in chunks}
    type_ = "text" if len(types) > 1 else next(iter(types))

    if type_ == "srt":
        merged, issues = merge_srt(chunks, results, report_path)
    else:
        merged, issues = merge_text(chunks, results, report_path)

    # 折行（text 类型 + --wrap 开启；结构化产物如 r03_plan.md 禁用）
    if args.wrap and type_ == "text" and merged:
        merged = wrap_text(merged, args.wrap)

    # 写合并产物
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(merged + "\n" if merged else "")

    # 异常清单 + 异常块头尾窗口（只导出涉及异常的块，控制报告体积）
    report_lines = ["# 合并报告 — %s" % os.path.basename(args.out),
                    "- 块数: %d / 类型: %s" % (total, type_),
                    "- 合并产物: %s" % os.path.abspath(args.out)]
    if not issues:
        report_lines.append("")
        report_lines.append("## 结论: 无异常（全自动合并，主 Agent 无需读取）")
    else:
        report_lines.append("")
        report_lines.append("## 异常清单（%d 条，需 Agent 决策）" % len(issues))
        for i, (bk, msg) in enumerate(issues, 1):
            report_lines.append("%d. %s" % (i, msg))
        # 异常块头尾窗口（只导出有异常关联的块；bk=0 的组级异常导出全部组相关块）
        bad_ks = sorted({bk for bk, _ in issues if bk > 0})
        report_lines.append("")
        report_lines.append("## 异常块头尾窗口（--window %d，仅异常块，仅供核对衔接，勿整读）" % window)
        for k in bad_ks:
            head = chunks[k]
            owned = head["owned"]
            res = results.get(k)
            labels = []
            for u in owned:
                m = TEXT_ROW.match(u[0]) if u else None
                labels.append(m.group(1) if m else u[0][:20] if u else "?")
            report_lines.append("### chunk_%03d（负责 %s）" % (k, ", ".join(labels)))
            report_lines.append("OWNED 头 %d 单元:" % min(window, len(owned)))
            for u in owned[:window]:
                report_lines.append("  " + (u[0][:120] if u else "?"))
            if len(owned) > 2 * window:
                report_lines.append("  …（中间 %d 单元省略）…" % (len(owned) - 2 * window))
            report_lines.append("OWNED 尾 %d 单元:" % min(window, len(owned)))
            for u in owned[-window:]:
                report_lines.append("  " + (u[0][:120] if u else "?"))
            if res:
                report_lines.append("结果头 %d 单元:" % min(window, len(res)))
                for u in res[:window]:
                    report_lines.append("  " + (u[0][:120] if u else "?"))
                report_lines.append("结果尾 %d 单元:" % min(window, len(res)))
                for u in res[-window:]:
                    report_lines.append("  " + (u[0][:120] if u else "?"))
        if not bad_ks:
            report_lines.append("（无单块异常；组级异常见上方清单，缺块/缺片按清单提示补齐后重跑）")
    with open(report_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(report_lines) + "\n")

    print("合并产物: %s（%d 字符）" % (os.path.abspath(args.out), len(merged)))
    print("合并报告: %s" % os.path.abspath(report_path))
    if issues:
        print("⚠️ 异常 %d 条（见报告；主 Agent 只需读异常块头尾窗口）" % len(issues))
    else:
        print("✅ 无异常，全自动合并完成")


if __name__ == "__main__":
    main()
