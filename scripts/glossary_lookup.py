#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查询术语的中文译名（只读，不修改任何文件）。

按 skill 的 L1 → L1.5 → L2 顺序在项目术语源中检索：
  L1   knowledge/01_terminology/*.csv、.cache/mojang/redstone.csv
  L1.5 .cache/mojang/{blocks,items,entities,misc}.csv
  L2   .cache/glossary/*.csv

用法: python glossary_lookup.py <term> [<term> ...]
"""
import argparse
import csv
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


def main():
    ap = argparse.ArgumentParser(description="查询术语中文译名（L1→L1.5→L2）")
    ap.add_argument("terms", nargs="+", help="要查询的英文术语")
    args = ap.parse_args()

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


if __name__ == "__main__":
    main()
