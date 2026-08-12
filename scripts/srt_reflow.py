# -*- coding: utf-8 -*-
"""时间轴语义回填（Semantic Timeline Refill）— 回填工作流（reflow-redstone）的确定性时间运算（CLI 入口）

子命令：
  reflow    r03_plan.md + 01_subtitle_asr_fixed.srt -> r04_draft.srt + r04_alerts.md + r03_anchored.jsonl
            整句锚定 -> 单元级 cue 锚定 -> 阅读失配触发中文阅读速度插值（--cjk-speed，倒装/中英时长差）
            -> 分割点就近吸附真实 cue 边界 -> 100ms 取整预测点（兜底）；r04_alerts 含长句碎片检测
  attach-en r04_draft.srt + r03_plan.md -> 双语 SRT（en-zh，英文行 = r03 英文片段）
  check-r03 r03_plan.md + 01 + r02 -> 写时即合规预检（锚定唯一性 / 拆句互斥 / 行宽 ≤20 / ZH 忠实），违规退出码 1
            r03 为目录时走块级：check-r03 r03_results/ 01 r02_results/ --chunks chunks/（锚定缩块内、ZH 忠实缩块内）
  check-duration r04_draft.srt + r03_plan.md -> 回填后时长复核（长句碎片/独立短句/阅读失配），长句碎片退出码 1

用法（命令根 = Project_Main/；输出默认写到输入文件 r03/r04 同目录，与 cwd 无关）：
  python scripts/srt_reflow.py reflow r03_plan.md 01_subtitle_asr_fixed.srt [-o r04_draft.srt] [--snap-ms 300] [--cjk-speed 5]
  python scripts/srt_reflow.py attach-en r04_draft.srt r03_plan.md [-o r04_bilingual.srt]
  python scripts/srt_reflow.py check-r03 r03_plan.md 01_subtitle_asr_fixed.srt r02_translation_zh.txt
  python scripts/srt_reflow.py check-duration r04_draft.srt r03_plan.md [--min-ms 1000] [--cjk-speed 5]

实现拆分：逻辑在 srt_reflow_core/（io/plan/anchor/allocate/alerts/reflow/attach），本文件只做 CLI 分发。
语义判断（分句对应、拆/合、切分位置）由 Agent 写入 r03 方案，脚本只做确定性时间运算。
阈值与 reflow-redstone SKILL 一致：长停顿 >5s / 剪辑跳转 >10s / 超长单元 >15s 或 >2×中位 /
单句时长通常 ≥1s（长句碎片 <1s 须回报 Agent）/ 中文阅读速度 5 字/秒（--cjk-speed）。

多语言扩展（未来，详见 srt_reflow_core/io.py 的 norm/text_width docstring）：
- 核心原则：锚定/时间运算语言无关；语言相关点 = 归一化(norm) + 宽度(text_width) + 断句标点 + 语言顺序
- 短期（已落地）：norm 支持拉丁语系（NFKD 去重音，覆盖 en/fr/de/es 等）；text_width 按 Unicode 块通用（全角/拉丁/数字），不再只认 CJK
- 中期：脚本加 --src-lang/--dst-lang，norm/width/断句标点按语言分流（CJK/西里尔/阿拉伯…）
- 长期：抽独立 langs.py 配置模块供脚本共用；加语言 = 加配置项，时间运算核心零改动
"""
import argparse
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.srt_reflow_core.reflow import reflow
from scripts.srt_reflow_core.attach import attach_en
from scripts.srt_reflow_core.plan import check_r03, check_r03_blocks
from scripts.srt_reflow_core.alerts import check_duration


