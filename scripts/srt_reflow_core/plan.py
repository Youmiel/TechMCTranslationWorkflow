# -*- coding: utf-8 -*-
"""r03 方案解析（parse_r03）与写时即合规预检（check_r03 / check_r03_blocks，含 ZH 忠实校验）"""
import re
import sys
from collections import Counter
from pathlib import Path

from .io import norm, text_width, parse_srt, build_full
from .allocate import (
    cjk_reading_ms,
    estimate_unit_durations,
    MIN_FRAG_MS,
    READING_MISMATCH_RATIO,
    READING_MIN_GAP_MS,
)
from .anchor import resolve_shared_cues, unit_anchor_in_sentence

# 译文忠实校验：去空白/标点，留中文字符与字母数字（断点标点不计入比较）
ZH_KEEP_RE = re.compile(r"[^\u4e00-\u9fff0-9a-zA-Z]")


def zh_content(s):
    """去空白/标点，留中文字符（ZH 忠实校验基准：断句只插标点 → 内容字符不变）"""
    return ZH_KEEP_RE.sub("", s)


class Sentence:
    """r03 整句组：S<n>（或合句 S<n+m>）"""

    def __init__(self, key, en, zh, rel, units):
        self.key = key          # 如 S1 / S19+20
        self.en = en            # 整句英文全文（锚定用）
        self.zh = zh            # 整句中文（对照）
        self.rel = rel          # 1:1 / 1:n / n:1
        self.units = units      # [(unit_key, en_frag, zh_frag), ...]


def parse_r03(path):
    """解析 r03_plan.md → [Sentence]"""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    sentences = []
    cur = None
    for line in lines:
        line = line.rstrip()
        m = re.match(r"^##\s*(S[\d+]+)\s*$", line)
        if m:
            cur = {"key": m.group(1), "en": None, "zh": None, "rel": None, "units": []}
            sentences.append(cur)
            continue
        if cur is None:
            continue
        m = re.match(r"^- EN:\s?(.*)$", line)
        if m and cur["en"] is None and not cur["units"]:
            cur["en"] = m.group(1)
            continue
        m = re.match(r"^- ZH:\s?(.*)$", line)
        if m and cur["zh"] is None and not cur["units"]:
            cur["zh"] = m.group(1)
            continue
        m = re.match(r"^- 关系:\s?(.*)$", line)
        if m and cur["rel"] is None:
            cur["rel"] = m.group(1).strip()
            continue
        m = re.match(r"^###\s*(S[\d+]+[a-z])$", line)
        if m:
            cur["units"].append({"key": m.group(1), "en": None, "zh": None})
            continue
        if cur["units"]:
            u = cur["units"][-1]
            m = re.match(r"^- EN:\s?(.*)$", line)
            if m and u["en"] is None:
                u["en"] = m.group(1)
                continue
            m = re.match(r"^- ZH:\s?(.*)$", line)
            if m and u["zh"] is None:
                u["zh"] = m.group(1)

    out = []
    for s in sentences:
        if s["en"] is None or s["rel"] is None:
            raise ValueError(f"r03 解析失败（缺 EN/关系）: {s['key']}")
        units = []
        for u in s["units"]:
            if u["en"] is None or u["zh"] is None:
                raise ValueError(f"r03 解析失败（子单元缺 EN/ZH）: {u['key']}")
            units.append((u["key"], u["en"], u["zh"]))
        out.append(Sentence(s["key"], s["en"], s["zh"], s["rel"], units))
    return out


