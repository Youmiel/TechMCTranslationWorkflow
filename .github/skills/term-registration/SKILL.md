---
name: term-registration
description: 将已确认的英文术语→中文译名登记到 knowledge/01_terminology/_uncategorized.csv 的规范。翻译工作流确认术语清单后、或文中出现明确映射时使用。
---

# 术语登记规范

将已确认的 `英文术语 → 中文译名` 映射登记到项目术语库。本规范是术语入库的唯一权威来源。

## 写入范围

- **只写入** `knowledge/01_terminology/_uncategorized.csv`
- 不创建其他 CSV，不擅自归类（人工定期分拣到对应类别）
- 所有术语 CSV 共享 `_example.csv` 表头

## 触发条件

- **翻译工作流**（最常见）：`translate-redstone` Skill 阶段一确认术语清单后，自动将已确认术语入库
- 文中明确给出 `英文术语 → 中文译名` 映射
- 用户要求登记

## 同步步骤

1. **筛选**：排除 `[待审核]` 标记的术语，只保留已确认译名的条目
2. **读表头**：读 `knowledge/01_terminology/_example.csv` 获取表头
3. **查重**：读 `knowledge/01_terminology/_uncategorized.csv`，检查 `term_en` 是否已存在
4. **追加**：不存在则用 Python `csv.DictWriter` 追加新行（`term_en`、`term_zh`、`definition` 从映射表获取，其余字段留空或填来源注释）；存在则跳过、不覆盖
   - **来源格式**：`notes`/`definition` 中的来源必须写**具体缓存文件路径**——`.cache/glossary/<分类>.csv`、`.cache/mojang/<文件>.csv`、`knowledge/01_terminology/<分类>.csv`；**禁止**写笼统的 "TechMC Glossary" / "knowledge/"（呼应 `use-glossary`"用拆分缓存、不用源文件"规则）
5. **索引**：`_uncategorized.csv` 词条变动**不更新** `indexes/knowledge/` 的具体词条（该条目只保留静态占位描述）；仅当新增**非 `_uncategorized`** 的稳定条目或类别描述实质变化时才更新索引，并同步更新索引文件的「最近更新/生成时间」时间戳（刷新判断依据，见 `indexing-rules`「索引时间戳与更新策略」）

## ASR 映射登记（翻译工作流专用）

用户确认的 `[ASR 推测]` 条目，同步追加到 `.github/experience/asr_fixes.md` 的"已验证映射"表（去重后）。

## 相关规范

- CSV 编码/解析/写入细节见 `csv-rules` Skill
- 表头列含义见 `csv-rules` Skill「表头列含义」（唯一权威）
