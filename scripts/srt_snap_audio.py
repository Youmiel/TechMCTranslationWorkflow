# -*- coding: utf-8 -*-
"""音频吸附时间轴：以语音能量谷为真值，修正 SRT / en_timeline 的时间戳偏移（纯音频，无 ML 依赖）。

## 背景

> 为什么需要
自动字幕（YouTube ASR）的时间轴按“显示节奏”而非语音边界生成：实测中位滞后
≈ +250ms，且大量边界落在词与词之间。此偏差会沿 reflow/reflow2 链条传给下游译文。
本脚本用 ffmpeg + numpy 的能量包络定位语音停顿，把每个边界吸附到最近的能量谷。

## 能力边界

> 务必知悉
**能修**：时间戳偏移；边界落在词中（吸附到气口）。
**不能修**：语义断句（哪些边界该存在、该切在哪）——那需要文本信息（句法/标点），
纯音频无从判断。因此本脚本**不改变边界数量与文本**，只移动边界时刻。
对连读中间无能量谷的边界，标为 `unfixed` 输出到报告（提示需文本层介入）。

## 判据与不变量
- 边界吸附：±W 窗口内定位能量谷，相对局部语音能量下降 ≥ min-drop(dB) 才生效
- **起终点分向吸附**：cue 结束取谷底（语音收尾）；cue 开始取谷底之后能量回升处（语音起音）。
  两者若都用谷底，“前 cue 结束”与“后 cue 开始”会吸到同一帧 → **cue 间隙被抹平**；
  而该间隙是 reflow 空隙探测（`gap = 下条 start − 上条 end`）的唯一输入，
  抹平后生效空隙点集变空、分块退化
- 保序：吸附后边界严格单调，相邻间隔 ≥ min-gap（只推挤，不主动拉开原有间隙）
- 时间戳不变量（写盘前自检，见报告“不变量自检”节）：cue 数、cue 文本、E 句编号与文本
  完全不变；cue 内 start < end；无逆序、无重叠；**间隙数守恒**（原轴有几处相邻 cue 分离，
  吸附后仍应有几处）

## 音频来源
`--audio` 显式指定，或 `--video` 指向视频（自动在视频同名/同目录找独立音频，或直接读容器
音轨——ffmpeg 可解码 mp4/mkv 音轨，无需先分离）。

## 缺口反馈（不静默跳过）
无音频源 / `--audio` 路径不存在 / ffmpeg 不在 PATH 时，**`--apply`（要写产物）会暂停并退出码 1**，
把缺口**一次性**反馈到报告（含**探测足迹**：搜索过哪些目录、各自实际内容），等用户决策：
补缺口（`--audio`/`--video`、装 ffmpeg 并加入 PATH）后重跑，或 `--skip-snap` 确认跳过。
仅报告模式（不带 `--apply`）本就无写盘动作，缺口只作提示、退出码 0。

**`--cache` 命中时无缺口**：`load_audio` 直接 `np.load`，既不需音频源也不需 ffmpeg（缓存自先前的成功解码）。

## 用法
  # 报告模式（默认，不改产物）
  python scripts/srt_snap_audio.py --audio <音频> --srt 01_subtitle_asr_fixed.srt
  # 写盘
  python scripts/srt_snap_audio.py --audio <音频> --srt 01.srt -o 00_subtitle_snapped.srt --apply
  # 视频容器内音轨（自动探测音频源）
  python scripts/srt_snap_audio.py --video <视频.mp4> --srt 01.srt -o 00_subtitle_snapped.srt --apply
  # en_timeline 目录（时间轴固化层）
  python scripts/srt_snap_audio.py --audio <音频> --etimeline reflow2/en_timeline
  # 缺口反馈后，用户确认跳过（跳过不产出吸附产物，退出码 0）
  python scripts/srt_snap_audio.py --srt 01.srt -o 00.srt --apply --skip-snap
`--report` 省略时写到 `<输入所在目录>/speech_align/snap_report.md`（不依赖 cwd）。
退出码：0 = 完成（含用户确认跳过 / 仅报告模式的缺口提示）；1 = 输入解析失败 / 自检未过 /
`--apply` 遇缺口待用户决策（无音频源、ffmpeg 缺失、解码失败）/ `--skip-snap` 未与 `--apply` 同用。
"""
import argparse
import glob
import os
import re
import shutil
import subprocess
import sys

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

