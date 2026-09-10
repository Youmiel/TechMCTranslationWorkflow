# -*- coding: utf-8 -*-
"""时间轴源头固化（新 reflow2 工作流）：r01 补标点英文切 E 句 + 每句固化真实时间（只读真值锚）

背景（reflow2 = 时间轴源头固化设计）：
现 reflow 的 r01_results 是块内整段连续英文（task-punctuate 不带 cue 前缀），翻译后中文句重建时间轴
靠「整句 EN 去 01 全文子串搜索猜时间」+ 共享 cue 切分 + 预测点。本脚本把时间轴**在源头固化**：
补标点后按 .?! 切 E1..En，每句用与消费端 reflow 同构的 char→cue 映射（srt_reflow_core.io.build_full：
norm 去空格、cue 无缝拼接）在 01 精确锚定 → 固化时间戳。E 句 = 只读真值锚，下游中文句通过对齐继承，
不再靠猜。

锚定策略（与消费端 anchor/resolve_shared_cues 同构、零漂移）：
- 每块 E 句在**块内 OWNED cue 子集**内**顺序锚定**（running cursor 顺延，保 E 句次序、防 Yeah/Okay 等
  短句跨 cue 重复非唯一误配）——原型实测 m5SvZsN chunk_001：49 E 句 48 命中、唯一 MISS 为内嵌
  [laughter] 标记（剥离后命中）
- 相邻 E 句**共享 cue** → 中间按两侧字符占比估算切分点（复用 anchor.resolve_shared_cues，与现 reflow
  整句层同构）——固化层即把共享 cue 切清，下游继承零重叠
- 块内未命中（跨块补全句/区间判断误差）→ 全局兜底（标 global；不计块内共享切分）

输入/输出（新工作流独立产物目录 reflow2/；chunks 复用 text_chunk 分块、r01_results 复用补标点产物）：
- 输入：`reflow2/chunks/`（cue 结构，含时间戳；OWNED 为负责段）+ `reflow2/r01_results/`（补标点整段，衔接归位后）
- 输出：`reflow2/en_timeline/chunk_<k>.txt`（每 E 句一行：`E<n>\t<start> --> <end>\t<c<a>-c<b>>\t<文本>`）
  en_timeline 为**纯脚本内部产物**（机器消费，供回填继承时间；不面向人工复核格式）。

用法（命令根 = Project_Main/）：
  python scripts/srt_reflow2_etimeline.py reflow2/chunks/ reflow2/r01_results/ --srt <工作目录>/01_subtitle_asr_fixed.srt -o reflow2/en_timeline/
退出码：0 = 全部块固化完成；1 = 有 E 句锚定失败（MISS，需处理措辞/标记残留）。
"""
import argparse
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

from srt_reflow_common import collect_chunk_files, parse_owned_cue_range, BRACKET_RE, fmt
from srt_reflow_presplit import split_en

PM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PM not in sys.path:
    sys.path.insert(0, PM)
from scripts.srt_reflow_core.io import norm, parse_srt, build_full
from scripts.srt_reflow_core.anchor import resolve_shared_cues


