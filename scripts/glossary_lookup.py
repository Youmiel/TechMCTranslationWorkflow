#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查询 / 扫描术语的中文译名（只读，不修改任何文件）。

按 skill 的 L1 → L1.5 → L2 顺序在项目术语源中检索：
  L1   knowledge/01_terminology/*.csv、.cache/mojang/redstone.csv
  L1.5 .cache/mojang/{blocks,items,entities,misc}.csv
  L2   .cache/glossary/*.csv

子命令：
  query <term> [<term> ...]                   查单个/多个术语译名（词→译名，词典式）
  scan <file> [--categories c1,c2] [--levels L1,L2] [--out f]
                                              扫字幕/块文本，找出出现的已收录术语
                                              （文本→命中词，机械匹配，不依赖"像不像术语"判断）

scan 默认扫 L1+L2（项目已确认译名 + 社区术语），L1.5（Mojang 官方，含大量常用词
water/sand/thing 等易制造噪声）通过 --levels L1,L1.5,L2 按需加入。

--categories 只按文件名过滤 L2（.cache/glossary/<文件名>.csv）；L2 文件名与
glossary_categories.yaml 分类是两套命名，部分重叠但**不对应**（L2 另有 general/other/
people 等 yaml 没有的文件）——勿假设二者完全对应，直接按实际文件名传参即可。
scan 本身不做类别预测：选哪些 L2 文件由 Agent 按语义判断（阶段〇，可多个），
这里只做按名过滤。
L1 始终全量加载（体量小，且其文件分类 common/game_system/redstone_concepts/...
又是另一套命名，不受 --categories 影响）；L1.5 的 redstone/blocks/items/entities/misc
是 Mojang 数据分类，再一套命名，只受 --levels 控制。

用法:
  python scripts/glossary_lookup.py query "Item Sorter" "Hopper"
  python scripts/glossary_lookup.py scan _work/<视频>/01_subtitle_asr_fixed.srt \
      --categories storage,general --out scan_terms.txt
"""
import argparse
import csv
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 同词多源时取层级最高的优先级（与 use-glossary 四级查找一致）
LEVEL_ORDER = {"L1": 0, "L1.5": 1, "L2": 2}


def discover_sources():
    """返回 [(层级, 路径)]，按 L1/L1.5/L2 顺序。"""
    sources = []
    term_dir = os.path.join(BASE, "knowledge", "01_terminology")
    if os.path.isdir(term_dir):
        for fn in sorted(os.listdir(term_dir)):
            if fn.endswith(".csv"):
                sources.append(("L1", os.path.join(term_dir, fn)))
    sources.append(("L1", os.path.join(BASE, ".cache", "mojang", "redstone.csv")))
    for fn in ("blocks.csv", "items.csv", "entities.csv", "misc.csv"):
        sources.append(("L1.5", os.path.join(BASE, ".cache", "mojang", fn)))
    gl_dir = os.path.join(BASE, ".cache", "glossary")
    if os.path.isdir(gl_dir):
        for fn in sorted(os.listdir(gl_dir)):
            if fn.endswith(".csv"):
                sources.append(("L2", os.path.join(gl_dir, fn)))
    return sources


def find_col(fieldnames, candidates, fallback_index):
    for c in fieldnames or []:
        if c.strip().lower() in candidates:
            return c
    if fieldnames:
        return fieldnames[fallback_index]
    return None


def find_short_col(fieldnames):
    """只在表头存在短式列时返回其列名，否则 None（不回落，避免误用其它列）。"""
    for c in fieldnames or []:
        if c.strip().lower() in ("short form", "short_form"):
            return c
    return None


def split_terms(raw):
    """把术语单元格拆成多个词形：
    - 按 `;` 分同义词
    - 展开 `(aka X)` 别名（主词 + 别名各自成词形）
    - 去首尾空白、去尾部 `*`
    """
    out = []
    if not raw:
        return out
    for part in str(raw).split(";"):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(.*?)\s*\((?:aka|aka\.)\s*(.*?)\)\s*$", part, re.IGNORECASE)
        if m:
            main, aka = m.group(1).strip(), m.group(2).strip()
            if main:
                out.append(main)
            if aka:
                out.append(aka)
        else:
            out.append(part)
    return [t.rstrip("*").strip() for t in out if t.rstrip("*").strip()]


def build_term_index(sources, l2_categories=None, levels=None):
    """构建 {term_lower: (level, path, zh)}。

    同词多源取层级最高者（L1>L1.5>L2，与四级查找一致）。
    L2 按文件名过滤（--categories，.cache/glossary/<文件名>.csv）；文件名与
    glossary_categories.yaml 分类部分重叠但不对应，勿假设完全对应。
    levels 可过滤层级（默认 None=全部；scan 默认 L1+L2）。
    缩写（short_form/Short Form 列）只有长度≥3 或含数字才入集——
    避免 `BE`/`AT`/`T` 等短缩写命中普通英文词（be/at/t）制造噪声；
    口语字幕几乎不单独说短缩写，长名称词形已覆盖其语义（如 MS→Main Storage）。
    """
    index = {}
    for level, path in sources:
        if levels is not None and level not in levels:
            continue
        if level == "L2" and l2_categories is not None:
            cat = os.path.splitext(os.path.basename(path))[0]
            if cat not in l2_categories:
                continue
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fn = reader.fieldnames or []
            en_col = find_col(fn, ("en_us", "english", "full form (english)", "term_en"), 0)
            zh_col = find_col(fn, ("zh_cn", "chinese", "term_zh"), -1)
            short_col = find_short_col(fn)
            rows = list(reader)
        for r in rows:
            zh = (r.get(zh_col) or "").strip()
            for t in split_terms(r.get(en_col)):
                if not t:
                    continue
                key = t.lower()
                cur = index.get(key)
                if cur is None or LEVEL_ORDER[level] < LEVEL_ORDER[cur[0]]:
                    index[key] = (level, path, zh)
            if short_col is not None:
                for t in split_terms(r.get(short_col)):
                    if not t or (len(t) < 3 and not any(c.isdigit() for c in t)):
                        continue
                    key = t.lower()
                    cur = index.get(key)
                    if cur is None or LEVEL_ORDER[level] < LEVEL_ORDER[cur[0]]:
                        index[key] = (level, path, zh)
    return index


def make_matcher(index):
    """由术语集构建命中正则（长短语优先；前后词边界防误匹配 B36↔B360 之类）。"""
    terms = sorted(index.keys(), key=lambda s: (-len(s), s))
    if not terms:
        return None
    pat = "|".join(re.escape(t) for t in terms)
    return re.compile(r"(?<![A-Za-z0-9])(?:%s)(?![A-Za-z0-9])" % pat, re.IGNORECASE)


def parse_srt(path):
    """解析 SRT → [(idx, start, end, [body...]), ...]（与 chunk_subtitles.py 同款）。"""
    with open(path, "r", encoding="utf-8-sig") as fh:
        text = fh.read()
    units = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        m_idx = re.fullmatch(r"\d+", lines[0])
        m_ts = re.fullmatch(r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})", lines[1])
        if not m_idx or not m_ts:
            continue
        units.append((int(lines[0]), m_ts.group(1), m_ts.group(2), lines[2:]))
    return units


def parse_chunk(path):
    """解析 chunk_*.txt → [(idx, start_ts, text), ...]（跳过 # / ## 头）。"""
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            m = re.match(r"^c(\d+)\t(.+?)\s*-->\s*.+?\t(.*)$", line)
            if m:
                out.append((int(m.group(1)), m.group(2), m.group(3)))
    return out


def cmd_query(args):
    for term in args.terms:
        print(f"\n===== {term} =====")
        found = False
        for level, path in discover_sources():
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                en_col = find_col(reader.fieldnames, ("en_us", "english", "full form (english)", "term_en"), 0)
                zh_col = find_col(reader.fieldnames, ("zh_cn", "chinese", "term_zh"), -1)
                rows = list(reader)
            for r in rows:
                if term.lower() in (r.get(en_col) or "").lower():
                    rel = os.path.relpath(path, BASE)
                    print(f"  [{level}] {rel} | {r.get(en_col)} | {r.get(zh_col)}")
                    found = True
        if not found:
            print("  未命中")


def cmd_scan(args):
    cats = [c.strip() for c in args.categories.split(",")] if args.categories else None
    lvls = tuple(v.strip().upper() for v in args.levels.split(",")) if args.levels else None
    index = build_term_index(discover_sources(), l2_categories=cats, levels=lvls)
    rx = make_matcher(index)
    if rx is None:
        sys.exit("术语集为空，无法扫描")

    with open(args.file, "r", encoding="utf-8-sig") as fh:
        head = fh.read(4096)
    if re.search(r"\d{2}:\d{2}:\d{2},\d{3}\s*-->", head):
        rows = [(idx, s, " ".join(body)) for idx, s, _e, body in parse_srt(args.file)]
    else:
        rows = parse_chunk(args.file)
    if not rows:
        sys.exit("未解析到任何 cue/文本行，请确认输入是 SRT 或 chunk_*.txt")

    hits = []
    for idx, ts, txt in rows:
        for m in rx.finditer(txt):
            term = m.group(0)
            level, path, zh = index[term.lower()]
            hits.append((idx, ts, term, zh or "—", os.path.relpath(path, BASE), level))

    seen, uniq = set(), []
    for h in hits:
        key = (h[0], h[2].lower())
        if key in seen:
            continue
        seen.add(key)
        uniq.append(h)
    uniq.sort(key=lambda h: (h[0], h[1], h[2]))

    lines = [f"c{i}\t{ts} | {term} | {zh} | {src} | {lvl}" for i, ts, term, zh, src, lvl in uniq]
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines) + ("\n" if lines else ""))
        print(f"命中 {len(lines)} 条（去重后）→ {os.path.abspath(args.out)}")
    else:
        print("\n".join(lines) if lines else "（无命中）")


def main():
    ap = argparse.ArgumentParser(description="查询/扫描术语中文译名（L1→L1.5→L2，只读）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_q = sub.add_parser("query", help="查单个/多个术语的中文译名（词→译名）")
    p_q.add_argument("terms", nargs="+", help="要查询的英文术语")
    p_q.set_defaults(func=cmd_query)

    p_s = sub.add_parser("scan", help="扫字幕/块文本，找出出现的已收录术语（文本→命中词）")
    p_s.add_argument("file", help="SRT 或 chunk_*.txt 路径")
    p_s.add_argument("--categories", help="逗号分隔的 L2 分类（如 storage,general）；缺省加载全部 L2")
    p_s.add_argument("--levels", default="L1,L2",
                     help="扫描层级，逗号分隔（默认 L1,L2；加 L1.5 需显式指定）")
    p_s.add_argument("--out", help="命中清单落盘路径（缺省打印到 stdout）")
    p_s.set_defaults(func=cmd_scan)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