ETL_LINE_RE = re.compile(r"^(E\d+)\t(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\t(\S+)\t(.*)$")


def fmt_t(t):
    return f"{int(t // 60):02d}:{t % 60:06.3f}"


def fmt_srt(t):
    ms = max(0, int(round(t * 1000)))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


AUDIO_EXTS = (".mp3", ".m4a", ".opus", ".wav", ".flac", ".aac", ".ogg")
VIDEO_EXTS = (".mp4", ".mkv", ".webm", ".mov", ".avi")
# 疑似音频 / 视频但不在白名单——仅供「格式不受支持」诊断，不参与选取
AUDIO_LIKE_EXTS = (".wma", ".aiff", ".aif", ".m4b", ".amr", ".ape", ".au", ".ra", ".oga", ".weba")
VIDEO_LIKE_EXTS = (".flv", ".wmv", ".m4v", ".mpg", ".mpeg", ".ts", ".vob", ".3gp", ".rmvb", ".rm")
FOOTPRINT_MAX_FILES = 25


def pick_audio(explicit=None, video=None, search_dirs=()):
    """定位可用音频源；无则返回 None。

    优先级：显式 --audio → 视频同名音频 → 视频容器本身（ffmpeg 抽轨）→ search_dirs 内音频。
    覆盖三种实际形态：独立音频文件、视频内音轨、目录内任意音频（自动字幕下载常留 mp3）。

    返回 None 后**不静默降级**——由 `check_gaps` 判定「暂停待用户决策」还是「报告模式仅提示」。
    """
    if explicit:
        return explicit
    cands = []
    if video:
        p = os.path.abspath(video)
        stem, ext = os.path.splitext(p)
        for a in AUDIO_EXTS:
            if os.path.exists(stem + a):
                cands.append(stem + a)
        if os.path.exists(p) and ext.lower() in VIDEO_EXTS:
            cands.append(p)
    for d in search_dirs:
        if not d or not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if os.path.splitext(f)[1].lower() in AUDIO_EXTS:
                cands.append(os.path.join(d, f))
    return cands[0] if cands else None


def scan_footprint(search_dirs=(), video=None, max_files=FOOTPRINT_MAX_FILES):
    """生成「探测足迹」：搜索位置 → 各目录**实际内容**，供诊断音频缺失的根因。

    只做目录列举（零文件读取、零解码）。附在缺口反馈里，让 Agent / 用户无需再补一轮
    目录列举，即可判断：音频放错位置 / 格式不在白名单 / 尚未下载 / 搜索目录本身不对。
    """
    L = ["- **探测足迹**（搜索位置 → 实际内容）："]
    if video:
        vp = os.path.abspath(video)
        L.append(f"  - `--video`：`{vp}`（{'存在' if os.path.exists(vp) else '**不存在**'}）")
        stem = os.path.splitext(vp)[0]
        same = [os.path.basename(stem + a) for a in AUDIO_EXTS if os.path.exists(stem + a)]
        L.append("  - 视频同名音频：" + (f"找到 {same}" if same else "无"))
    for d in [x for x in search_dirs if x]:
        if not os.path.isdir(d):
            L.append(f"  - `{d}`：**目录不存在**（检查输入文件路径是否正确）")
            continue
        try:
            files = sorted(f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f)))
        except OSError as e:
            L.append(f"  - `{d}`：**不可读**（{e}）")
            continue
        like = [f for f in files
                if os.path.splitext(f)[1].lower() in AUDIO_LIKE_EXTS + VIDEO_LIKE_EXTS]
        L.append(f"  - `{d}`：{len(files)} 个文件，白名单音频 / 视频 0 个")
        if like:
            L.append(f"    - ⚠️ **疑似音频/视频但格式不在白名单**：{like}")
        for f in files[:max_files]:
            L.append(f"    - `{f}`")
        if len(files) > max_files:
            L.append(f"    - …（余 {len(files) - max_files} 个未列）")
    return L


