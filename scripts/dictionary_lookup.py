#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查询 Storage-Catalog/Archive 的 dictionary（存储科技术语社区词典，只读）。

数据源：_repos/storage-archive/dictionary/
  config.json          轻量索引：id → terms(含同义词/缩写) + summary（社区官方索引）
  entries/<id>.json    完整条目：definition / status / references / referencedBy / threadURL

与 glossary_lookup.py 的关系：本脚本只查 storage-archive dictionary 这一个
社区知识库（存储科技，结构化 JSON 条目）；glossary_lookup.py 查项目
L1/L1.5/L2 的 CSV 译名表。两者正交，翻译流程按需调用（dictionary 定位 = L2 社区源）。

子命令：
  query <term> [<term>...]     查术语（词→完整定义），精确匹配 terms 数组（含同义词/缩写）
  scan <file> [--out f]        扫字幕/块文本，找出出现的已收录术语（文本→命中词）
  list [--brief]               列出全部术语（默认 id|terms|summary；--brief 只术语名）

用法:
  python scripts/dictionary_lookup.py query "Batcher" "Box Comparer"
  python scripts/dictionary_lookup.py scan _work/<视频>/01_subtitle_asr_fixed.srt --out dict_hits.tsv
  python scripts/dictionary_lookup.py list --brief
"""
import argparse
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT_DIR = os.path.join(BASE, "_repos", "storage-archive", "dictionary")
CONFIG_PATH = os.path.join(DICT_DIR, "config.json")
ENTRIES_DIR = os.path.join(DICT_DIR, "entries")


def _load_config():
    """读社区官方轻量索引 config.json → [{id, terms, summary, updatedAt}]。"""
    if not os.path.exists(CONFIG_PATH):
        sys.exit(f"未找到 {CONFIG_PATH}（storage-archive submodule 未检出/未初始化？）")
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("entries", [])


def _load_entry(entry_id):
    """读完整条目 entries/<id>.json → dict；缺文件返回 None。"""
    path = os.path.join(ENTRIES_DIR, f"{entry_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def build_term_index(meta):
    """由 config.json 的 terms 数组构建 {term_lower: entry_id}（含同义词/缩写）。"""
    index = {}
    for m in meta:
        for t in m.get("terms", []):
            t = (t or "").strip()
            if t:
                index.setdefault(t.lower(), m["id"])
    return index


def _fmt_terms(terms):
    return " / ".join(terms)


def _fmt_entry(entry):
    """把完整条目格式化为可读块。"""
    lines = []
    lines.append(f"# {_fmt_terms(entry.get('terms', []))}")
    lines.append(f"  id:      {entry.get('id')}")
    lines.append(f"  status:  {entry.get('status', '—')}")
    if entry.get("updatedAt"):
        lines.append(f"  updated: {entry.get('updatedAt')}")
    lines.append(f"  定义:    {entry.get('definition', '（无定义）')}")
    refs = entry.get("references") or []
    if refs:
        lines.append("  引用:    " + "; ".join(
            f"{r.get('type')}={r.get('term')}" for r in refs))
    if entry.get("threadURL"):
        lines.append(f"  来源:    {entry.get('threadURL')}")
    return "\n".join(lines)


def cmd_query(args):
    meta = _load_config()
    index = build_term_index(meta)
    meta_by_id = {m["id"]: m for m in meta}
    for term in args.terms:
        print(f"\n===== {term} =====")
        entry_id = index.get(term.lower())
        if entry_id is None:
            # 兜底：terms 含该词的条目（如查询词是完整句的一部分）
            alt = [m for m in meta if term.lower() in [t.lower() for t in m.get("terms", [])]]
            if alt:
                entry_id = alt[0]["id"]
        if entry_id is None:
            print("  未命中")
            continue
        entry = _load_entry(entry_id) or {}
        entry.setdefault("id", entry_id)
        entry.setdefault("terms", meta_by_id[entry_id]["terms"])
        print(_fmt_entry(entry))


def make_matcher(term_set):
    """由术语集构建命中正则（长短语优先；词边界防误匹配）。"""
    terms = sorted(term_set, key=lambda s: (-len(s), s))
    if not terms:
        return None
    pat = "|".join(re.escape(t) for t in terms)
    return re.compile(r"(?<![A-Za-z0-9])(?:%s)(?![A-Za-z0-9])" % pat, re.IGNORECASE)


def parse_srt(path):
    """解析 SRT → [(idx, start, [body...]), ...]（与 srt_chunk.py 同款）。"""
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
        units.append((int(lines[0]), m_ts.group(1), lines[2:]))
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


def cmd_scan(args):
    meta = _load_config()
    index = build_term_index(meta)
    meta_by_id = {m["id"]: m for m in meta}
    rx = make_matcher(set(index.keys()))
    if rx is None:
        sys.exit("术语集为空，无法扫描")

    with open(args.file, "r", encoding="utf-8-sig") as fh:
        head = fh.read(4096)
    if re.search(r"\d{2}:\d{2}:\d{2},\d{3}\s*-->", head):
        rows = [(idx, s, " ".join(body)) for idx, s, body in parse_srt(args.file)]
    else:
        rows = parse_chunk(args.file)
    if not rows:
        sys.exit("未解析到任何 cue/文本行，请确认输入是 SRT 或 chunk_*.txt")

    hits = []
    for idx, ts, txt in rows:
        for m in rx.finditer(txt):
            term = m.group(0)
            entry_id = index[term.lower()]
            summary = (meta_by_id[entry_id].get("summary") or "")[:60]
            hits.append((idx, ts, term, entry_id, summary))

    seen, uniq = set(), []
    for h in hits:
        key = (h[0], h[2].lower())
        if key in seen:
            continue
        seen.add(key)
        uniq.append(h)
    uniq.sort(key=lambda h: (h[0], h[1], h[2]))

    lines = [f"c{i}\t{ts} | {term} | dict:{entry_id} | {summary}" for i, ts, term, entry_id, summary in uniq]
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines) + ("\n" if lines else ""))
        print(f"命中 {len(lines)} 条（去重后）→ {os.path.abspath(args.out)}")
    else:
        print("\n".join(lines) if lines else "（无命中）")


def cmd_list(args):
    meta = _load_config()
    for m in sorted(meta, key=lambda x: (x.get("terms") or [""])[0].lower()):
        terms = _fmt_terms(m.get("terms", []))
        if args.brief:
            print(terms)
        else:
            summary = (m.get("summary") or "").replace("\n", " ")
            print(f"{m['id']}\t{terms}\t{summary[:80]}")


def main():
    ap = argparse.ArgumentParser(
        description="查询 storage-archive dictionary（存储科技术语社区词典，只读）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_q = sub.add_parser("query", help="查术语的完整定义（词→条目）")
    p_q.add_argument("terms", nargs="+", help="要查询的英文术语/缩写")
    p_q.set_defaults(func=cmd_query)

    p_s = sub.add_parser("scan", help="扫字幕/块文本，找出出现的已收录术语（文本→命中词）")
    p_s.add_argument("file", help="SRT 或 chunk_*.txt 路径")
    p_s.add_argument("--out", help="命中清单落盘路径（缺省打印到 stdout）")
    p_s.set_defaults(func=cmd_scan)

    p_l = sub.add_parser("list", help="列出全部术语")
    p_l.add_argument("--brief", action="store_true", help="只输出术语名（不含 id/summary）")
    p_l.set_defaults(func=cmd_list)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
