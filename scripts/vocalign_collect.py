# -*- coding: utf-8 -*-
"""vocalign 语音采集：音频 → 词级时轴（文本 + 标点 + 每词起止时间）

定位
    vocalign 工作流的**唯一需要重型依赖的环节**。两步走，必须**分两个进程**
    （`whisperx` 与 `ctranslate2` 同进程会触发 cuDNN 冲突）：

        ① transcribe：faster-whisper **段级**转写 → segments.srt（文本 + 标点）
           ⚠️ 必须用段级（`word_timestamps=False`、`vad_filter=False`）——
              faster-whisper 的**词级**模式标点严重退化（实测最长句 129 词、数字转单词）；
              段级模式标点正常（句末停顿 p50 847ms）。
        ② align：wav2vec2 强制对齐 → words.json（词级时间戳）
           只用 `whisperx.align`，**不用** `whisperx.transcribe`（后者拉 pyannote，同 cuDNN 报错）。

⚠️ **未对齐词必须保留占位**（本脚本的关键行为）
    whisperX 约 2.6% 词对齐失败，实测**几乎全是数字**（`15.` / `3` / `8, 8` / `20`）。
    若像探针脚本那样 `continue` 丢弃，词序列会出现“空洞”→ 前后词直接相邻 →
    跨空洞的间隙被 `vocalign_skeleton.py` 误判为停顿边界，实测伪边界：
        `values of | and`（原文 "values of 1 and 2"）
        `going from | to`（原文 "going from 1 to 15"）
    故本脚本把失败词**保留在序列里、时间置 null**，由骨架构建器按前后锚点插值补齐。

输出（`-o` 目录）
    `segments.srt`  段级转写（文本 + 标点）
    `words.json`    词级时轴（`{"meta": {...}, "words": [{"start","end","text","score"}]}`）
    `collect_report.txt`  采集报告（耗时 / 词数 / 未对齐数 / 间隙统计）

⚠️ **运行环境**（本脚本依赖 torch / faster-whisper / whisperx，**不在主 requirements 内**）
    命令根 = Project_Main/；一律用 venv 的 python，**勿 activate**：
        Project_Main\\.venv\\Scripts\\python.exe scripts/vocalign_collect.py audio.mp3 -o <work>/vocalign
    依赖坑与修复见 `Project_Plan/2026-10-08_vocalign工作流设计.md` §6.2。

用法
    python scripts/vocalign_collect.py <音频> -o <work>/vocalign                    # 两步全跑
    python scripts/vocalign_collect.py <音频> -o <work>/vocalign --stage transcribe # 只转写
    python scripts/vocalign_collect.py <音频> -o <work>/vocalign --stage align \\
        --text-srt <已有文本.srt>                                                   # 只对齐（跳过转写，~10s）

退出码：0 = 成功；1 = 依赖缺失 / 步骤失败。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

DEFAULT_MODEL = "large-v3"
DEFAULT_DEVICE = "cuda"
DEFAULT_COMPUTE = "float16"
DEFAULT_LANG = "en"


def _require(mod, hint):
    try:
        return __import__(mod)
    except ImportError:
        sys.exit("❌ 缺少依赖 %s。%s\n   运行环境：%s" % (
            mod, hint, os.path.join(".venv", "Scripts", "python.exe")))


def _fmt_srt_time(sec):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)


def _parse_srt(path):
    import re
    with open(path, encoding="utf-8-sig") as fh:
        raw = fh.read()
    time_re = re.compile(
        r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})")
    out = []
    for block in re.split(r"\n\s*\n", raw.strip()):
        lines = [x for x in block.split("\n") if x.strip()]
        ti, m = None, None
        for i, ln in enumerate(lines):
            m = time_re.search(ln)
            if m:
                ti = i
                break
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0
        end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0
        out.append({"start": start, "end": end, "text": " ".join(lines[ti + 1:]).strip()})
    return out


def stage_transcribe(args, report):
    """faster-whisper 段级转写 → segments.srt"""
    _require("faster_whisper", "安装：pip install faster-whisper")
    from faster_whisper import WhisperModel
    srt_path = os.path.join(args.out, "segments.srt")
    t0 = time.perf_counter()
    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)
    # 注：`WhisperModel.transcribe` 无 batch_size（批处理属 BatchedInferencePipeline，
    # 会默认开启 VAD 分块，破坏本工作流要求的“段级 + 无 VAD”口径）→ 走原生串行调用
    # 注：`condition_on_previous_text` 开启时有标点优势，但 whisper 在前文条件下偶发
    # **段级重复幻觉**（后段重复前段末句）→ 重复段时距被压缩 → 强制对齐错位 → 骨架伪边界；
    # 可用 `--no-repeat-ngram` 抑制、或 `--no-cond-prev` 关闭前文上下文（实测标点会退化）
    segments, info = model.transcribe(
        args.audio, language=args.language, word_timestamps=False, vad_filter=False,
        condition_on_previous_text=not args.no_cond_prev,
        no_repeat_ngram_size=args.no_repeat_ngram or None)
    segs = list(segments)
    with open(srt_path, "w", encoding="utf-8", newline="\n") as fh:
        for i, s in enumerate(segs, 1):
            fh.write("%d\n%s --> %s\n%s\n\n" % (
                i, _fmt_srt_time(s.start), _fmt_srt_time(s.end), str(s.text).strip()))
    dur = time.perf_counter() - t0
    report["transcribe"] = {"seconds": round(dur, 1), "segments": len(segs),
                            "audio_seconds": round(getattr(info, "duration", 0.0), 1),
                            "rtf": round(dur / max(1e-6, getattr(info, "duration", 1.0)), 4)}
    print("转写：%d 段 / %.1fs（RTF %.3f）→ %s" % (
        len(segs), dur, report["transcribe"]["rtf"], srt_path))
    return srt_path


def stage_align(args, report, srt_path):
    """wav2vec2 强制对齐 → words.json（保留未对齐词占位）"""
    _require("whisperx", "安装见设计文档 §6.2（含 ctranslate2 --no-deps 升版与 transformers<5）")
    import whisperx
    import torch

    if not srt_path or not os.path.exists(srt_path):
        sys.exit("❌ 对齐需要 segments.srt（先跑 --stage transcribe，或用 --text-srt 指定）")
    segments = _parse_srt(srt_path)
    for s in segments:
        s["text"] = s["text"].strip()

    t0 = time.perf_counter()
    wav = whisperx.load_audio(args.audio)
    model_a, metadata = whisperx.load_align_model(language_code=args.language, device=args.device)
    load_s = time.perf_counter() - t0
    t1 = time.perf_counter()
    aligned = whisperx.align(segments, model_a, metadata, wav, args.device,
                             return_char_alignments=False)
    align_s = time.perf_counter() - t1
    del model_a
    if args.device == "cuda":
        torch.cuda.empty_cache()

    words, n_total, n_unaligned = [], 0, 0
    for seg in aligned["segments"]:
        for w in seg.get("words") or []:
            n_total += 1
            st, en = w.get("start"), w.get("end")
            if st is None or en is None:
                # ⚠️ 保留占位（不丢弃！）——由骨架构建器插值补齐，防“空洞伪边界”
                words.append({"start": None, "end": None, "text": w.get("word", ""), "score": None})
                n_unaligned += 1
            else:
                words.append({"start": round(float(st), 3), "end": round(float(en), 3),
                              "text": w.get("word", ""),
                              "score": None if w.get("score") is None else round(float(w["score"]), 3)})

    gaps = [round((b["start"] - a["end"]) * 1000, 1)
            for a, b in zip(words, words[1:])
            if a["end"] is not None and b["start"] is not None]
    payload = {"meta": {
        "audio": os.path.basename(args.audio),
        "model": args.model, "device": args.device, "compute_type": args.compute_type,
        "language": args.language,
        "segments": len(segments), "n_words": len(words),
        "n_unaligned": n_unaligned,
        "timing_s": {"load_and_extract": round(load_s, 2), "align": round(align_s, 2)},
    }, "words": words}
    out_path = os.path.join(args.out, "words.json")
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)

    report["align"] = payload["meta"]
    print("对齐：%d 词（未对齐 %d，已保留占位）/ %.1fs（含音频解码 %.1fs）→ %s" % (
        len(words), n_unaligned, load_s + align_s, load_s, out_path))
    if gaps:
        gs = sorted(gaps)
        report["gap_ms_p50"] = gs[len(gs) // 2]
        print("词间间隙 p50 = %.0fms（伪间隙 baseline 取 40ms）" % gs[len(gs) // 2])
    return out_path


def main():
    ap = argparse.ArgumentParser(description="vocalign 语音采集：音频 → 词级时轴")
    ap.add_argument("audio", help="音频或视频文件（mp4/mkv 可直接解码）")
    ap.add_argument("-o", "--out", required=True, help="输出目录（<work>/vocalign/）")
    ap.add_argument("--stage", choices=("all", "transcribe", "align"), default="all",
                    help="分阶段执行（all = 分两进程各跑一步）")
    ap.add_argument("--text-srt", default=None,
                    help="已有文本（跳过转写直接对齐；文本仍建议用 --stage transcribe 的直出）")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--device", default=DEFAULT_DEVICE)
    ap.add_argument("--compute-type", default=DEFAULT_COMPUTE)
    ap.add_argument("--language", default=DEFAULT_LANG)
    ap.add_argument("--no-cond-prev", action="store_true",
                    help="关闭前文上下文（默认开；开启时 whisper 偶发段级重复幻觉）")
    ap.add_argument("--no-repeat-ngram", type=int, default=5,
                    help="禁止重复的 n-gram 长度（默认 5，抑制 whisper 重复幻觉；0=关）")
    ap.add_argument("--hf-endpoint", default=None, help="HF 镜像（如 https://hf-mirror.com）")
    args = ap.parse_args()

    if not os.path.exists(args.audio):
        sys.exit("❌ 音频不存在：%s" % args.audio)
    os.makedirs(args.out, exist_ok=True)
    if args.hf_endpoint:
        os.environ["HF_ENDPOINT"] = args.hf_endpoint
    if not shutil.which("ffmpeg"):
        print("⚠️ PATH 中未找到 ffmpeg —— 音频解码可能失败（阶段〇 同款缺口）")

    report = {"audio": os.path.basename(args.audio), "params": {
        "model": args.model, "device": args.device, "compute_type": args.compute_type,
        "language": args.language}}

    if args.stage == "transcribe":
        stage_transcribe(args, report)
    elif args.stage == "align":
        stage_align(args, report, args.text_srt or os.path.join(args.out, "segments.srt"))
    else:
        # all：**必须分两个进程**（whisperx + ctranslate2 同进程触发 cuDNN 冲突）
        base = [sys.executable, os.path.abspath(__file__), args.audio, "-o", args.out,
                "--model", args.model, "--device", args.device,
                "--compute-type", args.compute_type, "--language", args.language]
        if args.no_cond_prev:
            base += ["--no-cond-prev"]
        base += ["--no-repeat-ngram", str(args.no_repeat_ngram)]
        if args.hf_endpoint:
            base += ["--hf-endpoint", args.hf_endpoint]
        r1 = subprocess.run(base + ["--stage", "transcribe"], env=os.environ.copy())
        if r1.returncode != 0:
            sys.exit("❌ 转写阶段失败（退出码 %d）" % r1.returncode)
        align_args = base + ["--stage", "align"]
        if args.text_srt:
            align_args += ["--text-srt", args.text_srt]
        r2 = subprocess.run(align_args, env=os.environ.copy())
        if r2.returncode != 0:
            sys.exit("❌ 对齐阶段失败（退出码 %d）" % r2.returncode)
        # 汇总两阶段的报告
        for name in ("segments.srt", "words.json"):
            p = os.path.join(args.out, name)
            if not os.path.exists(p):
                sys.exit("❌ 预期产物缺失：%s" % p)
        print("采集完成：%s" % os.path.abspath(args.out))
        return 0

    with open(os.path.join(args.out, "collect_report.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(report, ensure_ascii=False, indent=1) + "\n")
    print("报告：%s" % os.path.join(args.out, "collect_report.txt"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