def main():
    ap = argparse.ArgumentParser(description="时间轴源头固化：r01 英文切 E 句 + 每句固化真实时间（en_timeline，只读真值锚）")
    ap.add_argument("chunks_dir", help="分块骨架目录：reflow2/chunks/（cue 结构，OWNED 为负责段）")
    ap.add_argument("r01_dir", help="补标点产物目录：reflow2/r01_results/（整段英文，衔接归位后）")
    ap.add_argument("--srt", required=True, help="01_subtitle_asr_fixed.srt（cue 时间戳，锚定真值源）")
    ap.add_argument("-o", "--out", required=True, help="输出目录：reflow2/en_timeline/")
    ap.add_argument("--verbose", action="store_true", help="展开打印每块细节")
    args = ap.parse_args()

    # 01 语音全文（parse_srt 已剔除纯标记 cue；build_full 与消费端 reflow 同构）
    all_cues = parse_srt(args.srt)
    all_full, all_mapping, all_offsets = build_full(all_cues)
    print(f"01 语音 cue {len(all_cues)} 条，full {len(all_full)} 字符（parse_srt 已剔除纯标记 cue）")

    chunk_blocks = collect_chunk_files(args.chunks_dir)
    r01_blocks = collect_chunk_files(args.r01_dir)
    if not chunk_blocks:
        sys.exit(f"❌ chunks 目录无块文件：{args.chunks_dir}")
    os.makedirs(args.out, exist_ok=True)

    keys = sorted(set(chunk_blocks) & set(r01_blocks))
    if not keys:
        sys.exit("❌ chunks 与 r01_results 无共同块号（先跑补标点）")
    total_e = total_miss = 0
    for k in keys:
        with open(r01_blocks[k], encoding="utf-8") as fh:
            es = split_en(fh.read())
        owned = parse_owned_cue_range(chunk_blocks[k])
        # 块内 OWNED cue 子集 + 子 full（锚定域，防跨块重复误配）
        bcues = [c for c in all_cues if owned[0] <= c["idx"] <= owned[1]] if owned else []
        bfull, bmapping, boffsets = build_full(bcues) if bcues else ("", [], [])

        # 每 E 句锚定 → info dict：{key, text, kind(block/global/miss/skip), a(anchor|None), note}
        infos = []
        anchors = []   # 块内命中的 E 句，按顺序（供共享 cue 切分；si/ei 为 bcues 下标）
        cursor = 0     # 块内顺序锚定游标（保 E 句次序）
        for i, etext in enumerate(es, 1):
            clean = BRACKET_RE.sub("", etext).strip()
            n = norm(clean)
            key = f"E{i}"
            if not n:
                infos.append({"key": key, "text": etext.strip(), "kind": "skip", "a": None, "note": "剥离标记后为空"})
                continue
            p = bfull.find(n, cursor) if bcues else -1
            if p != -1:
                si, ei = bmapping[p], bmapping[p + len(n) - 1]
                a = {"key": key, "start": bcues[si]["start"], "end": bcues[ei]["end"],
                     "si": si, "ei": ei, "pos": p, "pos_end": p + len(n) - 1}
                infos.append({"key": key, "text": etext.strip(), "kind": "block", "a": a, "note": None})
                anchors.append(a)
                cursor = p + len(n)   # 顺延：下一 E 句从本句之后找
                continue
            # 块内游标后未命中：全局兜底（跨块补全句/区间判断误差）
            gp = all_full.find(n)
            if gp != -1:
                gsi, gei = all_mapping[gp], all_mapping[gp + len(n) - 1]
                a = {"key": key, "start": all_cues[gsi]["start"], "end": all_cues[gei]["end"],
                     "si": None, "ei": None, "pos": None, "pos_end": None}
                infos.append({"key": key, "text": etext.strip(), "kind": "global", "a": a, "note": None})
                continue
            infos.append({"key": key, "text": etext.strip(), "kind": "miss", "a": None, "note": "锚定失败"})

        # 相邻 E 句共享 cue 中间断句估算切分（resolve_shared_cues 直接改 anchor start/end）
        resolve_shared_cues(anchors, bcues, boffsets, [])

        out_lines = []
        for info in infos:
            kk, a = info["key"], info["a"]
            if info["kind"] == "block":
                c1, c2 = bcues[a["si"]], bcues[a["ei"]]
                out_lines.append(f"{kk}\t{fmt(a['start'])} --> {fmt(a['end'])}\tc{c1['idx']}-c{c2['idx']}\t{info['text']}")
            elif info["kind"] == "global":
                out_lines.append(f"{kk}\t{fmt(a['start'])} --> {fmt(a['end'])}\t-\t{info['text']}\t(global)")
            elif info["kind"] == "miss":
                out_lines.append(f"{kk}\tMISS\t-\t{info['text']}\t{info['note']}")
            else:
                out_lines.append(f"{kk}\t-\t-\t{info['text']}\t{info['note']}")
        with open(os.path.join(args.out, "chunk_%03d.txt" % k), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(f"# en_timeline chunk_{k:03d} — E 句固化时间（只读真值锚；与 r01 按 .?! 切句一致）\n")
            fh.write("\n".join(out_lines) + "\n")

        n_miss = sum(1 for r in infos if r["kind"] == "miss")
        n_skip = sum(1 for r in infos if r["kind"] == "skip")
        n_glob = sum(1 for r in infos if r["kind"] == "global")
        total_e += len(es)
        total_miss += n_miss
        if args.verbose or n_miss:
            print(f"   chunk_{k:03d}: E {len(es)} 句 / 锚定失败 {n_miss} / 全局兜底 {n_glob} / 跳过 {n_skip}"
                  + (f"（OWNED cue {owned}）" if owned else ""))
    print(f"✅ en_timeline 固化完成：{len(keys)} 块 / {total_e} E 句 → {args.out}；锚定失败 {total_miss}")
    if total_miss:
        print("   锚定失败 = 补标点措辞与 01 不一致 / 标记残留未剥离净——需检查对应 E 句（回填继承时间会缺该句）")
        return 1
    return 0


if __name__ == "__main__":
    main()
