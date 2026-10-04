# -*- coding: utf-8 -*-
"""陷阱词清单（`.github/experience/trap_words.md`）解析——供渲染脚本注入 subagent prompt。

清单收录"看似普通英文、易被固有思维误判为普通词而不去查"的科技术语（如 `filter`、
`main storage`），是**触发层**资产：与术语词汇表正交——词汇表回答“查到是什么”，
清单负责“提醒记得去查”。

用法：
    from shared.traps import load_traps
    text = load_traps(path)      # → 全部分类段的 markdown 片段（无清单文件时为空串）
"""
import re

# `## <分类名>` 标题（分类名不含空格；文档自身的说明节如“格式约定”需排除）
SECTION_RE = re.compile(r"^##\s+(\S+)\s*$", re.M)
NON_CATEGORY_SECTIONS = ("格式约定",)


def parse_sections(text):
    """trap_words.md 正文 → {分类名: 段落正文}（段落不含 `## 分类名` 标题行本身）。"""
    sections = {}
    marks = list(SECTION_RE.finditer(text))
    for i, m in enumerate(marks):
        name = m.group(1)
        if name in NON_CATEGORY_SECTIONS:
            continue
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        sections[name] = text[m.end():end].strip()
    return sections


def load_traps(path):
    """读陷阱词清单 → 全部分类段的 markdown 片段（按文档顺序，含分类名）。

    文件不存在 → 返回空串（调用方按“无陷阱词”处理，不阻断）。
    """
    try:
        with open(path, encoding="utf-8") as fh:
            sections = parse_sections(fh.read())
    except OSError:
        return ""
    out = []
    for name, body in sections.items():
        if body:
            out.append(f"**{name}**\n\n{body}")
    return "\n\n".join(out)
