# -*- coding: utf-8 -*-
"""r01 措辞校验：r01 词序列 == 01 词序列（剔除 [Music]），验证"不得改动措辞"硬约束

回填工作流（reflow-redstone）步骤 1：LLM 合并补标点后，词序列必须与 01 一致（只加标点、不改措辞）。

用法（命令根 = Project_Main/）：
  python scripts/srt_check_r01.py <01.srt> <r01_merged_en.txt>
退出码：0 = 一致；1 = 存在分歧。
"""
import argparse
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")


def srt_words(path):
    raw = open(path, encoding="utf-8-sig").read()
    texts = []
    for block in raw.split("\n\n"):
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        body = " ".join(lines[2:])
        if body.strip() in ("[Music]", "[Music] "):
            continue
        texts.append(body)
    joined = " ".join(texts)
    return re.findall(r"[a-z0-9']+", joined.lower())


def txt_words(path):
    raw = open(path, encoding="utf-8").read()
    return re.findall(r"[a-z0-9']+", raw.lower())


def main():
    ap = argparse.ArgumentParser(description="r01 措辞校验：词序列与 01 一致（不得改动措辞）")
    ap.add_argument("srt", help="01_subtitle_asr_fixed.srt")
    ap.add_argument("r01", help="r01_merged_en.txt")
    args = ap.parse_args()

    w1 = srt_words(args.srt)
    w2 = txt_words(args.r01)
    print(f"01 词数: {len(w1)}  r01 词数: {len(w2)}")
    if w1 == w2:
        print("✅ 词序列完全一致（含顺序）")
        return
    # 定位第一处分歧
    for i, (a, b) in enumerate(zip(w1, w2)):
        if a != b:
            ctx1 = " ".join(w1[max(0, i - 4):i + 5])
            ctx2 = " ".join(w2[max(0, i - 4):i + 5])
            print(f"❌ 第 {i} 词分歧: 01=[{a}] r01=[{b}]")
            print(f"  01 上下文: ...{ctx1}...")
            print(f"  r01 上下文: ...{ctx2}...")
            print(f"  01 长度 {len(w1)} / r01 长度 {len(w2)}")
            sys.exit(1)
    # 前缀一致，长度不同
    print(f"⚠️ 前缀一致但长度不同（01={len(w1)} r01={len(w2)}）")
    extra1 = " ".join(w1[len(w2):][:15])
    extra2 = " ".join(w2[len(w1):][:15])
    if extra1:
        print(f"  01 多出: ...{extra1}")
    if extra2:
        print(f"  r01 多出: ...{extra2}")
    sys.exit(1)


if __name__ == "__main__":
    main()
