# -*- coding: utf-8 -*-
"""通用文本分块脚本（SRT 与非 SRT 统一）——替代 srt_chunk.py 作为新项目的分块入口。

设计（通用文本分块格式，见 docs/PRODUCT_FORMATS.md「通用文本分块」）：
- 输入任意文本：SRT（按 cue）或非 SRT 产物（r01/r02/r03 等 txt/md，按语义单位）
- 每块 = 元数据头 + OWNED 分区（本块负责产出）+ CONTEXT 分区（前后只读衔接）
- 块边界永远在「单位」边界，不切开任何单位；单位 = cue（srt）/ 语义块（text）
- SRT 分块两种模式：
  - 默认：每 N 个 cue 一块（translate 合并/断句用）
  - --gaps：按空隙点（gap>5s）分组成「空隙组」，组内再按 N cue 分片（reflow 从 01 分块用；
    块边界优先在空隙点=语义硬边界，组内分片=窗口控制）；块标识「块G-片P」，同组片合并无缝
- 超长单位自动细分（--max-chars）为「组-片」，同组片合并时无缝拼接（解决 r01 块0 拆 0a..0f 场景）
- 确定性：同样输入同样输出；块头为机器可解析元数据行（text_merge.py 靠它归位）

用法（命令根 = Project_Main/）:
  python scripts/text_chunk.py <输入> --out <dir> [--type srt|text] [--unit 段|句|整句组]
      [--owned N] [--ctx M] [--max-chars N] [--order en-zh|zh-en] [--gaps]
  SRT  : 01_subtitle_asr_fixed.srt / 双语段 SRT（unit=cue 固定，--owned 默认 100、--ctx 默认 6）
         reflow 从 01 分块用 --gaps（空隙组优先，先验证 r00_gaps 准确性；已存在则复用，勿重复探测）
  text : r01_merged_en.txt / r02_translation_zh.txt / r03_plan.md 等（--unit 默认 段）

输出:
  <dir>/chunk_001.txt ...         每块一个文件
  <dir>/manifest.md               块清单（组/片 → 块号映射，text_merge.py 与人工核对用）

注：--inherit 已弃用（deprecated），旧块级流水线方案；新方案从 01 分块 + 块级独立流转。
"""
import argparse
import os
import re
import sys
from collections import OrderedDict

sys.stdout.reconfigure(encoding="utf-8")

TS_RE = re.compile(r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})")
SENT_ZH = re.compile(r"([^。？！]*[。？！])")          # 中文按 。？！ 切句


def parse_srt(path):
    """返回 [(idx, start, end, text), ...]；[Music] 等纯标记 cue 保留。"""
    with open(path, "r", encoding="utf-8-sig") as fh:
        text = fh.read()
    units = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        m_idx = re.fullmatch(r"\d+", lines[0])
        m_ts = TS_RE.fullmatch(lines[1])
        if not m_idx or not m_ts:
            continue
        body = lines[2:]
        txt = " | ".join(body) if len(body) > 1 else (body[0] if body else "")
        units.append((int(lines[0]), m_ts.group(1), m_ts.group(2), txt))
    return units


BRACKET_RE = re.compile(r"\[[^\]]*\]")
LONG_GAP_MS = 5000  # 长停顿阈值（与 srt_reflow_gap_scan/breaks/check_breaks 一致）


def _ts_ms(ts):
    """HH:MM:SS,mmm → 毫秒。"""
    h, m, rest = ts.split(":")
    sec, ms = rest.split(",")
    return int(h) * 3600000 + int(m) * 60000 + int(sec) * 1000 + int(ms)


def _is_marker(text):
    """纯非语音标记 cue（[Music]/[Applause] 等，去括号后无可见字符）。"""
    return BRACKET_RE.sub("", text).strip() == ""


