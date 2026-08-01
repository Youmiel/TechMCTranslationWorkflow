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

三个"词汇表"的区分表见 `use-glossary` Skill 开头（项目术语库 / 拆分术语缓存 / 上游术语表），此处不重复。

维护视角：
- Agent **只写入** `knowledge/01_terminology/_uncategorized.csv`，不触碰 `.cache/glossary/`（脚本生成）与 `_repos/`（只读）
- 具体的术语文件清单见 `indexes/knowledge/`

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

登记流程（触发条件、同步步骤、ASR 映射登记）统一按 `term-registration` Skill 执行。

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

> **CSV 读写**：编码、解析、写入统一按 `csv-rules` Skill 执行。

### 版本标注

索引/知识条目的版本标注统一按 `indexing-rules` Skill 执行（`[通用]` / `[版本+]` / `[起-止]` / `[旧]` 等）。

## 更新索引

内容变更后，更新 `indexes/knowledge/` 下对应索引文件。条目格式与版本标注按 `indexing-rules` Skill 执行。

## 运行脚本

| 操作 | 命令 |
|------|------|
| 拆分术语表 | `python scripts/glossary_split.py` |
| 检查术语表 | `python scripts/glossary_split.py --check` |
| 同步 submodule | `git submodule update --remote` |

## 安全规则

- 删除规则见 `AGENTS.md` 核心原则 #6（禁止自动删除，需清理时提示用户手动操作）。
- 只写入 `knowledge/`、`indexes/`、`.cache/`（脚本生成），不触碰 `_repos/`（只读）。
- 修改 `knowledge/` 前确认版本信息准确。