def main():
    ap = argparse.ArgumentParser(description="时间轴语义回填（reflow/attach-en/check-r03/check-duration）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("reflow")
    p1.add_argument("r03", help="r03_plan.md（回填方案）")
    p1.add_argument("srt", help="01_subtitle_asr_fixed.srt（cue 时间戳）")
    p1.add_argument("-o", dest="out", default=None, help="输出 r04（默认 r03 同目录 r04_draft.srt）")
    p1.add_argument("--alert", dest="alert", default=None, help="告警清单（默认 r03 同目录 r04_alerts.md）")
    p1.add_argument("--anchored", dest="anchored", default=None, help="锚定明细 JSONL（默认 r03 同目录 r03_anchored.jsonl，每行一整句）")
    p1.add_argument("--snap-ms", type=int, default=300, help="分割点吸附真实 cue 边界的最大距离（默认 300ms）")
    p1.add_argument("--cjk-speed", type=float, default=5.0,
                    help="中文阅读速度（字/秒），用于阅读失配检测与插值；0=禁用（默认 5.0）")

    p2 = sub.add_parser("attach-en")
    p2.add_argument("r04", help="r04_draft.srt（回填后单语）")
    p2.add_argument("r03", help="r03_plan.md（英文片段）")
    p2.add_argument("-o", dest="out", default=None, help="输出双语（默认 r04 同目录 r04_bilingual.srt）")

    p3 = sub.add_parser("check-r03", help="r03 写时即合规预检（锚定唯一性/拆句互斥/行宽/ZH忠实/碎片/中英失配预警），硬违规退出码 1；r03 为目录时走块级（r03_results/ + --chunks + r02_results/）")
    p3.add_argument("r03", help="r03_plan.md（整段）或 r03_results 目录（块级）")
    p3.add_argument("srt", help="01_subtitle_asr_fixed.srt（cue 时间戳）")
    p3.add_argument("r02", help="r02_translation_zh.txt（整段基准）或 r02_results 目录（块级基准）")
    p3.add_argument("--chunks", default=None, help="块级模式：chunks 骨架目录（解析块↔cue区间）")
    p3.add_argument("--cjk-speed", type=float, default=5.0,
                    help="中文阅读速度（字/秒），用于碎片预检与中英失配预估；0=禁用两者（默认 5.0）")
    p3.add_argument("--no-frag", action="store_true", help="禁用碎片预检（存疑预警）")
    p3.add_argument("--no-mismatch", action="store_true", help="禁用中英失配预估（存疑预警）")

    p4 = sub.add_parser("check-duration", help="回填后时长复核（长句碎片/独立短句/阅读失配），长句碎片退出码 1")
    p4.add_argument("r04", help="r04_draft.srt（回填后时间轴）")
    p4.add_argument("r03", help="r03_plan.md（回填方案）")
    p4.add_argument("--min-ms", type=int, default=1000, help="长句碎片阈值（默认 1000ms）")
    p4.add_argument("--cjk-speed", type=float, default=5.0, help="中文阅读速度（字/秒），0=禁用（默认 5.0）")
    p4.add_argument("--min-gap-ms", type=int, default=300, help="显著阅读失配最小毫秒数（默认 300ms）")

    args = ap.parse_args()
    if args.cmd == "reflow":
        out = args.out or str(Path(args.r03).parent / "r04_draft.srt")
        alert = args.alert or str(Path(args.r03).parent / "r04_alerts.md")
        anchored = args.anchored or str(Path(args.r03).parent / "r03_anchored.jsonl")
        reflow(args.r03, args.srt, out, alert, anchored, args.snap_ms, args.cjk_speed)
    elif args.cmd == "attach-en":
        out = args.out or str(Path(args.r04).parent / "r04_bilingual.srt")
        attach_en(args.r04, args.r03, out)
    elif args.cmd == "check-r03":
        # r03 为目录 → 块级（r03_results/ + chunks/ 骨架 + r02_results/）；为文件 → 整段
        if os.path.isdir(args.r03):
            sys.exit(check_r03_blocks(args.r03, args.srt, args.chunks, args.r02, args.cjk_speed,
                                      check_frag=not args.no_frag, check_mismatch=not args.no_mismatch))
        sys.exit(check_r03(args.r03, args.srt, args.r02, args.cjk_speed,
                           check_frag=not args.no_frag, check_mismatch=not args.no_mismatch))
    elif args.cmd == "check-duration":
        sys.exit(check_duration(args.r04, args.r03, args.min_ms, args.cjk_speed, min_gap_ms=args.min_gap_ms))


if __name__ == "__main__":
    main()
