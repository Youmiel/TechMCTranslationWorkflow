# -*- coding: utf-8 -*-
"""ASR 修正链路公共层（映射表解析 / 文本归一化 / 停用词表）。

**消费方**（全部只读引用，勿各自另写解析）：

| 工具 | 用到的部分 |
|---|---|
| `asr_trigger.py` | 映射解析 + 归一化 + 停用词（分层过滤） |
| `asr_check_trigger.py` | 归一化（清单项 ↔ `.asr.tsv` 决策行比对） |
| `glossary_hit_rate.py` | 停用词表（命中率回测的噪声剔除） |
| `render_preprocess_prompt.py` | 映射解析（先验注入） |

**为什么停用词表在此**：它原只存在于 `glossary_hit_rate.py`（为命中率回测设计），
ASR 触发清单的 X 层过滤（可执行方案 §三 判据 4）**复用同一张表**——实测
“滤 121 误报 / 0 误滤真命中”。两处各存一份必然漂移，故迁到本模块作单一权威。

> ⚠️ 停用词表只用于“**变体**是否为功能词”的判定（单字变体命停用词 → X 层不列清单）。
> **不得**用它作“词汇表组成词”判据——实测该判据会误滤 19 个真命中（含 `lock` 16 个）。
"""

import os
import re

# ---- 停用词表（单一权威；原 glossary_hit_rate.py 迁入）----

# 硬停用词：连接词 / 限定词 / 代词 / 介词 / 助动词 / 系动词
# 判据：这类词在口语字幕里必然是普通语法词，不可能单独作技术术语出现。
STOP_HARD = frozenset("""
a an the and or but nor so yet
for of to in on at by with from as if then than that this these those
it its is are was were be been being am do does did done have has had having
will would shall should can could may might must
i you he she they we me him her them us my your his their our
not no yes ok okay
""".split())

# 软停用词：抽象名词 / 方位词 / 泛用形容词——**可能**是真术语（如 up/down/block/full），
# 故只单独计数、不剔除，供人工复核。
#
# ⚠️ 但在 **ASR 触发清单** 语境下（可执行方案 §三 判据 4）软档**也参与过滤**：
# 实测 `STOP_HARD ∪ STOP_SOFT` 滤掉 121 条误报、零误滤真命中。两处口径不同是**故意的**，
# 不是不一致——命中率回测“宁可漏报不可误杀”（多为人工复核），清单“宁可清短”。
STOP_SOFT = frozenset("""
up down out off over under left right top bottom front back side
full empty empty-ish new old high low big small long short
line lines point points level levels value values size state power
bit bits byte bytes number numbers many most some any all both each every
more much very just only also
""".split())

# 清单分层用的合并集（判据 4）
STOP_ANY = STOP_HARD | STOP_SOFT


def load_stopwords(path=None):
    """外置停用词表覆盖：每行一词（`#` 注释；`# soft` / `# hard` 切换所属档）。

    返回 `(hard, soft)`；`path` 为空或不存在时返回内表。
    """
    hard, soft = set(STOP_HARD), set(STOP_SOFT)
    if not path or not os.path.exists(path):
        return hard, soft
    section = "hard"
    for ln in open(path, encoding="utf-8"):
        s = ln.strip()
        if not s:
            continue
        if s.startswith("#"):
            if "soft" in s.lower():
                section = "soft"
            elif "hard" in s.lower():
                section = "hard"
            continue
        (hard if section == "hard" else soft).add(s.lower())
    return hard, soft


# ---- 归一化 / 匹配 ----

def normalize(s):
    """匹配前标准处理：小写 + 折叠空白。

    可执行方案 §五 实测：**不折叠空白会漏检 3 个变体**（如 `MPT` → `mpt`）；
    大小写不敏感同理必需。
    """
    return re.sub(r"\s+", " ", s.lower()).strip()


def variant_re(variant):
    """变体 → 整串精确匹配正则（大小写不敏感由调用方在归一化文本上施加）。

    边界 `[a-z0-9]`：防 `36` 命中 `c36`、防 `car` 命中 `cars`。

    ⚠️ **不得改成模糊匹配**——一旦模糊，匹配器即退化为“另一个会漏检的近似器”
    （可执行方案决策记录）。
    """
    return re.compile(r"(?<![a-z0-9])" + re.escape(normalize(variant)) + r"(?![a-z0-9])")


# ---- 映射表解析 ----

def parse_fixes(path):
    """解析 asr_fixes.md 表格 → `[(正确词, [变体], 说明)]`。

    格式约定（`term-registration#ASR 映射登记`）：同一条多个变体合并为一行（`/` 分隔），
    按**正确词聚合**。表头行与 `|---|` 分隔行跳过。
    """
    if not path or not os.path.exists(path):
        return []
    rows = []
    for ln in open(path, encoding="utf-8-sig", errors="replace"):
        s = ln.strip()
        if not (s.startswith("|") and s.endswith("|")):
            continue
        if set(s) <= set("|- "):
            continue  # 分隔行
        cols = [c.strip() for c in s.strip("|").split("|")]
        if len(cols) < 2 or not cols[0].strip("-: "):
            continue
        if cols[0].lower() in ("正确词", "correct"):
            continue  # 表头
        variants = [v.strip() for v in cols[1].split("/") if v.strip()]
        if variants:
            rows.append((cols[0], variants, cols[2] if len(cols) > 2 else ""))
    return rows


def collect_pairs(paths):
    """多份映射表 → `[(正确词, 变体, 说明, 来源路径)]`（展平，**不合并**）。

    不合并的原因：同一变体指向多个正确词是**多义条目**（实测 3 个），
    必须在清单里标 `ambiguous` 交语境判定，合并会静默丢信息。
    """
    out = []
    for p in paths:
        for correct, variants, note in parse_fixes(p):
            for v in variants:
                out.append((correct, v, note, p))
    return out


# ---- SRT 读取（需 cue 号与时间码，故不复用只取文本的旧解析）----

def read_srt(path):
    """读 SRT → `[(idx, start, end, text)]`；文本内部换行合并为空格。

    坏块（无时间码 / 空文本）跳过但**计数**，由调用方决定是否判为不可解析。
    """
    text = open(path, encoding="utf-8-sig", errors="replace").read()
    cues = []
    bad = 0
    for blk in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        lines = [x for x in blk.split("\n") if x.strip()]
        if not lines:
            continue
        ti = next((i for i, x in enumerate(lines) if "-->" in x), None)
        if ti is None:
            bad += 1
            continue
        body = " ".join(lines[ti + 1:]).strip()
        if not body:
            bad += 1
            continue
        ts = [x.strip() for x in lines[ti].split("-->")]
        idx = 0
        if ti > 0:
            m = re.fullmatch(r"\d+", lines[0].strip())
            if m:
                idx = int(m.group(0))
        cues.append((idx, ts[0], ts[1] if len(ts) > 1 else "", body))
    return cues, bad


def fmt_hhmmss(timestamp):
    """SRT 时间码（`HH:MM:SS,mmm`）→ `HH:MM:SS`（清单/登记口径，无毫秒）。"""
    m = re.match(r"(\d{2}:\d{2}:\d{2})", timestamp.strip())
    return m.group(1) if m else timestamp.strip()