def check_r03(r03_path, srt_path, r02_path=None, cjk_speed=5.0, check_frag=True, check_mismatch=True,
              cue_range=None, r02_text=None):
    """r03 写时即合规预检（步骤 4 产出后、步骤 5 回填前必跑）：

    - 锚定唯一性：每个整句 EN 在 01 唯一命中（未命中 / 重复命中均报告）
      ——块级（cue_range=(cmin,cmax)）时锚定缩到块内 cue 区间，避免跨块重复误报
    - 拆句互斥性：1:n 拆句子单元 EN 拼接 == 整句 EN
    - 行宽：每个译文单元中文视觉宽度 ≤ 26（软 22 / 硬 26，与 srt_check_width 一致；>26 硬违规）
    - ZH 忠实性（需 r02）：r03 整句 ZH 拼接（去标点空白）== r02 定稿（块级时缩到该块 r02 段）——断句只允许插断点标点，不得改写译文
    - 碎片预检（预警，不阻断；--no-frag 可关）：1:n 整句按中文阅读速度（--cjk-speed）粗估子单元时长，
      <1s 的提示 Agent 在 r03 阶段就合并/调整切分点（长句不碎，避免回填后返工）
    - 中英失配预估（预警，不阻断；--no-mismatch 可关）：1:n 整句按单元级 cue 锚定 + 共享 cue 切分预估
      各单元实际时长，文本量大的中文单元只拿到很短英文 cue（倒装/中英时长差）时提示 Agent
      调整切分点或依赖回填阅读插值

    有硬违规输出清单并返回 1（打回 r03 改写），仅存疑预警则通过并打印提示（Agent 智能判断）。全部通过返回 0。
    """
    sentences = parse_r03(r03_path)
    cues = parse_srt(srt_path)
    if cue_range:
        cmin, cmax = cue_range
        cues = [c for c in cues if cmin <= c["idx"] <= cmax]
        if not cues:
            print(f"❌ 块级 check-r03：cue 区间 c{cmin}-c{cmax} 无语音 cue（可能整块为标记），跳过锚定检查")
    full, mapping, cue_offsets = build_full(cues)
    problems = []
    warnings = []
    anchors = []
    for s in sentences:
        n = norm(s.en)
        pos = full.find(n)
        if pos == -1:
            problems.append(f"❌ 整句 {s.key} 锚定失败（{'块内 c%d-c%d' % cue_range if cue_range else '01 全文'}未找到）——回填将走顺序兜底，须修正措辞")
            anchors.append(None)
        else:
            if full.find(n, pos + 1) != -1:
                problems.append(f"⚠️ 整句 {s.key} 非唯一命中（{'块内' if cue_range else '01 全文'}出现 ≥2 次）——回填将取第一处，须保证唯一或接受")
            anchors.append({
                "key": s.key,
                "start": cues[mapping[pos]]["start"],
                "end": cues[mapping[pos + len(n) - 1]]["end"],
                "si": mapping[pos],
                "ei": mapping[pos + len(n) - 1],
                "pos": pos,
                "pos_end": pos + len(n) - 1,
            })
        if s.rel == "1:n" and s.units:
            joined = "".join(norm(u[1]) for u in s.units)
            if joined != n:
                problems.append(f"❌ 拆句 {s.key} 子单元 EN 拼接 ≠ 整句 EN（互斥性破坏）——双语英文行将错位")
        units = s.units or [(s.key, s.en, s.zh)]
        for u in units:
            w = text_width(u[2])
            if w > 26:
                problems.append(f"📏 行宽 {w:.1f}（>26 硬）{u[0]}: {u[2]}")

    # 括号/引号配对预警（存疑，不阻断）：单元内不成对 = 括号被拆 / 引号归属漂移（S24/S61e/S70c 类）
    for s in sentences:
        units = s.units or [(s.key, s.en, s.zh)]
        for u in units:
            zh = u[2]
            for o, c in (("（", "）"), ("(", ")")):
                if zh.count(o) != zh.count(c):
                    warnings.append(f"🧩 括号不配对 {u[0]}: 「{zh}」含 {o}×{zh.count(o)}/{c}×{zh.count(c)}——括号整体应归同一单元（可能被切在括号中间）")
                    break
            if zh.count('"') % 2 == 1 or zh.count("“") != zh.count("”"):
                warnings.append(f"🧩 引号不配对 {u[0]}: 「{zh}」引号不成对——引号归属可能漂移（整句中间的引号随其后中文文本归属，不得丢失/错位）")

    # 跨整句共享 cue 切分（预估贴近回填：相邻整句共享 cue 时末单元被裁到共享切分点，S6/S7 实证）
    resolve_shared_cues([a for a in anchors if a is not None], cues, cue_offsets, [])

    # 回填前预估预警（碎片 + 中英失配，均为存疑、Agent 智能判断）
    for s, a in zip(sentences, anchors):
        if a is None:
            continue
        units = s.units or [(s.key, s.en, s.zh)]
        if s.rel != "1:n" or len(units) < 2 or cjk_speed <= 0:
            continue
        start, end = a["start"], a["end"]
        span = end - start
        # 碎片预检：整句 span 按阅读比例粗估子单元时长，<1s 预警（长句切碎风险）
        if check_frag and span > 0:
            weights = [max(1, cjk_reading_ms(u[2], cjk_speed)) for u in units]
            total = sum(weights) or 1
            for u, w in zip(units, weights):
                est = span * w / total
                if est < MIN_FRAG_MS:
                    warnings.append(
                        f"🔪 碎片预检 {u[0]}: 整句 {s.key} span {span}ms 按阅读比例约 {est:.0f}ms"
                        f" <{MIN_FRAG_MS}ms——建议在 r03 合并相邻单元或调整切分点（长句不碎）"
                    )
        # 中英失配预估：单元级 cue 锚定 + 共享 cue 切分预估实际时长，对比中文阅读所需
        # ——倒装/中英时长差：文本量大的中文单元可能只拿到很短的英文 cue（读不完）
        if check_mismatch:
            ucs = unit_anchor_in_sentence(s, a, full, mapping, cues)
            if ucs is not None:
                ests = estimate_unit_durations(s, a, units, ucs, cues, cue_offsets)
                if ests:
                    for u, est in zip(units, ests):
                        d = int(est[1] - est[0])
                        need = cjk_reading_ms(u[2], cjk_speed)
                        if need > 0 and d < need * READING_MISMATCH_RATIO \
                                and (need * READING_MISMATCH_RATIO - d) >= READING_MIN_GAP_MS:
                            warnings.append(
                                f"📖 中英失配预估 {u[0]}: 中文「{u[2]}」阅读需 {need}ms，英文 cue 预估仅 {d}ms"
                                f"（<阅读所需×{READING_MISMATCH_RATIO}，失配 {int(need * READING_MISMATCH_RATIO - d)}ms）"
                                f"——倒装/时长不均，整句 {s.key}：可调整 r03 切分点或依赖回填阅读插值"
                            )
    # 拆句单元层一致性：1:n 子单元 ZH 拼接 == 整句 ZH（去标点后逐字相等）——拦截子单元层译文改写
    for s in sentences:
        if s.rel == "1:n" and len(s.units) > 1:
            joined = zh_content("".join(u[2] for u in s.units))
            whole = zh_content(s.zh)
            if joined != whole:
                problems.append(
                    f"❌ 拆句 {s.key} 子单元 ZH 拼接 ≠ 整句 ZH（断句不得改写译文）"
                    f"——子单元「{joined}」vs 整句「{whole}」"
                )
    # ZH 忠实性：r03 整句 ZH（s.zh）与 r02 定稿做字符多集比较
    # ——断句只允许插标点/重排口语词归属，不得增删或改写任何字（净增删即违规）
    if r02_path or r02_text:
        r02_norm = zh_content(r02_text if r02_text is not None else Path(r02_path).read_text(encoding="utf-8"))
        r03_norm = zh_content("".join(s.zh for s in sentences))
        c2, c3 = Counter(r02_norm), Counter(r03_norm)
        if c2 != c3:
            added = "".join(sorted((c3 - c2).elements())) or "—"
            removed = "".join(sorted((c2 - c3).elements())) or "—"
            problems.append(
                f"❌ 译文忠实性：r03 译文单元 ZH ≠ r02 定稿（断句不得增删/改写字，仅可插标点）"
                f"；r03 多出「{added}」/ r02 有而 r03 缺「{removed}」"
            )
    if warnings:
        print(f"🔪 check-r03 存疑预警 {len(warnings)} 条（估算值，供 Agent 判断：合并相邻单元 / 调整切分点 / 接受 / 依赖回填插值）:")
        for w in warnings:
            print("  " + w)
    if not problems:
        print(f"✅ check-r03 通过：{len(sentences)} 整句，锚定唯一 / 互斥 / 行宽 / ZH忠实均合规")
        return 0
    print(f"❌ check-r03 发现 {len(problems)} 处问题（r03 需改写后重跑）:")
    for p in problems:
        print("  " + p)
    return 1