def check_gaps(audio, writes_output, cache=None, explicit=None, search_dirs=(), video=None):
    """探测时间轴吸附的**输入 / 环境缺口** → `(can_run, tag, lines, exit_code)`。

    与 `srt_mech_fix.py` 共用本函数，保证「一次性反馈 + 待用户决策」口径一致。
    本函数**只做判定与文案**，不改行为（是否产出由调用方决定）。

    `writes_output` = 本次是否要写产物（写则缺口阻断 → 待用户决策；不写仅提示）。

      tag = "ok"                 环境齐备，可执行
      tag = "need-decision"      缺口存在且要写产物 → **暂停等用户决策**（exit_code=1）
      tag = "skip-no-audio"      无音频、仅报告模式 → 不吸附
      tag = "skip-no-ffmpeg"     ffmpeg 缺失、仅报告模式 → 不吸附
      tag = "skip-bad-explicit"  `--audio` 路径不存在、仅报告模式 → 不吸附

    `cache` 命中时**无缺口**——`load_audio` 直接 `np.load`，既不需音频源也不需 ffmpeg。
    `lines` = 反馈要点（need-decision 时供调用方追加决策指引）。
    """
    if cache and os.path.exists(cache):
        return (True, "ok", [], 0)
    if explicit and not os.path.exists(explicit):
        lines = [f"- **`--audio` 指定的文件不存在**：`{explicit}`",
                 "- 检查路径拼写 / 文件是否已移动；或改用 `--video`（自动找同名音频或读容器音轨）"]
        return ((False, "need-decision", lines, 1) if writes_output
                else (False, "skip-bad-explicit", lines, 0))
    if not audio:
        lines = ["- **无音频可用**（未指定，且输入目录 / 视频旁均未探测到）",
                 "- 探测顺序：`--audio` → `--video` 同名音频 → 视频容器音轨 → 输入目录内音频文件",
                 "- 白名单：音频 " + " / ".join(AUDIO_EXTS) + "；视频 " + " / ".join(VIDEO_EXTS)]
        if writes_output:
            return (False, "need-decision",
                    lines + [""] + scan_footprint(search_dirs, video), 1)
        return (False, "skip-no-audio", lines, 0)
    if shutil.which("ffmpeg") is None:
        lines = [f"- **ffmpeg 不在 PATH**（已探测到音频：`{audio}`）",
                 "- 装上 ffmpeg 并把其 bin 目录加入 PATH 后重跑"]
        return ((False, "need-decision", lines, 1) if writes_output
                else (False, "skip-no-ffmpeg", lines, 0))
    return (True, "ok", [], 0)


