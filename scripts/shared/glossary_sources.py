# -*- coding: utf-8 -*-
"""术语源适配层（单一权威）：不同词汇表的表头差异在此统一。

**为什么需要**：三套词汇表的表头各不相同，且同一层的命名也不统一——

| 层 | 表头示例 | 英文列 | 中文列 | 缩写列 |
|----|----------|--------|--------|--------|
| L1 项目库 | `term_en,short_form,definition,notes,term_zh,term_ja` | `term_en` | `term_zh` | `short_form` |
| L1.5 Mojang | `en_us,zh_cn` | `en_us` | `zh_cn` | — |
| L2 社区 | `Short Form,Regex,Full Form (English),…,Chinese,…` | `Full Form (English)` | `Chinese` | `Short Form` |

调用方只需 `iter_terms(path)`，不关心表头差异。

**历史教训**：`render_preprocess_prompt.py` 曾按**固定列位**取值
（`rec[2]` / `rec[7]`，且 `len(rec) < 8` 直接跳过）——该写法只对 L2 表有效，
**L1 项目库（6 列）全部行被静默丢弃**（484 行 → 0 行），导致阶段〇 ASR 纠错
从未拿到过项目自己裁定的译名。故本模块统一按**列名**取，位置仅作兜底。

用法：
    from glossary_sources import iter_terms, find_col, split_terms

    for terms, zh, shorts in iter_terms(path):
        ...   # terms/shorts 已展开同义词与 (aka X) 别名
"""
import csv
import os
import re

# 各列名的候选写法（小写比较）；按优先级排列，位置兜底
EN_CANDIDATES = ("en_us", "english", "full form (english)", "term_en")
ZH_CANDIDATES = ("zh_cn", "chinese", "term_zh")
SHORT_CANDIDATES = ("short form", "short_form")

# 首行若命中这些值，视为表头（部分表可能无表头）
HEADER_HINTS = frozenset("en_us term_en english full form (english)".split())


def find_col(fieldnames, candidates, fallback_index):
    """按列名找列；找不到时回退到 `fieldnames[fallback_index]`。

    `fallback_index` 支持负数（-1 = 最后一列）。
    """
    for c in fieldnames or []:
        if (c or "").strip().lower() in candidates:
            return c
    if fieldnames:
        return fieldnames[fallback_index]
    return None


def find_short_col(fieldnames):
    """只在表头确有缩写列时返回列名，否则 None（不回落，避免误用其它列）。"""
    for c in fieldnames or []:
        if (c or "").strip().lower() in SHORT_CANDIDATES:
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


def short_terms(raw, min_len=3):
    """缩写单元格 → 词形列表。

    默认只收**长度 ≥3 或含数字**的缩写：避免 `BE`/`AT`/`T` 命中普通英文词
    （be/at/t）制造噪声；口语字幕几乎不单独说短缩写，长名称词形已覆盖其语义。
    """
    out = []
    for t in split_terms(raw):
        if t and (len(t) >= min_len or any(c.isdigit() for c in t)):
            out.append(t)
    return out


def has_header(path):
    """探测文件是否有表头行（读首行，命中 HEADER_HINTS 即认为有）。"""
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            first = next(csv.reader(f), [])
    except (OSError, StopIteration):
        return False
    for cell in first:
        if (cell or "").strip().lower() in HEADER_HINTS:
            return True
    return False


def iter_terms(path):
    """读一个术语 CSV → yield `(terms, zh, shorts)`。

    - `terms`  : 英文词形列表（已展开 `;` 与 `(aka X)`）
    - `zh`     : 标准译名（可能为空字符串）
    - `shorts` : 缩写词形列表（无缩写列或过短时为 `[]`）

    表头按列名适配；无表头时按位置兜底（英文列 0 / 中文列 -1）。
    """
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        if not fieldnames:
            return
        en_col = find_col(fieldnames, EN_CANDIDATES, 0)
        zh_col = find_col(fieldnames, ZH_CANDIDATES, -1)
        short_col = find_short_col(fieldnames)
        for row in reader:
            terms = split_terms(row.get(en_col))
            if not terms:
                continue
            zh = (row.get(zh_col) or "").strip() if zh_col else ""
            shorts = short_terms(row.get(short_col)) if short_col else []
            yield terms, zh, shorts
