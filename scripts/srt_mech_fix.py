# -*- coding: utf-8 -*-
"""字幕机械修复：**纯脚本、零知识、零 LLM** 的上游修正层 → `00_subtitle_snapped.srt`。

## 定位

> 为什么单独成层
最上游的输入（YouTube 自动字幕）带有两类与“内容”无关的缺陷：
  1. **结构缺陷**：cue 重叠 / 倒序 / 异常时长
  2. **时间轴缺陷**：时间戳按“显示节奏”而非语音边界生成（实测中位滞后 ≈250ms，
     且大量边界落在词与词之间）
两者都**不需要任何领域知识**，可确定性地机械修正；且越早修，下游（空隙探测 /
分块 / 补标点 / 锚定）越不会吃进坏边界。

**与 LLM 层（阶段二 术语扫描的 ASR 修正）的分界**：本脚本**绝不动文本**。
ASR 误识别修正需要领域预判加载的词汇表 / asr_fixes 作先验，属语义判断，留在 LLM 层。

## 产物
`00_subtitle_snapped.srt` —— 全部工作流的时间轴新基准（`01` 的 `--cue-exact` 对照物）。
`01_subtitle_asr_fixed.srt` 仍是原文件名，其不变量由“相对**原始 ASR**”变为
“相对 **00**”（`01` 只改文本、时间码逐条照抄 `00`、不增删 cue）。

## 修正项
- **重叠 / 倒序 cue**：后条 `start` < 前条 `end` → 后条顺延到前条 `end`；若顺延后
  `end <= start` 则该 cue 不可修，报错退出（不静默产出坏轴）
- **异常时长**：`< ULTRA_SHORT_MS`、`> LONG_UNIT_MS` → 报告告警（**不自动改**——
  改时长会破坏语义边界）
- **时间轴吸附**（可选，需音频 + ffmpeg）：边界吸附到语音能量谷，起终点分向以保留 cue 间隙
  （实现复用 `srt_snap_audio`）
- **缺口反馈（本阶段一次性汇报，等用户决策，不擅自跳过）**：无音频 / ffmpeg 缺失时**暂停并退出码 1**
  （缺口一次性列出），由用户决定**补缺口重跑**还是**确认跳过**（`--skip-snap`）

## 不变量

> 写盘前自检，未过则退出码 1
cue 数不变、cue 文本逐条不变、每条 `start < end`、无重叠无倒序、吸附后 cue 间隙守恒

## 用法
  # 仅结构清理（无音频也能跑，保持“纯文本可跑”）
  python scripts/srt_mech_fix.py <原始ASR.srt> -o 00_subtitle_snapped.srt
  # 结构清理 + 时间轴吸附（音频显式指定）
  python scripts/srt_mech_fix.py <原始ASR.srt> -o 00_subtitle_snapped.srt --audio <音频>
  # 音频自动探测（同名音频 / 视频容器音轨 / 输入目录内音频文件）
  python scripts/srt_mech_fix.py <原始ASR.srt> -o 00_subtitle_snapped.srt --video <视频.mp4>
  # 缺口反馈后，用户确认跳过时间轴吸附
  python scripts/srt_mech_fix.py <原始ASR.srt> -o 00_subtitle_snapped.srt --skip-snap
`--report` 省略时写到 `<输入所在目录>/speech_align/mech_fix_report.md`（不依赖 cwd）。
退出码：0 = 完成（含用户确认跳过）；1 = 输入解析失败 / 自检未过 / **吸附缺口待用户决策**。
"""
import argparse
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

from shared.srt_common import ULTRA_SHORT_MS, LONG_UNIT_MS
from srt_snap_audio import (
    check_gaps, check_srt_invariants, envelope, fmt_srt, fmt_t, load_audio,
    parse_srt, pick_audio, snap_points,
)


