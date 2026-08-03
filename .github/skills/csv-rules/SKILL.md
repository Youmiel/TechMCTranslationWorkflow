---
name: csv-rules
description: 本项目术语 CSV 的统一读写规范（编码、解析、写入、表头列含义）。凡涉及 .cache/glossary/、knowledge/01_terminology/ 下 CSV 的读取、解析、写入、更新操作均须遵守。翻译、术语登记、知识维护时自动参考。
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

## 三种词汇表的表头差异

项目涉及三个词汇表（区分与性质见 `use-glossary`「三个词汇表」表），**表头各不相同**，读写前先认清用的是哪个：

| 词汇表 | 位置 | 表头 | 说明 |
|--------|------|------|------|
| 项目术语库 | `knowledge/01_terminology/*.csv` | `term_en, short_form, definition, notes, term_zh, term_ja` | 共享 `_example.csv`；列含义见下节 |
| Mojang 官方词汇 | `.cache/mojang/*.csv` | 列顺序见下方注释 | 脚本生成 |
| TechMC 拆分术语 | `.cache/glossary/*.csv` | `Short Form, Regex, Full Form (English), Related, Description, ...`（多语言并排） | 英文术语在 `Full Form (English)`，中文在 `Chinese` / `Description (Chinese)` |

> 解析时**务必用 `csv` 模块按列名取值**（`csv.DictReader`），勿按位置硬编码——三表头列位各不相同。
>
> **Mojang 官方词汇列顺序**：由 `scripts/mojang_glossary/config.py` 的 `LANG_ORDER` 决定（当前 `["en_us","zh_cn"]`，第一列 `en_us` 英文术语，后续各目标语言）；扩展语言改 `LANG_LIST` / `LANG_ORDER`；解析按列名（`en_us` / `zh_cn`），勿假设固定列序。

## 表头列含义（唯一权威）

以下列含义**仅适用于项目术语库** `knowledge/01_terminology/*.csv`（共享 `_example.csv`；Mojang / TechMC 表头见上节「三种词汇表的表头差异」）：

| 列 | 说明 | 示例 |
|----|------|------|
| `term_en` | 英文标准术语，分号分隔同义词 | `BUD;Block Update Detector` |
| `short_form` | 缩写 | `BUD` |
| `definition` | 中文释义 | `能检测相邻方块更新并输出信号的元件` |
| `notes` | 备注（版本、来源、审核状态等） | `[1.16+]`、`待审核` |
| `term_zh` | 中文标准译名 | `方块更新检测器` |
| `term_ja` | 日文术语 | `BUD` |

- `term_en` 为首列（英→中翻译场景的自然查找方向），分号分隔同义词
- 语言列放在末尾，可随意向右扩展（`term_ko` `term_ru` 等）
- `category` 由文件名表达，无需在表中
