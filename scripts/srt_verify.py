# -*- coding: utf-8 -*-
"""核对修正后 SRT 与原始 SRT 的块数、时间码、文本，并重编号对齐原始编号。

用法: python srt_verify.py <orig.srt> <fixed.srt>
"""
import argparse
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ap = argparse.ArgumentParser(description='核对并重编号修正 SRT')
ap.add_argument('orig', help='原始 SRT 路径')
ap.add_argument('fixed', help='修正后 SRT 路径')
args = ap.parse_args()
ORIG = args.orig
FIXED = args.fixed


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
        if not m:
            print(f"  !! 无法解析块首行: {lines[0]!r}")
            continue
        idx = int(m.group(1))
        ts = lines[1].strip() if len(lines) > 1 else ""
        body = " ".join(l.strip() for l in lines[2:]) if len(lines) > 2 else ""
        blocks.append({"idx": idx, "ts": ts, "body": body})
    return blocks


orig = parse(ORIG)
fixed = parse(FIXED)

print(f"原始块数: {len(orig)}  修正后块数: {len(fixed)}")
print(f"原始编号: {orig[0]['idx']}..{orig[-1]['idx']}")

# 检查原编号是否有跳跃
missing = []
for i in range(1, len(orig)):
    if orig[i]["idx"] != orig[i - 1]["idx"] + 1:
        missing.append((orig[i - 1]["idx"], orig[i]["idx"]))
print(f"原始编号跳跃点: {missing if missing else '无'}")

# 用原始编号序列重编号修正文件
new_idx_seq = [b["idx"] for b in orig]
if len(fixed) == len(new_idx_seq):
    print("块数一致，按原始编号重编号。")
    with open(FIXED, "w", encoding="utf-8", newline="\n") as f:
        for b, new_idx in zip(fixed, new_idx_seq):
            f.write(f"{new_idx}\n{b['ts']}\n{b['body']}\n\n")
    print("重编号完成。")
else:
    print("块数不一致！需要手动核查。")
    # 逐块对比
    for i, (o, fx) in enumerate(zip(orig, fixed)):
        if o["ts"] != fx["ts"]:
            print(f"  [{i}] 时间码不同: 原 {o['idx']} {o['ts']} vs 修 {fx['idx']} {fx['ts']}")
    if len(orig) > len(fixed):
        for j in range(len(fixed), len(orig)):
            print(f"  修正文件缺少: {orig[j]['idx']} {orig[j]['ts']} {orig[j]['body'][:40]}")
    if len(fixed) > len(orig):
        for j in range(len(orig), len(fixed)):
            print(f"  修正文件多出: {fixed[j]['idx']} {fixed[j]['ts']} {fixed[j]['body'][:40]}")