def detect_gap_groups(units, gap_ms=LONG_GAP_MS):
    """按空隙点（相邻语音 cue 时间 gap > 阈值）把 SRT cue 分成「空隙组」。
    返回 (groups, breaks)：groups = [组号→(起始 cue 索引, 结束 cue 索引+1, cue 数)]，
    breaks = [(ia_idx, ib_idx, gap_ms), ...]（组边界处，供块内空隙点标记）。
    """
    n = len(units)
    speech = [(i, u) for i, u in enumerate(units) if not _is_marker(u[3])]
    breaks = []
    for k in range(len(speech) - 1):
        ia, ua = speech[k]
        ib, ub = speech[k + 1]
        gap = _ts_ms(ub[1]) - _ts_ms(ua[2])
        if gap > gap_ms:
            breaks.append((ia, ib, gap))
    # 空隙组 = 空隙点之间（含空隙点前的 cue）的 cue 段
    group_bounds = [0]
    for ia, ib, _ in breaks:
        group_bounds.append(ib)
    group_bounds.append(n)
    groups = []
    for g in range(len(group_bounds) - 1):
        a, b = group_bounds[g], group_bounds[g + 1]
        groups.append((a, b, b - a))
    return groups, breaks


def split_sentences(text, lang):
    """按句子标点切分文本，返回句列表（保留标点）。lang: en|zh。
    en 的 .?! 后必须跟空白或结尾才算句界（避免 1.17 / e.g. 中小数/缩写被误切）。"""
    text = " ".join(text.split())
    if not text:
        return []
    if lang == "zh":
        parts = [p for p in SENT_ZH.findall(text) if p.strip()]
        rest = SENT_ZH.sub("", text)
    else:
        parts = []
        start = 0
        for m in re.finditer(r"[.!?]+(?=\s|$)", text):
            end = m.end()
            parts.append(text[start:end].strip())
            start = end
        rest = text[start:].strip()
    if rest.strip():
        parts.append(rest.strip())
    return [p for p in parts if p.strip()]


def parse_units(path, type_, unit):
    """返回 [(gid, text), ...]（text 类型按语义单位分组）或 [(cid, start, end, text), ...]（srt）。"""
    if type_ == "srt":
        srt_units = parse_srt(path)
        # srt 返回 4 元组；调用方在此分支按 4 元组解包
        return srt_units  # type: ignore[return-value]
    raw = open(path, encoding="utf-8-sig").read()
    if unit == "整句组":
        # r03_plan.md：按 "## S<n>" 分节；组 id = "S<n>"（含合句 "S19+20"）
        blocks = re.split(r"(?m)^## (S\d+(?:\+\d+)*)", raw)
        # blocks[0] 是头部注释，之后成对 [标题, 内容]
        units = []
        for i in range(1, len(blocks) - 1, 2):
            gid = blocks[i].strip()
            body = blocks[i + 1].strip()
            if body:
                units.append((gid, body))
        return units
    if unit == "句":
        # 组 = 空隙块（空行分隔）；组内按句切分为原子单位（同组多句，合并时无缝拼接）
        segs = [s for s in re.split(r"\n\s*\n", raw) if s.strip()]
        lang = "zh" if re.search(r"[\u4e00-\u9fff]", raw) else "en"
        units = []
        for si, seg in enumerate(segs):
            for s in split_sentences(seg, lang):
                units.append(("块%d" % si, s))
        return units
    # 段（默认）：按空行分隔，组 id = "块<序号>"
    segs = [s for s in re.split(r"\n\s*\n", raw) if s.strip()]
    return [("块%d" % i, " ".join(s.split())) for i, s in enumerate(segs)]


def subdivide_group(gid, texts, max_chars):
    """把一个组的所有原子单位细分为「组-片」列表。返回 ([(gid, part, text), ...], 细分计数)。
    同组片合并时无缝拼接（见 text_merge.py）；part 在该组内全局递增。
    细分计数 = 被字符硬切的原子单位数（同组多句不算细分，只有单句超长硬切才计）。"""
    parts = []
    split_atoms = 0
    for text in texts:
        if len(text) <= max_chars:
            parts.append(text)
            continue
        split_atoms += 1
        lang = "zh" if re.search(r"[\u4e00-\u9fff]", text) else "en"
        sents = split_sentences(text, lang)
        if len(sents) <= 1:
            # 一句超长（无标点可切）：按字符硬切
            cur = text
            while len(cur) > max_chars:
                parts.append(cur[:max_chars])
                cur = cur[max_chars:]
            if cur:
                parts.append(cur)
        else:
            # 贪心打包句子到 <= max_chars 的片
            cur = ""
            for s in sents:
                if cur and len(cur) + len(s) > max_chars:
                    parts.append(cur)
                    cur = s
                else:
                    cur = (cur + " " + s) if cur else s
            if cur:
                parts.append(cur)
    return [(gid, i + 1, p) for i, p in enumerate(parts)], split_atoms