def clean_structure(cues):
    """结构清理：重叠 / 倒序 cue 顺延。返回 (新 cues, 改动清单, 致命问题)。

    只调 `start`（顺延到前条 `end`）——`end` 是语音收尾点，比 `start` 可信；
    且顺延不改变后续 cue 的归属，是可逆的最小改动。
    """
    out = []
    fixes = []
    fatal = []
    for i, (idx, st, en, text) in enumerate(cues):
        if en <= st:
            fatal.append(f"cue {idx}: start({fmt_srt(st)}) ≥ end({fmt_srt(en)})，时长非正，无法机械修复")
            continue
        if out and st < out[-1][2]:
            prev_end = out[-1][2]
            if en <= prev_end:
                fatal.append(f"cue {idx}: 与 cue {out[-1][0]} 完全重叠（end {fmt_srt(en)} ≤ 前条 end {fmt_srt(prev_end)}），无法顺延")
                continue
            fixes.append((idx, out[-1][0], st, prev_end))
            st = prev_end
        out.append((idx, st, en, text))
    return out, fixes, fatal


def durations_outliers(cues):
    """异常时长 cue → [(idx, 时长ms, 类型)]。仅告警，不改（改时长会破坏语义边界）。"""
    bad = []
    for idx, st, en, _t in cues:
        ms = (en - st) * 1000
        if ms < ULTRA_SHORT_MS:
            bad.append((idx, ms, "极短"))
        elif ms > LONG_UNIT_MS:
            bad.append((idx, ms, "超长"))
    return bad


