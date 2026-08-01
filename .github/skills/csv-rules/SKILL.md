---
name: csv-rules
description: 本项目术语 CSV 的统一读写规范（编码、解析、写入）。凡涉及 .cache/glossary/、knowledge/01_terminology/ 下 CSV 的读取、解析、写入、更新操作均须遵守。翻译、术语登记、知识维护时自动参考。
---

# CSV 术语表读写规范

本项目所有术语 CSV 共享同一套读写规范。本规范是唯一权威来源，其他 Skill 引用此处，不重复展开。

## 适用范围

- `.cache/glossary/<类别>.csv`（上游拆分缓存，脚本生成）
- `knowledge/01_terminology/*.csv`（项目术语库，共享 `_example.csv` 表头）

## 编码规范

- **读取**：用 `utf-8-sig`（带 BOM，可能带 BOM）
- **写入**：用 `utf-8`

## 解析规范

- `definition`、`description`、`notes` 等列**常包含逗号**（如 "指一种比较器，当接收到方块或库存更新时会改变其信号"）
- **必须用 Python `csv` 模块解析**（`csv.DictReader` / `csv.reader`），它正确处理引号内的逗号
- **禁止**用 `split(',')` 或 `grep_search` 按逗号分列提取译名
- 用 `grep_search` 查找术语可模糊匹配内容，但提取译名务必读取完整行、用 `csv` 模块解析

## 写入规范

- 用 `csv.DictWriter` / `csv.writer` 追加，或手动将含逗号的字段用双引号包裹（如 `"指比较器在接收到方块或库存更新时改变信号"`），否则后续解析分列出错
- 复杂 Python 一律写脚本文件执行，**勿用 `python -c` 内联**（引号/中文易出错）