def fmt_srt_line(idx, start, end, text, order):
    body = text.split(" | ") if " | " in text else [text]
    if len(body) <= 1:
        return "c%d\t%s --> %s\t%s" % (idx, start, end, text)
    if order == "en-zh":
        return "c%d\t%s --> %s\ten: %s | zh: %s" % (idx, start, end, body[0], body[1])
    return "c%d\t%s --> %s\tzh: %s | en: %s" % (idx, start, end, body[0], body[1])


def main():
    ap = argparse.ArgumentParser(description="通用文本分块（SRT 与非 SRT 统一），输出统一块格式")
    ap.add_argument("input", nargs="?", help="输入：SRT 或 reflow 非 SRT 产物（txt/md）；--inherit 模式下可省略")
    ap.add_argument("--out", required=True, help="输出目录（不存在则创建）")
    ap.add_argument("--type", choices=("srt", "text"), default=None,
                    help="输入类型（默认自动：.srt 为 srt，否则 text）")
    ap.add_argument("--unit", choices=("段", "句", "整句组", "cue"), default="段",
                    help="text 类型的语义单位（默认 段=空行分隔；句=按标点；整句组=r03 的 ## S<n>）")
    ap.add_argument("--owned", type=int, default=None, help="每块负责的单位数 N（srt 默认 100、text 默认 1）")
    ap.add_argument("--ctx", type=int, default=None, help="块前后只读上下文单位数 M（srt 默认 6、text 默认 1）")
    ap.add_argument("--gaps", action="store_true",
                    help="srt 类型：按空隙点（gap>5s）分组成「空隙组」，组内再按 --owned 分片（reflow 从 01 分块用；块边界优先在空隙点）")
    ap.add_argument("--max-chars", type=int, default=6000,
                    help="text 类型单单位超长细分阈值（字符；默认 6000；r01 大块建议按 context_estimate 反推）")
    ap.add_argument("--order", choices=("en-zh", "zh-en"), default="en-zh", help="双语行语言顺序")
    ap.add_argument("--inherit", default=None,
                    help="【已弃用 deprecated】旧块级流水线：继承 <父块目录> 的块边界，内容换成 <--content> 结果目录的对应块。"
                         "新方案改为从 01 分块（--type srt --gaps）+ 块级独立流转，不再需要继承；此参数仅兼容旧流程，后续删除")
    ap.add_argument("--content", action="append", default=None,
                    help="--inherit 模式的内容源：上一级 subagent 结果目录（chunk_<k>.txt，保留组-片前缀）；可多次给出（r03 用双内容：r01 英文块 + r02 中文块对照）")
    args = ap.parse_args()

    if args.inherit:
        main_inherit(args)
        return

    type_ = args.type or ("srt" if args.input.lower().endswith(".srt") else "text")
    N = args.owned if args.owned is not None else (100 if type_ == "srt" else 1)
    M = args.ctx if args.ctx is not None else (6 if type_ == "srt" else 1)
    if N < 1 or M < 0:
        sys.exit("--owned 必须 >= 1、--ctx 必须 >= 0")

    units = parse_units(args.input, type_, "cue" if type_ == "srt" else args.unit)
    if not units:
        sys.exit("未解析到任何单位，请检查输入格式")
    # srt 分支：units 为 4 元组 (idx, start, end, text)；text 分支为 2 元组 (gid, text)
    if type_ == "srt":
        units = [tuple(u) for u in units]  # type: ignore[assignment]
        for u in units:
            assert len(u) == 4, "SRT 单位应为 4 元组 (idx,start,end,text)"

    os.makedirs(args.out, exist_ok=True)

    # 展开为「最小单位」序列：text 按组聚合后细分（同组全局 part 编号）；
    # srt 默认每 cue 一个最小单位；--gaps 时按空隙组分片（组-片标识）
    # items 统一存 (组标识, part, 行文本)；text 行文本自带「组-片\t」前缀
    items = []  # (组标识, part, 行文本)
    n_split = 0

    def _tl(gid, part):
        return gid if part == 1 else "%s-片%d" % (gid, part)

    if type_ == "srt":
        if args.gaps:
            groups, breaks = detect_gap_groups(units)
            for g, (a, b, cnt) in enumerate(groups):
                gid = "块%d" % g
                for part, i in enumerate(range(a, b, N), start=1):
                    for idx, start, end, text in units[i:min(i + N, b)]:
                        items.append((gid, part, fmt_srt_line(idx, start, end, text, args.order)))
        else:
            for idx, start, end, text in units:
                items.append(("c%d" % idx, 1, fmt_srt_line(idx, start, end, text, args.order)))
    else:
        # 按组聚合（句模式同组多原子单位 → part 组内连续）
        by_gid = OrderedDict()
        for gid, text in units:
            by_gid.setdefault(gid, []).append(text)
        for gid, texts in by_gid.items():
            sub_items, cnt = subdivide_group(gid, texts, args.max_chars)
            items.extend((gid, part, "%s\t%s" % (_tl(gid, part), txt)) for gid, part, txt in sub_items)
            n_split += cnt

    # 分块：
    #   srt --gaps：块边界 = 「空隙组-片」边界（片边界即块边界，不再按 N 重切）
    #   srt 无 --gaps / text：每 N 个最小单位一块
    chunk_gids = {}  # k -> [组-片标识...]（--gaps 模式用）
    if type_ == "srt" and args.gaps:
        # 按 (gid, part) 连续段分组 → 每片一块
        chunks = []
        cur_gid, cur_part = None, None
        cur = []
        for gid, part, line in items:
            if (gid, part) != (cur_gid, cur_part):
                if cur:
                    chunks.append(cur)
                    chunk_gids[len(chunks)] = ["%s" % _tl(cur_gid, cur_part)]
                cur = [line]
                cur_gid, cur_part = gid, part
            else:
                cur.append(line)
        if cur:
            chunks.append(cur)
            chunk_gids[len(chunks)] = ["%s" % _tl(cur_gid, cur_part)]
        chunk_ranges = []  # (start, end) 用于 CONTEXT 定位
        pos = 0
        for c in chunks:
            chunk_ranges.append((pos, pos + len(c)))
            pos += len(c)
    else:
        chunks = []
        for i in range(0, len(items), N):
            chunks.append([line for _g, _p, line in items[i:i + N]])
        chunk_ranges = [(i, min(i + N, len(items))) for i in range(0, len(items), N)]
    total = len(chunks)

    def fmt_label(gid, part):
        return gid if part == 1 else "%s-片%d" % (gid, part)

    def owned_desc(owned, k):
        """块头负责描述：srt --gaps 显示空隙组-片；srt 无 gaps 显示 cue 区间；text 显示组-片列表去重。"""
        if type_ == "srt":
            if args.gaps:
                return ", ".join(chunk_gids.get(k, []))
            cids = []
            for line in owned:
                m = re.match(r"c(\d+)", line)
                if m:
                    cids.append(int(m.group(1)))
            if cids:
                return "c%d-c%d" % (min(cids), max(cids))
            return "c%d" % len(owned)
        seen = []
        for line in owned:
            lbl = line.split("\t")[0] if "\t" in line else line
            if lbl not in seen:
                seen.append(lbl)
        return ", ".join(seen)

    manifest = ["# CHUNK MANIFEST - %s" % os.path.basename(args.input),
                "- TYPE: %s / UNIT: %s / OWNED: %d / CTX: %d" % (type_, args.unit if type_ == "text" else "cue", N, M),
                "- TOTAL UNITS: %d / CHUNKS: %d" % (len(items), total), ""]
    for k, chunk in enumerate(chunks):
        owned = chunk
        a0, b0 = chunk_ranges[k]
        before = [line for _g, _p, line in items[max(0, a0 - M):a0]]
        after = [line for _g, _p, line in items[b0:min(len(items), b0 + M)]]
        lines = ["# CHUNK %d/%d  SRC: %s  TYPE: %s  UNIT: %s  OWN: %s  CTX: BEFORE %d AFTER %d" %
                 (k + 1, total, os.path.basename(args.input), type_,
                  args.unit if type_ == "text" else "cue", owned_desc(owned, k + 1), len(before), len(after))]

        if type_ == "text":
            # text 类型：单元间空行分隔，单元首行 = 「组-片\t」前缀，内容可多行（r03 markdown）
            if before:
                lines.append("## BEFORE")
                for line in before:
                    lines.append(line)
                    lines.append("")
            lines.append("## OWNED")
            for line in owned:
                lines.append(line)
                lines.append("")
            if after:
                lines.append("## AFTER")
                for line in after:
                    lines.append(line)
                    lines.append("")
        else:
            # srt 类型：每行一条 cue（行自带 cN\t时间\t文本）
            if before:
                lines.append("## BEFORE")
                lines.extend(before)
            lines.append("## OWNED")
            lines.extend(owned)
            if after:
                lines.append("## AFTER")
                lines.extend(after)
        fname = os.path.join(args.out, "chunk_%03d.txt" % (k + 1))
        with open(fname, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines) + "\n")
        manifest.append("- chunk_%03d: OWN %s" % (k + 1, owned_desc(owned, k + 1)))

    with open(os.path.join(args.out, "manifest.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(manifest) + "\n")

    print("类型: %s / 单位: %s" % (type_, args.unit if type_ == "text" else "cue"))
    print("最小单位数: %d / 分块数: %d（每块负责 %d，上下文 %d）" % (len(items), total, N, M))
    print("输出目录: %s" % os.path.abspath(args.out))
    if type_ == "srt" and args.gaps:
        ng = len(detect_gap_groups(units)[0])
        print("空隙组: %d 个（块边界优先在空隙点，组内按 %d cue 分片）" % (ng, N))
    if type_ == "text" and n_split:
        print("超长单位硬切: %d 个原子单位被按字符拆为多片（合并时同组无缝拼接）" % n_split)


def main_inherit(args):
    """块级流水线：继承 <args.inherit> 的块边界，内容换成 <args.content> 结果目录的对应块。
    单内容源：r02（继承 r01 块边界、内容 = r01 补标点结果）。
    多内容源：r03（继承 r02 边界、内容 = [r01 英文块, r02 中文块] 对照，供分句语义对应）。
    中间不拼全文——直到校验/审核前才 text_merge.py 拼接。"""
    if not args.content:
        sys.exit("--inherit 模式必须同时给 --content <上一级结果目录>（可多个）")
    contents = args.content if isinstance(args.content, list) else [args.content]
    parent_dir, out_dir = args.inherit, args.out
    os.makedirs(out_dir, exist_ok=True)

    # 收集父块文件（按序号）
    parent_files = {}
    for fn in sorted(os.listdir(parent_dir)):
        m = re.fullmatch(r"chunk_(\d{3})\.txt", fn)
        if m:
            parent_files[int(m.group(1))] = os.path.join(parent_dir, fn)
    if not parent_files:
        sys.exit("父块目录下未找到 chunk_*.txt")
    total = max(parent_files)

    manifest = ["# CHUNK MANIFEST (INHERIT %s) - SOURCES %s" %
                (os.path.basename(parent_dir), ", ".join(os.path.basename(c) for c in contents)),
                "- CHUNKS: %d / SOURCES: %d" % (total, len(contents)), ""]

    for k in range(1, total + 1):
        # 读父块头（复用元数据）
        head = None
        with open(parent_files[k], encoding="utf-8") as fh:
            parent_text = fh.read()
        for ln in parent_text.split("\n"):
            m = re.match(r"^# CHUNK (\d+)/(\d+)\s+SRC: (.+?)\s+TYPE: (srt|text)\s+UNIT: (.+?)\s+OWN: (.+?)\s+CTX: (.+?)$", ln)
            if m:
                head = m.groups()
                break
        if head is None:
            sys.exit("父块 %d 无有效块头" % k)
        p_total, p_src, p_type, p_unit, p_owned, p_ctx = int(head[1]), head[2], head[3], head[4], head[5], head[6]

        lines = ["# CHUNK %d/%d  SRC: %s  TYPE: %s  UNIT: %s  OWN: %s  CTX: BEFORE 1 AFTER 1" %
                 (k, total, os.path.basename(parent_dir), p_type, p_unit, p_owned)]
        if p_type == "text":
            if k > 1:
                lines.append("## BEFORE")
                for ci, cdir in enumerate(contents):
                    bf = os.path.join(cdir, "chunk_%03d.txt" % (k - 1))
                    if os.path.exists(bf):
                        if len(contents) > 1:
                            lines.append("# SOURCE %d: %s" % (ci + 1, os.path.basename(cdir)))
                        lines.append("--- PREV (chunk_%03d) ---" % (k - 1))
                        lines.append(open(bf, encoding="utf-8").read().rstrip("\n"))
            lines.append("## OWNED")
            # 多内容源按顺序排（r03：先英文块后中文块），单内容源（r02）直接一段
            for ci, cdir in enumerate(contents):
                content_file = os.path.join(cdir, "chunk_%03d.txt" % k)
                if not os.path.exists(content_file):
                    sys.exit("source chunk missing: %s" % content_file)
                content = open(content_file, encoding="utf-8").read().rstrip("\n")
                if len(contents) > 1:
                    lines.append("=== SOURCE %d: %s ===" % (ci + 1, os.path.basename(cdir)))
                lines.append(content)
                lines.append("")
            if k < total:
                lines.append("## AFTER")
                for ci, cdir in enumerate(contents):
                    af = os.path.join(cdir, "chunk_%03d.txt" % (k + 1))
                    if os.path.exists(af):
                        if len(contents) > 1:
                            lines.append("# SOURCE %d: %s" % (ci + 1, os.path.basename(cdir)))
                        lines.append("--- NEXT (chunk_%03d) ---" % (k + 1))
                        lines.append(open(af, encoding="utf-8").read().rstrip("\n"))
        else:
            if k > 1:
                lines.append("## BEFORE")
                for ci, cdir in enumerate(contents):
                    bf = os.path.join(cdir, "chunk_%03d.txt" % (k - 1))
                    if os.path.exists(bf):
                        lines.append("--- PREV ---")
                        lines.append(open(bf, encoding="utf-8").read().rstrip("\n"))
            lines.append("## OWNED")
            for ci, cdir in enumerate(contents):
                content_file = os.path.join(cdir, "chunk_%03d.txt" % k)
                content = open(content_file, encoding="utf-8").read().rstrip("\n")
                if len(contents) > 1:
                    lines.append("=== SOURCE %d: %s ===" % (ci + 1, os.path.basename(cdir)))
                lines.append(content)
            if k < total:
                lines.append("## AFTER")
                for ci, cdir in enumerate(contents):
                    af = os.path.join(cdir, "chunk_%03d.txt" % (k + 1))
                    if os.path.exists(af):
                        lines.append("--- NEXT ---")
                        lines.append(open(af, encoding="utf-8").read().rstrip("\n"))
        with open(os.path.join(out_dir, "chunk_%03d.txt" % k), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines) + "\n")
        manifest.append("- chunk_%03d: OWN %s" % (k, p_owned))

    with open(os.path.join(out_dir, "manifest.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(manifest) + "\n")
    print("继承分块: %d 块（父块 %s → 内容源 %s → 输出 %s）" %
          (total, os.path.basename(parent_dir),
           ", ".join(os.path.basename(c) for c in contents), os.path.abspath(out_dir)))


if __name__ == "__main__":
    main()
