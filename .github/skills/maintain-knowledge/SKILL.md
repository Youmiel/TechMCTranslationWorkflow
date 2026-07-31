---
name: maintain-knowledge
description: 维护项目第一类知识（knowledge/）和索引（indexes/）。包括术语登记、CSV 格式规范、版本标注、索引更新。修改 knowledge/ 或登记新术语时参考。
---

# 知识库维护

在 `Project_Main/` 打开的工作区中，Agent 负责维护第一类知识（`knowledge/`）及相关设施。

## 目录速查

| 目录 | 性质 | 维护方式 |
|------|------|----------|
| `knowledge/` | 第一类，Git 追踪 | 人工撰写/审核，Agent 辅助 |
| `.cache/` | 第二类，Git 忽略 | 脚本生成，禁止手动编辑 |
| `_repos/` | 第三类，Submodule | 上游维护，只读引用 |
| `indexes/` | 索引，Git 追踪 | 内容变更后同步更新 |
| `scripts/` | 工具脚本 | 按需修改 |

## 术语体系（防混淆）

项目中有三个不同的"词汇表"，必须区分：

| 名称 | 位置 | 性质 |
|------|------|------|
| **项目术语库** | `knowledge/01_terminology/` | 本项目的译名标准、人物/组织名录（第一类，人工维护） |
| **拆分术语缓存** | `.cache/glossary/` | 从上游自动拆分的独立 CSV（第二类，脚本生成） |
| **上游术语表** | `_repos/techmc-glossary/` | 社区维护的合并 CSV（第三类，只读） |

## knowledge/01_terminology/ 结构

此目录不仅包含游戏术语，还包含翻译所需的各类参考信息：

```
knowledge/01_terminology/
├── _example.csv           # 表头模板（所有 CSV 共享同一表头）
├── _uncategorized.csv     # Agent 自动登记的新术语（待人工分拣）
├── *.csv                  # 人工分拣后的各类术语表（redstone.csv、people.csv 等）
└── ...                    # 按需扩展
```

所有 CSV 共用 `_example.csv` 中的表头。Agent 只写入 `_uncategorized.csv`，不创建其他 CSV。具体的术语文件清单见 `indexes/knowledge/`。

## 术语同步机制

Agent 只写入 `_uncategorized.csv`，不擅自归类。人工定期分拣到对应类别的 CSV。

### 触发条件

以下情况登记到 `_uncategorized.csv`：

- **翻译工作流**（最常见）：`translate_redstone` Skill 的阶段一确认术语清单后，自动将已确认术语入库（详见该 Skill §1.5）
- 文中明确给出 `英文术语 → 中文译名` 映射
- 用户要求登记

### 同步步骤

1. 识别文中所有 `英文术语 → 中文译名` 映射
2. 在 `_uncategorized.csv` 中查 `term_en` 是否已存在
3. 不存在则追加新行，存在则跳过
4. 更新 `indexes/knowledge/`

### 文件格式

- 长篇机制说明：`knowledge/<分类>/<词条>.md`（含 YAML frontmatter）
- 术语/人物/组织：CSV，共享 `_example.csv` 中的表头
- 所有术语 CSV 表头统一，Agent 新建术语只能写入 `_uncategorized.csv`

### CSV 表头（见 `_example.csv`）

```csv
term_en,short_form,definition,notes,term_zh,term_ja
```

- `term_en` 为首列（英→中翻译场景的自然查找方向），分号分隔同义词
- 语言列放在末尾，可随意向右扩展（`term_ko` `term_ru` 等）
- `category` 由文件名表达，无需在表中

| 列 | 说明 | 示例 |
|----|------|------|
| `term_en` | 英文标准术语，分号分隔同义词 | `BUD;Block Update Detector` |
| `short_form` | 缩写 | `BUD` |
| `definition` | 中文释义 | `能检测相邻方块更新并输出信号的元件` |
| `notes` | 备注（版本、来源、审核状态等） | `[1.16+]`、`待审核` |
| `term_zh` | 中文标准译名 | `方块更新检测器` |
| `term_ja` | 日文术语 | `BUD` |

> **CSV 写入注意**：`definition` 和 `notes` 列常包含逗号。Agent 写入时必须用 Python `csv.writer` 
> 或手动将含逗号的字段用双引号包裹（如 `"指比较器在接收到方块或库存更新时改变信号"`），
> 否则后续解析会分列出错。
>
> **CSV 编码注意**：读取 `knowledge/` 下 CSV 用 `utf-8-sig`（带 BOM），写入用 `utf-8`。
> 复杂 Python 一律写脚本文件执行，勿用 `python -c` 内联。

### 版本标注

Minecraft 机制随版本变化，知识条目必须标注适用版本：
- `[通用]` — 基础机制，跨版本稳定
- `[1.21+]` — 1.21 起新增的机制
- `[1.16-1.20]` — 仅在该版本范围内有效
- `[旧]` — 已过时，保留仅供参考

## 更新索引

内容变更后，更新 `indexes/knowledge/` 下对应索引文件。索引条目格式：

```markdown
- **<文件路径>** — 一句话概要 [版本]
  - 关键词：tag1, tag2, tag3
```

## 运行脚本

| 操作 | 命令 |
|------|------|
| 拆分术语表 | `python scripts/split_glossary.py` |
| 检查术语表 | `python scripts/split_glossary.py --check` |
| 同步 submodule | `git submodule update --remote` |

## 安全规则

- **禁止删除任何文件**。需要清理时提示用户手动操作。
- 只写入 `knowledge/`、`indexes/`、`.cache/`（脚本生成），不触碰 `_repos/`（只读）。
- 修改 `knowledge/` 前确认版本信息准确。