def load_audio(path, sr=16000, cache=None, silent=False):
    """解码为 float32 单声道。`silent=True` 时解码失败返回 `None`（调用方自行反馈）。"""
    if cache and os.path.exists(cache):
        return np.load(cache), sr
    p = subprocess.run(["ffmpeg", "-v", "quiet", "-i", path, "-ac", "1", "-ar", str(sr),
                        "-f", "s16le", "-"], capture_output=True)
    if p.returncode != 0 or not p.stdout:
        if silent:
            return None
        sys.exit(f"❌ ffmpeg 解码失败：{path}")
    x = np.frombuffer(p.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    if cache:
        os.makedirs(os.path.dirname(os.path.abspath(cache)), exist_ok=True)
        np.save(cache, x)
    return x, sr


def envelope(x, sr, frame_ms=10, hop_ms=5):
    """能量包络（dBFS）。累积和实现，避免大矩阵内存。"""
    f = max(1, int(sr * frame_ms / 1000))
    h = max(1, int(sr * hop_ms / 1000))
    cs = np.concatenate([[0.0], np.cumsum(x.astype(np.float64) ** 2)])
    n = 1 + max(0, (len(x) - f) // h)
    starts = np.arange(n) * h
    rms = np.sqrt((cs[starts + f] - cs[starts]) / f + 1e-12)
    return 20 * np.log10(rms), h / sr


def snap_point(db, hop, t, window, min_drop, mode):
    """单点吸附 → (nt, drop, status)。

    mode="end"   → 窗口内能量最低帧（cue 结束 = 语音收尾，落静音起点附近）
    mode="start" → 最低帧之后能量回升 ≥ min_drop 的第一帧（cue 开始 = 语音起音，
                   落静音终点附近）

    为什么要分向：同一段静音两侧的“前 cue 结束”与“后 cue 开始”若都取谷底，
    会吸到同一帧 → cue 间隙归零。而该间隙是 reflow 空隙探测的唯一输入
    （`gap = 下条 start − 上条 end`），抹平后生效空隙点集变空、分块退化。

    status："valley" 吸附到谷（有位移）/ "at-valley" 目标点恰在谷上 / "unfixed" 窗口内无谷可用。
    """
    a = max(0, int((t - window) / hop))
    b = min(len(db), int((t + window) / hop) + 1)
    if b <= a + 1:
        return t, 0.0, "unfixed"
    seg = db[a:b]
    i = int(np.argmin(seg))
    floor = float(seg[i])
    drop = float(np.percentile(seg, 90) - floor)
    if drop < min_drop:
        return t, drop, "unfixed"
    j = i
    if mode == "start":
        thr = floor + min_drop
        while j + 1 < len(seg) and seg[j] < thr:
            j += 1
    nt = (a + j) * hop
    return (t, drop, "at-valley") if abs(nt - t) < 1e-9 else (nt, drop, "valley")


def snap_points(db, hop, points, window, min_drop, min_gap):
    """点序列吸附：`points=[(t, role)]`，role ∈ {"start", "end"}。

    先按时刻排序去重（同一时刻的 role 合并），再逐点吸附、施加保序约束。
    去重是关键：cue 首尾相接（原轴 start == 前条 end）时合并为单点，不会被
    保序拆成 min_gap 间隔——即**原轴无缝处保持无缝，有缝处保持有缝**。

    返回点级记录（按时刻升序），每点含：
      t / nt / raw_nt / drop / status / pushed / role
    role = "both"（同一时刻既是某 cue 结束又是下条 cue 开始）
    """
    merged = {}
    for t, role in points:
        merged.setdefault(round(t, 3), set()).add(role)
    records = []
    prev_nt = None
    for t in sorted(merged):
        roles = merged[t]
        nt, drop, status = snap_point(db, hop, t, window, min_drop,
                                      "end" if "end" in roles else "start")
        raw_nt = nt
        pushed = False
        if prev_nt is not None and nt < prev_nt + min_gap:
            nt = prev_nt + min_gap
            pushed = True
        records.append({"t": t, "nt": nt, "raw_nt": raw_nt, "drop": drop,
                        "status": status, "pushed": pushed,
                        "role": "both" if len(roles) > 1 else next(iter(roles))})
        prev_nt = nt
    return records


def check_srt_invariants(cues, mp):
    """SRT 吸附后的时间戳不变量自检 → problems(list[str])。

    “时间被改坏”在全链无校验点（下游 `io.build_full` 的文本锚定不含时间），故在此自检：
      - cue 内 start < end（吸附可能使结束早于开始）
      - 无逆序（后条 start 早于前条 end = 重叠）
      - **间隙数守恒**：原轴相邻 cue 分离（start > 前条 end）的处数，吸附后应完全一致。
        边集构造若退回“只取每条 cue 的 end”，间隙会被整体抹平且**不报任何错**。
    """
    problems = []
    for i, (idx, st, en, _t) in enumerate(cues):
        ns, ne = mp[round(st, 3)], mp[round(en, 3)]
        if ne <= ns:
            problems.append(f"cue {idx}: 吸附后 start({fmt_srt(ns)}) ≥ end({fmt_srt(ne)})")
        if i and ns < mp[round(cues[i - 1][2], 3)]:
            problems.append(f"cue {idx}: 吸附后与前条重叠（{fmt_srt(ns)} < 前条 end {fmt_srt(mp[round(cues[i - 1][2], 3)])}）")
    g0 = sum(1 for i, c in enumerate(cues) if i and c[1] > cues[i - 1][2])
    g1 = sum(1 for i, c in enumerate(cues)
             if i and mp[round(c[1], 3)] > mp[round(cues[i - 1][2], 3)])
    if g0 != g1:
        problems.append(f"间隙数不守恒：原轴 {g0} 处 → 吸附后 {g1} 处"
                        "（reflow 空隙探测读该量，变化会导致生效空隙点集改变）")
    return problems


def parse_srt(path):
    raw = open(path, encoding="utf-8-sig").read().replace("\r\n", "\n")
    out = []
    for blk in re.split(r"\n\s*\n", raw.strip()):
        ls = blk.split("\n")
        if len(ls) < 2 or not re.fullmatch(r"\d+", ls[0].strip()):
            continue
        m = re.match(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})", ls[1])
        if not m:
            continue
        g = list(map(int, m.groups()))
        out.append((ls[0].strip(),
                    g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000,
                    g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000,
                    ls[2:]))
    return out


def report_lines(args, dur, db, hop, records, src, audio, problems=(), extra=()):
    """从点级 records（snap_points 产物）生成报告。"""
    own = np.array([(r["nt"] - r["t"]) for r in records if not r["pushed"]]) * 1000   # 自主位移
    pushed = [r for r in records if r["pushed"]]
    drops = np.array([r["drop"] for r in records])
    n = len(records) or 1
    n_valley = sum(1 for r in records if r["status"] == "valley")
    n_at = sum(1 for r in records if r["status"] == "at-valley")
    unfixed = [r for r in records if r["status"] == "unfixed"]

    L = ["# 时间轴吸附报告（语音谷）", ""]
    L.append(f"- 输入：{src}")
    L.append(f"- 音频：{audio}" if audio else "- 音频：（缓存命中，未解码音频源）")
    L.append(f"- 音频时长 {fmt_t(dur)}；包络 {len(db)} 帧 @ {hop*1000:.1f}ms")
    L.append(f"- 参数：窗口 ±{args.window}s，下降阈 {args.min_drop}dB，最小间隔 {args.min_gap}s")
    L.append(f"- 边界点 {len(records)} 个")
    for e in extra:
        L.append(f"- {e}")
    L.append("")
    L.append("## 不变量自检")
    if problems:
        L.append(f"❌ **{len(problems)} 项未通过**（时间轴可能被改坏，勿直接使用产物）：")
        for p in problems:
            L.append(f"  - {p}")
    else:
        L.append("✅ cue 内 start<end、无逆序重叠、**间隙数守恒**、文本与 cue 数未变")
    L.append("")
    L.append("## 边界分类")
    L.append(f"- **吸附到谷**（valley）：{n_valley}（{n_valley/n*100:.0f}%）")
    L.append(f"- **本来就在谷上**（at-valley，无需移动）：{n_at}（{n_at/n*100:.0f}%）")
    L.append(f"- **无谷可用**（unfixed，需文本层/人工）：{len(unfixed)}（{len(unfixed)/n*100:.0f}%）")
    L.append("")
    L.append("## 位移统计（已分离“被推挤”）")
    if len(own):
        L.append(f"- 自主位移（不含被推挤）：均值 {own.mean():+.0f}ms，中位 {np.median(own):+.0f}ms，"
                 f"**绝对中位 {np.median(np.abs(own)):.0f}ms**")
        L.append(f"- 方向：前移 {(own<-1).sum()} / 后移 {(own>1).sum()} / 未动 {(np.abs(own)<=1).sum()}")
    L.append(f"- 被前邻最小间隔推挤：{len(pushed)} 处"
             + (f"（最大推挤 {max(abs(r['nt']-r['raw_nt']) for r in pushed)*1000:.0f}ms）" if pushed else ""))
    L.append(f"- 边界处能量下降中位：**{np.median(drops):.1f}dB**")
    L.append("")
    L.append("## 按角色")
    for role, desc in (("start", "cue/E 句起点（语音起音）"), ("end", "cue/E 句终点（语音收尾）"),
                       ("both", "起终重合（原轴无缝）")):
        sub = [r["nt"] - r["t"] for r in records if r["role"] == role and not r["pushed"]]
        if sub:
            a = np.abs(np.array(sub)) * 1000
            L.append(f"- {desc}：{len(sub)} 点，绝对位移中位 {np.median(a):.0f}ms")

    if unfixed:
        L.append("")
        L.append("### unfixed 明细（窗口内无谷，需文本层/人工）")
        for r in unfixed[:30]:
            L.append(f"  - @{fmt_t(r['t'])} [{r['role']}] 局部下降仅 {r['drop']:.1f}dB")

    L.append("")
    L.append("## 能力边界")
    L.append("- 本脚本只移动边界时刻，**不改变边界数量与文本**")
    L.append("- 语义断句（长句该切在哪）需文本信息，纯音频无法判断 → 见 speech_align 报告")
    L.append("- 判据：吸附仅在窗口内能量下降 ≥ 阈值时生效；起终点分向吸附以保留 cue 间隙")
    return L


def emit_report(path, lines):
    """报告落盘 + 打印（路径含目录时自动创建；与 cwd 无关）。"""
    txt = "\n".join(lines)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    open(path, "w", encoding="utf-8").write(txt)
    print(txt)


def main():
    ap = argparse.ArgumentParser(description="音频吸附时间轴（纯音频，修正时间戳偏移）")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--srt", help="输入 SRT（cue 级）")
    g.add_argument("--etimeline", help="输入 en_timeline 目录（E 句级）")
    ap.add_argument("--audio", help="音频文件（缺省时按 --video / 输入目录自动探测）")
    ap.add_argument("--video", help="视频文件（自动取同名音频或容器音轨）")
    ap.add_argument("-o", "--out", help="输出路径（目录输入时为输出目录）")
    ap.add_argument("--report", help="报告路径（默认 <输入目录>/speech_align/snap_report.md）")
    ap.add_argument("--window", type=float, default=0.35, help="吸附窗口(秒)")
    ap.add_argument("--min-drop", type=float, default=6.0, help="吸附所需能量下降(dB)")
    ap.add_argument("--min-gap", type=float, default=0.04, help="相邻边界最小间隔(秒)")
    ap.add_argument("--apply", action="store_true", help="写出结果（默认只报告）")
    ap.add_argument("--skip-snap", action="store_true",
                    help="用户确认跳过时间轴吸附（缺口反馈后由其决策时使用，须与 --apply 同用）")
    ap.add_argument("--cache", default=None,
                    help="音频解码缓存 .npy（存在则直接读、不需音频源与 ffmpeg）")
    args = ap.parse_args()
    if args.skip_snap and not args.apply:
        sys.exit("❌ --skip-snap 需与 --apply 同用（它是「用户确认跳过」的凭据）")

    src = args.srt or args.etimeline
    base = os.path.dirname(os.path.abspath(args.srt if args.srt else args.etimeline.rstrip("/\\")))
    report = args.report or os.path.join(base, "speech_align", "snap_report.md")

    audio = pick_audio(args.audio, args.video, search_dirs=(base,))
    can, tag, lines, code = check_gaps(audio, writes_output=args.apply, cache=args.cache,
                                       explicit=args.audio, search_dirs=(base,), video=args.video)
    if args.skip_snap:
        lines = ([f"- 用户确认跳过（`--skip-snap`；环境本可用）"] if can
                 else lines + ["- **用户确认跳过**（`--skip-snap`）"])
        can, tag, code = False, "skip-user", 0
    if not can:
        L = ["# 时间轴吸附报告（语音谷）", "", f"- 输入：{src}", *lines]
        if tag == "need-decision":
            L += ["", "**本脚本已暂停（未产出产物）。** 请用户决策（缺口已一次性反馈）：",
                  "- 补上缺口（提供 `--audio` / `--video`，或安装 ffmpeg 并确保在 PATH）后重跑；",
                  "- 或确认跳过时间轴吸附 → 重跑加 `--apply --skip-snap`（产物照常写出）。"]
        emit_report(report, L)
        if code:
            sys.exit(code)
        return

    loaded = load_audio(audio, cache=args.cache, silent=True)
    if loaded is None:
        emit_report(report, ["# 时间轴吸附报告（语音谷）", "", f"- 输入：{src}",
                             f"- ❌ ffmpeg 解码失败：{audio}（文件损坏或格式不支持）"])
        sys.exit(1)
    x, sr = loaded
    db, hop = envelope(x, sr)
    dur = len(x) / sr

    if args.srt:
        cues = parse_srt(args.srt)
        if not cues:
            sys.exit(f"❌ 无法解析：{args.srt}")
        points = []
        for _idx, st, en, _text in cues:
            points.append((st, "start"))
            points.append((en, "end"))
        records = snap_points(db, hop, points, args.window, args.min_drop, args.min_gap)
        mp = {r["t"]: r["nt"] for r in records}
        L = report_lines(args, dur, db, hop, records, args.srt, audio,
                         check_srt_invariants(cues, mp))
        if args.apply:
            if not args.out:
                sys.exit("❌ --apply 需同时给 -o/--out")
            lines = []
            for idx, st, en, text in cues:
                lines += [idx, f"{fmt_srt(mp[round(st, 3)])} --> {fmt_srt(mp[round(en, 3)])}"] + list(text) + [""]
            os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
            open(args.out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
            L += ["", "## 输出", f"- 已写出：{args.out}"]
        emit_report(report, L)
        return

    # --- en_timeline 目录 ---
    files = sorted(glob.glob(os.path.join(args.etimeline, "chunk_*.txt")))
    if not files:
        sys.exit(f"❌ 目录无 chunk_*.txt：{args.etimeline}")
    total_records = []
    per_file = {}
    for fp in files:
        lines = open(fp, encoding="utf-8").read().split("\n")
        recs = []
        for ln in lines:
            m = ETL_LINE_RE.match(ln)
            if m:
                recs.append((m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)))
        if not recs:
            per_file[fp] = (lines, None)
            continue
        # E 句之间可能有间隙（起点 ≠ 前句终点）→ 起点按 start 分向、终点按 end 分向，间隙守恒
        points = [(parse_time_any(r[1]), "start") for r in recs] \
                 + [(parse_time_any(r[2]), "end") for r in recs]
        records = snap_points(db, hop, points, args.window, args.min_drop, args.min_gap)
        per_file[fp] = (lines, {r["t"]: r["nt"] for r in records})
        total_records += records
    L = report_lines(args, dur, db, hop, total_records, args.etimeline, audio,
                     extra=(f"块文件 {len(files)} 个",))
    if args.apply:
        if not args.out:
            sys.exit("❌ --apply 需同时给 -o/--out")
        os.makedirs(args.out, exist_ok=True)
        for fp, (lines, mp) in per_file.items():
            dst = os.path.join(args.out, os.path.basename(fp))
            if mp is None:
                open(dst, "w", encoding="utf-8").write("\n".join(lines))
                continue
            out = []
            for ln in lines:
                m = ETL_LINE_RE.match(ln)
                if not m:
                    out.append(ln)
                    continue
                eid, span, txt = m.group(1), m.group(4), m.group(5)
                ns = mp[round(parse_time_any(m.group(2)), 3)]
                ne = mp[round(parse_time_any(m.group(3)), 3)]
                out.append(f"{eid}\t{fmt_srt(ns)} --> {fmt_srt(ne)}\t{span}\t{txt}")
            open(dst, "w", encoding="utf-8").write("\n".join(out))
        L += ["", "## 输出", f"- 已写出目录：{args.out}"]
    emit_report(report, L)


def parse_time_any(s):
    h, m, rest = s.split(":")
    sec, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000


if __name__ == "__main__":
    main()
