# -*- coding: utf-8 -*-
"""知识卡索引（`indexes/knowledge/02_mechanic.md`）解析——供渲染脚本注入 subagent prompt。

注入内容 = 索引的「**知识卡**」节，只保留介绍各知识卡的句子
（`- **`卡.md`** — 说明 [版本]`），移除缩进的维护子项（「关键词」「来源」）
与文件头部维护信息（生成时间等）——即「一个移除了关键词和来源的索引」。

用法：
    from shared.knowledge_cards import load_card_index
    text = load_card_index(path)   # → 「知识卡」节条目列表（不含节标题；无文件/无该节时为空串）
"""
import re

# `## 知识卡` 节标题
SECTION_RE = re.compile(r"(?m)^##\s+知识卡\s*$")
NEXT_SECTION_RE = re.compile(r"(?m)^##\s+")
# 条目内的缩进子项（「关键词」「来源」等维护信息）：顶层条目 `- ` 无前导空白，据此区分
SUBITEM_RE = re.compile(r"(?m)^[ \t]+-[ \t].*(?:\n|$)")


def load_card_index(path):
    """读知识卡索引 → 「知识卡」节条目列表（移除缩进维护子项；不含节标题）。

    文件不存在 / 无「知识卡」节 → 返回空串（调用方按“无知识卡索引”处理，不阻断）。
    """
    try:
        with open(path, encoding="utf-8-sig") as fh:
            text = fh.read()
    except OSError:
        return ""
    m = SECTION_RE.search(text)
    if not m:
        return ""
    rest = text[m.end():]
    nxt = NEXT_SECTION_RE.search(rest)
    body = rest[:nxt.start()] if nxt else rest
    body = SUBITEM_RE.sub("", body)
    return body.strip()