def main():
    ap = argparse.ArgumentParser(description="字幕机械修复（结构清理 + 可选时间轴吸附）")
    ap.add_argument("src", help="原始 ASR SRT")
    ap.add_argument("-o", "--out", help="输出 00_subtitle_snapped.srt（省略则只报告）")
    ap.add_argument("--audio", help="音频文件（缺省时按 --video / 输入目录自动探测）")
    ap.add_argument("--video", help="视频文件（自动取同名音频或容器音轨）")
    ap.add_argument("--skip-snap", action="store_true",
                    help="用户确认跳过时间轴吸附（缺口反馈后由其决策时使用；可单独用，也可与 --audio/--video 同用）")
    ap.add_argument("--report", help="报告路径（默认 <输入目录>/speech_align/mech_fix_report.md）")
    ap.add_argument("--window", type=float, default=0.35, help="吸附窗口(秒)")
    ap.add_argument("--min-drop", type=float, default=6.0, help="吸附所需能量下降(dB)")
    ap.add_argument("--min-gap", type=float, default=0.04, help="相邻边界最小间隔(秒)")
    ap.add_argument("--cache", default=None,
                    help="音频解码缓存 .npy（存在则直接读、不需音频源与 ffmpeg）")
    args = ap.parse_args()

    base = os.path.dirname(os.path.abspath(args.src))
    report = args.report or os.path.join(base, "speech_align", "mech_fix_report.md")

    cues = parse_srt(args.src)
    if not cues:
        sys.exit(f"❌ 无法解析：{args.src}")
    n_cue = len(cues)
    texts = [c[3] for c in cues]

    L = ["# 字幕机械修复报告", "", f"- 输入：{args.src}", f"- cue 数：{n_cue}", ""]

    # ---- 1. 结构清理 ----
    cues, fixes, fatal = clean_structure(cues)
    L.append("## 结构清理")
    if fatal:
        for f in fatal:
            L.append(f"  - ❌ {f}")
        L.append("")
        L.append("**存在不可机械修复的结构缺陷 → 未产出产物。**需人工/上游确认后重跑。")
        emit(report, L)
        sys.exit(1)
    L.append(f"- 重叠 / 倒序 cue 顺延：{len(fixes)} 处" + ("（无）" if not fixes else ""))
    for idx, pid, old, new in fixes[:30]:
        L.append(f"  - cue {idx}: start {fmt_srt(old)} → {fmt_srt(new)}（顺延到 cue {pid} 的 end）")
    bad = durations_outliers(cues)
    L.append(f"- 异常时长（仅告警、不自动改）：{len(bad)} 处")
    for idx, ms, kind in bad[:30]:
        L.append(f"  - cue {idx}: {ms:.0f}ms（{kind}）")
    L.append("")

    # ---- 2. 时间轴吸附（可选）----
    audio = pick_audio(args.audio, args.video, search_dirs=(base,))
    L.append("## 时间轴吸附")
    can, tag, gap_lines, code = check_gaps(audio, writes_output=bool(args.out), cache=args.cache,
                                           explicit=args.audio, search_dirs=(base,), video=args.video)
    if args.skip_snap:
        gap_lines = ([f"- 用户确认跳过（`--skip-snap`；环境本可用）"] if can
                     else gap_lines + ["- **用户确认跳过**（`--skip-snap`）"])
        can, tag, code = False, "skip-user", 0
    if not can:
        L += gap_lines
        if tag == "need-decision":
            L += ["", "**本阶段已暂停（未产出 `00`）。** 吸附缺口一次性反馈如下，请用户决策：",
                  "- 补缺口（`--audio` / `--video`，或安装 ffmpeg 并加入 PATH）后重跑；",
                  "- 或确认跳过时间轴吸附 → 重跑加 `--skip-snap`（`00` 照常产出、时间轴为原轴）。"]
            emit(report, L)
            sys.exit(code)
        L.append("")
        emit_report(report, L, args, cues, texts, n_cue, applied=True,
                    note="仅结构清理（" + ("用户确认跳过吸附" if tag == "skip-user"
                                          else "无音频 / 无 ffmpeg，未做吸附") + "）")
        return

    loaded = load_audio(audio, cache=args.cache, silent=True)
    if loaded is None:
        L += [f"- ❌ **ffmpeg 解码失败**：`{audio}`（文件损坏 / 不含音轨 / 格式不支持）", "",
              "**本阶段已暂停（未产出 `00`）。** 请用户决策：换可用音频 / 视频，或确认跳过吸附后加 `--skip-snap` 重跑。"]
        emit(report, L)
        sys.exit(1)
    x, sr = loaded
    db, hop = envelope(x, sr)
    L.append(f"- 音频：`{audio}`" if audio else f"- 音频：**缓存命中**（`{args.cache}`，未解码音频源）")
    L.append(f"- 音频时长 {fmt_t(len(x) / sr)}；包络 {len(db)} 帧 @ {hop * 1000:.1f}ms")
    L.append(f"- 参数：窗口 ±{args.window}s，下降阈 {args.min_drop}dB，最小间隔 {args.min_gap}s")

    points = [(st, "start") for _i, st, _e, _t in cues] + [(en, "end") for _i, _s, en, _t in cues]
    records = snap_points(db, hop, points, args.window, args.min_drop, args.min_gap)
    mp = {r["t"]: r["nt"] for r in records}
    new_cues = [(idx, mp[round(st, 3)], mp[round(en, 3)], t) for idx, st, en, t in cues]
    L.append(f"- 边界点 {len(records)} 个（起终分向吸附，保留 cue 间隙）")
    L.append("")

    # ---- 3. 不变量自检 ----
    problems = check_srt_invariants(cues, mp)
    L.append("## 不变量自检")
    if problems:
        L.append(f"❌ **{len(problems)} 项未通过**（时间轴可能被改坏，勿使用产物）：")
        for p in problems:
            L.append(f"  - {p}")
        L.append("")
        emit(report, L)
        sys.exit(1)
    L.append("✅ cue 数不变、文本逐条不变、每条 start<end、无重叠无倒序、cue 间隙守恒")
    L.append("")
    emit_report(report, L, args, new_cues, texts, n_cue, applied=True)


def emit_report(report, lines, args, cues, texts, n_cue, applied, note=None):
    """写产物（若要求）+ 落盘并打印报告。`applied` = 产物是否可写（跳过吸附不构成不可写）。"""
    lines.append("## 产物")
    if args.out and applied:
        out = ["%s\n%s --> %s\n%s\n" % (idx, fmt_srt(st), fmt_srt(en), "\n".join(text))
               for idx, st, en, text in cues]
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        open(args.out, "w", encoding="utf-8").write("\n".join(out))
        lines.append(f"- 时间轴基准：`{args.out}`（{n_cue} cue；文本逐条未改）")
        if note:
            lines.append(f"- {note}")
        lines.append("- `01_subtitle_asr_fixed.srt` 的 `--cue-exact` 对照物应改为本文件")
    elif args.out:
        lines.append("- **未产出**（存在不可机械修复的结构缺陷，或吸附后自检未过）")
    else:
        lines.append("- 未指定 `-o`，仅报告")
    emit(report, lines)


def emit(report, lines):
    txt = "\n".join(lines)
    os.makedirs(os.path.dirname(os.path.abspath(report)), exist_ok=True)
    open(report, "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
