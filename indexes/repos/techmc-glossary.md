# techmc-glossary 内容索引

> 生成时间：2026-07-30
> 上游 commit：1f4da98548598cdd5d1c9c72818195cdab3bd6f5
> 仓库：https://github.com/TechMC-Glossary/TechMC-Glossary
> 在线浏览：http://beta.techmc.wiki/glossary

1. **禁止直接使用 `_repos/techmc-glossary/TechMC Glossary.csv`**（源文件是合并格式）
2. **必须使用 `.cache/glossary/` 下的拆分文件**（按类别独立，Agent 按需加载）

## 术语表 CSV

- **TechMC Glossary.csv** — 多语言 MC 技术术语对照表

  **CSV 字段结构（28 列）：**

  | 列名 | 用途 |
  |------|------|
  | `Category` | 主题分类，用于排序 |
  | `Short Form` | 常用缩写 |
  | `Regex` | 可变数量术语的正则 |
  | `Full Form (English)` | 标准英文术语 |
  | `Related` | 关联术语（`synonym:` / `see:`） |
  | `Description` | 英文释义 |
  | `Chinese` / `Description (Chinese)` | 简体中文译名与释义 |
  | `Japanese` / `Description (Japanese)` | 日语译名与释义 |
  | + Arabic, French, German, Italian, Korean, Portuguese, Russian, Spanish |

  - 关键词：术语表, 多语言, CSV, 对照表, 翻译, 标准化
