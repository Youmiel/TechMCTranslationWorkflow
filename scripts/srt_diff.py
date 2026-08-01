# -*- coding: utf-8 -*-
"""逐块对比两个 SRT，报告所有 ts 或正文不同的 cue。

用法: python srt_diff.py <a.srt> <b.srt>
"""
import argparse
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ap = argparse.ArgumentParser(description='逐块对比两个 SRT')
ap.add_argument('a', help='SRT 甲（如原始字幕）')
ap.add_argument('b', help='SRT 乙（如修正后字幕）')
args = ap.parse_args()
ORIG = args.a
FIXED = args.b


def parse(path):
    blocks = []
    with open(path, "r", encoding="utf-8-sig") as f:
        text = f.read()
    parts = re.split(r"\n\s*\n", text.strip())
    for p in parts:
        lines = p.strip().splitlines()
        if not lines:
            continue
        m = re.match(r"^(\d+)$", lines[0].strip())
        idx = int(m.group(1)) if m else -1
        ts = lines[1].strip() if len(lines) > 1 else ""
        body = " ".join(l.strip() for l in lines[2:]) if len(lines) > 2 else ""
        blocks.append({"idx": idx, "ts": ts, "body": body})
    return blocks


orig = parse(ORIG)
fixed = parse(FIXED)

print(f"原始 {len(orig)} 块 / 修正 {len(fixed)} 块\n")
print("=== ts 不同的 cue ===")
n_ts = 0
for o, f in zip(orig, fixed):
    if o["ts"] != f["ts"]:
        n_ts += 1
        print(f"[{o['idx']}] 原: {o['ts']}")
        print(f"       修: {f['ts']}")
print(f"ts 差异数: {n_ts}")

print("\n=== 正文不同的 cue（前 80 个）===")
n_body = 0
for o, f in zip(orig, fixed):
    if o["body"] != f["body"]:
        n_body += 1
        if n_body <= 80:
            print(f"[{o['idx']}] 原: {o['body'][:70]}")
            print(f"       修: {f['body'][:70]}")
print(f"正文差异数: {n_body}")
