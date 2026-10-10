# -*- coding: utf-8 -*-
"""字幕段间小空隙填充：把相邻段的间隙「覆盖」掉，消除闪烁观感

为什么需要
    相邻两条字幕之间哪怕只有几百毫秒的空隙，播放时也会**闪一下**（前条消失、后条未出现）。
    由语音实测切出的时间戳天然会有这种小空隙（词间真实停顿、切点落在词边界），
    而观感上更好的做法是：**空隙小于阈值时，把前条延到后条起点**（两条首尾相接）。

适用对象
    任意 SRT（单语 / 双语均可）——只改时间行的 `end`，不动编号与文本。
    双语稿（中文行 + 英文行）时间戳本就同行共享，无需特殊处理。

作用位置
    vocalign 的**输出后处理**（回填产出 r04 之后、阶段五人工审核之前）。做成独立脚本
    而非回填内一步，是为了让“时间取语音实测”与“观感后处理”产物分离、可对照。

⚠️ 这是**主动偏离语音实测时间**的例外
    填充后的 `end` 不再对应任何语音边界（多出的是静默段）。故：
    - 默认**不原地覆盖**（产 `<名>.filled.srt`，保留原始产物供对照）
    - 只填**小于阈值**的空隙；≥ 阈值的保留（那是真实停顿或剪辑跳转，不该覆盖）

用法（命令根 = Project_Main/）
    python scripts/srt_fill_gaps.py <字幕.srt>                       # → <同目录>/<名>.filled.srt
    python scripts/srt_fill_gaps.py <字幕.srt> -o <输出.srt>          # 指定输出
    python scripts/srt_fill_gaps.py <字幕.srt> --in-place            # 原地覆盖（谨慎）
    python scripts/srt_fill_gaps.py <字幕.srt> --max-gap-ms 800      # 自定义阈值
    python scripts/srt_fill_gaps.py <字幕.srt> --expand              # 展开打印每处填充

退出码：0 = 完成（含 0 处填充）；1 = 解析失败或存在时间重叠（倒挂）。
"""
import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

from shared.srt_common import fmt, GAP_FILL_MS

TIME_RE = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})")


def to_ms(g):
    """`HH:MM:SS,mmm` 组 → 毫秒"""
    return ((int(g[0]) * 3600 + int(g[1]) * 60 + int(g[2])) * 1000
            + int(g[3].ljust(3, "0")))


def parse_blocks(text):
    """SRT → [(time_line_idx, start_ms, end_ms, lines)]

    保留原始行（编号 / 文本 / 空行结构），只把时间行视为可改点。
    无时间行的块（缺时间戳）跳过但**不报错**（可能是自制提示块）。
    """
    out = []
    for blk in re.split(r"\n\s*\n", text.strip()):
        if not blk.strip():
            continue
        lines = blk.split("\n")
        ti, m = None, None
        for i, ln in enumerate(lines):
            m = TIME_RE.search(ln)
            if m:
                ti = i
                break
        if ti is None:
            continue
        g = m.groups()
        out.append((ti, to_ms(g[:4]), to_ms(g[4:]), lines))
    return out


def main():
    ap = argparse.ArgumentParser(description="字幕段间小空隙填充（前段 end 延到后段 start）")
    ap.add_argument("srt", help="输入字幕（SRT）")
    ap.add_argument("-o", "--out", default=None,
                    help="输出路径（默认 <输入目录>/<名字>.filled.srt）")
    ap.add_argument("--in-place", action="store_true", help="原地覆盖输入文件（谨慎：原始产物将丢失）")
    ap.add_argument("--max-gap-ms", type=int, default=GAP_FILL_MS,
                    help="空隙填充上限（默认 %d；间隙 ≥ 此值 = 真实停顿，不覆盖）" % GAP_FILL_MS)
    ap.add_argument("--report", default=None, help="报告落盘路径（默认不写）")
    ap.add_argument("--expand", action="store_true", help="展开打印每处填充")
    args = ap.parse_args()

    if not os.path.isfile(args.srt):
        sys.exit("❌ 输入不存在：%s" % args.srt)
    with open(args.srt, encoding="utf-8-sig") as fh:
        text = fh.read()

    blocks = parse_blocks(text)
    if not blocks:
        sys.exit("❌ 未解析到任何带时间行的字幕块：%s" % args.srt)

    fills, overlaps = [], []
    for (ti0, _s0, e0, l0), (ti1, s1, _e1, _l1) in zip(blocks, blocks[1:]):
        gap = s1 - e0
        if gap < 0:
            overlaps.append((s1 - e0, l0[ti0].strip()))
        elif 0 < gap < args.max_gap_ms:
            fills.append((gap, l0[ti0].strip(), e0, s1))
            # 前段 end ← 后段 start：**只换 `-->` 之后的结束时刻**，起始时刻原样保留
            m = TIME_RE.search(l0[ti0])
            l0[ti0] = "%s --> %s" % (l0[ti0][:m.end(4)], fmt(s1))

    out_text = "\n\n".join("\n".join(lns) for _ti, _s, _e, lns in blocks) + "\n"

    if args.in_place:
        out_path = args.srt
    else:
        out_path = args.out or os.path.join(
            os.path.dirname(os.path.abspath(args.srt)),
            os.path.splitext(os.path.basename(args.srt))[0] + ".filled.srt")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    if args.report:
        rd = os.path.dirname(os.path.abspath(args.report))
        if not os.path.isdir(rd):
            print("❌ 报告目录不存在：%s\n   （先建目录，或去掉 --report）" % rd)
            return 1
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(out_text)

    total = sum(g for g, _t, _a, _b in fills)
    print("空隙填充：%d 处 / 合计 %.2fs（阈值 < %dms）→ %s"
          % (len(fills), total / 1000.0, args.max_gap_ms, out_path))
    if overlaps:
        print("⚠️ 时间重叠 %d 处（未处理，请查上游）" % len(overlaps))

    if args.report:
        rp = ["# 段间空隙填充报告", "",
              "- 输入：%s" % args.srt,
              "- 输出：%s" % out_path,
              "- 阈值：间隙 < %dms → 前段 end 延到后段 start" % args.max_gap_ms,
              "- 填充：%d 处 / 合计 %.2fs" % (len(fills), total / 1000.0), ""]
        if fills:
            rp += ["## 填充明细", ""]
            for g, t, a, b in fills[:200]:
                rp.append("- +%dms｜%s：结束 %.3f → %.3f"
                          % (g, t.split("-->")[0].strip(), a / 1000.0, b / 1000.0))
            if len(fills) > 200:
                rp.append("- 共 %d 处，仅列前 200 处" % len(fills))
            rp.append("")
        if overlaps:
            rp += ["## 时间重叠", "",
                   "以下为时间重叠处，本脚本不修（属上游回填问题）。", ""]
            for d, t in overlaps[:200]:
                rp.append("- %dms｜%s" % (d, t))
        with open(args.report, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(rp) + "\n")
        print("报告：%s" % args.report)

    if args.expand:
        for g, t, a, b in fills[:50]:
            print("   +%dms  %.3f → %.3f  %s" % (g, a / 1000.0, b / 1000.0, t))
    return 1 if overlaps else 0


if __name__ == "__main__":
    sys.exit(main())