def check_r03_blocks(r03_dir, srt_path, chunks_dir, r02_dir, cjk_speed=5.0,
                     check_frag=True, check_mismatch=True):
    """块级 check-r03：逐块校验（r03_results/ + chunks/ 骨架 + r02_results/）。

    - 每块 = 一个空隙组-片（chunks/ 的块 ↔ cue 区间）；锚定缩到块内 cue 区间
    - ZH 忠实缩到该块 r02 段（r02_results/ 对应块）
    - 拼回 r03_plan.md 后的整段 check-r03（锚定 01 全文 + 全量 r02）仍建议最后跑一次兜底
    """
    import os
    import re
    from pathlib import Path

    # 收集块文件（按序号），解析块 ↔ cue 区间
    chunk_files = {}
    for fn in sorted(os.listdir(chunks_dir)):
        m = re.fullmatch(r"chunk_(\d{3})\.txt", fn)
        if m:
            chunk_files[int(m.group(1))] = os.path.join(chunks_dir, fn)
    if not chunk_files:
        sys.exit("chunks 目录下未找到 chunk_*.txt（需 text_chunk.py 生成）")
    total = max(chunk_files)

    n_block_err = 0
    n_blocks = 0
    for k in sorted(chunk_files):
        r03_blk = os.path.join(r03_dir, "chunk_%03d.txt" % k)
        r02_blk = os.path.join(r02_dir, "chunk_%03d.txt" % k)
        if not os.path.exists(r03_blk):
            print(f"❌ chunk_{k:03d}: 无 r03 结果文件，跳过")
            n_block_err += 1
            continue
        # 解析块 cue 区间（OWNED 行 cN 前缀）
        cids = []
        in_owned = False
        for ln in open(chunk_files[k], encoding="utf-8").read().split("\n"):
            if ln.startswith("## "):
                in_owned = ln.startswith("## OWNED")
                continue
            if in_owned:
                mm = re.match(r"c(\d+)\t", ln)
                if mm:
                    cids.append(int(mm.group(1)))
        if not cids:
            print(f"⚠️ chunk_{k:03d}: 无 OWNED cue 区间，跳过（可能整块为标记）")
            continue
        cue_range = (min(cids), max(cids))
        r02_text = Path(r02_blk).read_text(encoding="utf-8") if os.path.exists(r02_blk) else None
        print(f"--- chunk_{k:03d} (c{cue_range[0]}-c{cue_range[1]}) ---")
        rc = check_r03(r03_blk, srt_path, r02_path=None, cjk_speed=cjk_speed,
                       check_frag=check_frag, check_mismatch=check_mismatch,
                       cue_range=cue_range, r02_text=r02_text)
        n_blocks += 1
        if rc != 0:
            n_block_err += 1
    print("=" * 60)
    if n_block_err:
        print(f"❌ 块级 check-r03 失败：{n_block_err}/{n_blocks} 块异常（打回对应块 r03 改写）")
        return 1
    print(f"✅ 块级 check-r03 通过：{n_blocks} 块全部合规（锚定缩块内 / ZH 忠实缩块内）")
    print("   ⚠️ 拼回 r03_plan.md 后仍建议整段 check-r03 兜底（锚定 01 全文唯一性）")
    return 0
