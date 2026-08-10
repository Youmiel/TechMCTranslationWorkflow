# -*- coding: utf-8 -*-
"""r03 方案解析（parse_r03）与写时即合规预检（check_r03）"""
import re
from pathlib import Path

from .io import norm, text_width, parse_srt, build_full


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


def check_r03(r03_path, srt_path):
    """r03 写时即合规预检（步骤 4 产出后、步骤 5 回填前必跑）：

    - 锚定唯一性：每个整句 EN 在 01 全文唯一命中（未命中 / 重复命中均报告）
    - 拆句互斥性：1:n 拆句子单元 EN 拼接 == 整句 EN
    - 行宽：每个译文单元中文视觉宽度 ≤ 20

    有违规输出清单并返回 1（打回 r03 改写），全部通过返回 0。
    """
    sentences = parse_r03(r03_path)
    cues = parse_srt(srt_path)
    full, _mapping, _offsets = build_full(cues)
    problems = []
    for s in sentences:
        n = norm(s.en)
        pos = full.find(n)
        if pos == -1:
            problems.append(f"❌ 整句 {s.key} 锚定失败（01 全文未找到）——回填将走顺序兜底，须修正措辞")
        elif full.find(n, pos + 1) != -1:
            problems.append(f"⚠️ 整句 {s.key} 非唯一命中（01 全文出现 ≥2 次）——回填将取第一处，须保证唯一或接受")
        if s.rel == "1:n" and s.units:
            joined = "".join(norm(u[1]) for u in s.units)
            if joined != n:
                problems.append(f"❌ 拆句 {s.key} 子单元 EN 拼接 ≠ 整句 EN（互斥性破坏）——双语英文行将错位")
        units = s.units or [(s.key, s.en, s.zh)]
        for u in units:
            w = text_width(u[2])
            if w > 20:
                problems.append(f"📏 行宽 {w:.1f}（>20）{u[0]}: {u[2]}")
    if not problems:
        print(f"✅ check-r03 通过：{len(sentences)} 整句，锚定唯一 / 互斥 / 行宽均合规")
        return 0
    print(f"❌ check-r03 发现 {len(problems)} 处问题（r03 需改写后重跑）:")
    for p in problems:
        print("  " + p)
    return 1
