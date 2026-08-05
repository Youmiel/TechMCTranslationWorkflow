---
name: maintain-knowledge
description: 维护项目第一类知识（knowledge/）与索引（indexes/）的总入口：目录速查、维护任务路由（细节在各扩展 Skill）、通用知识卡维护、运行脚本、安全规则。修改 knowledge/、新建知识卡、或需决定"用哪个维护 Skill"时参考。
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
| `.github/experience/` | 经验（广义知识），Git 追踪 | 随翻译追加 + 日常维护（见「经验文件维护」） |
| `scripts/` | 工具脚本 | 按需修改 |

## 维护任务决策（用哪个 Skill）

| 任务 | 用哪个 Skill |
|------|-------------|
| 术语登记（英→中） | `term-registration` |
| CSV 读写/表头列含义 | `csv-rules` |
| 索引格式/版本/时间戳 | `indexing-rules` |
| 外部仓库索引生成/更新判断 | `index-repos`（`scripts/check_index_stale.py`） |
| 术语表加载/四级查找 | `use-glossary` |
| Wiki 抓取/兜底 | `wiki-tools` |
| 通用知识卡 | 本 Skill [#通用知识卡](#通用知识卡) 节 |
| 经验/日志维护（ASR 分层、coverage 流水、经验提炼、超限整理） | 写入按 `term-registration` / `translate-redstone` 阶段三；超限整理按本 Skill「经验文件维护」 |

## 术语体系（防混淆）

三个"词汇表"的区分表见 `use-glossary` Skill 开头（项目术语库 / 拆分术语缓存 / 上游术语表），此处不重复。

维护视角：
- Agent **只写入** `knowledge/01_terminology/_uncategorized.csv`，不触碰 `.cache/glossary/`（脚本生成）与 `_repos/`（只读）
- 具体的术语文件清单见 `indexes/knowledge/`

## knowledge/01_terminology/ 结构

此目录不仅包含游戏术语，还包含翻译所需的各类参考信息：

```
knowledge/
├── _template_knowledge.md      # 通用知识卡模板（唯一权威，位于 knowledge/ 根）
├── 01_terminology/             # 术语表 CSV
└── 02_mechanic/                # 机制知识卡

knowledge/01_terminology/
├── _example.csv            # 表头模板（所有 CSV 共享同一表头）
├── _uncategorized.csv      # Agent 自动登记的新术语（待人工分拣）
├── *.csv                   # 人工分拣后的各类术语表（redstone.csv、people.csv 等）
├── *.md                    # 术语知识卡（<英文术语>.md）
└── ...                     # 按需扩展
```

所有 CSV 共用 `_example.csv` 中的表头。Agent 只写入 `_uncategorized.csv`，不创建其他 CSV。具体的术语文件清单见 `indexes/knowledge/`。

## 术语同步机制

Agent 只写入 `_uncategorized.csv`，不擅自归类。人工定期分拣到对应类别的 CSV。

登记流程（触发条件、同步步骤、ASR 映射登记）统一按 `term-registration` Skill 执行。

### 文件格式与规范（指针）

- 长篇机制说明：`knowledge/<分类>/<词条>.md`（含 YAML frontmatter）
- 术语/人物/组织：CSV，共享 `_example.csv` 表头；Agent 新建术语只能写入 `_uncategorized.csv`
- **CSV 表头列含义**：`csv-rules` Skill（唯一权威）
- **CSV 读写规范**：`csv-rules` Skill（编码/解析/写入）
- **版本标注**：`indexing-rules` Skill

## 通用知识卡

记录一条**词汇/概念/机制**的知识要点——定义、语境用法、翻译注意事项等（通用术语 CSV 未覆盖的部分）。

### 模板

- 唯一权威模板：`knowledge/_template_knowledge.md`
- 每词/每概念一卡，文件命名 `<英文术语>.md`；术语类卡片放 `knowledge/01_terminology/`，机制类卡片放 `knowledge/02_mechanic/`
- 卡片结构：YAML frontmatter（`term`/`aliases`/`category`/`source`/`version`/`status`）+ 3 分区（`要点`/`翻译注意事项`/`备注`）

### 创建时机

以下情况创建或更新知识卡：

- 翻译中发现某词/概念有值得记录的语境用法、特殊指代或翻译注意事项（如 `main storage` 在本视频指 Wavetech 全物品仓库）
- 用户明确要求登记某词条/概念

### 维护规则

- `status`：新建为 `待审核`；用户确认后改 `已确认`。`待审核` 卡片**不作为标准译名依据**（与 `[待审核]` 术语同理）
- 版本标注遵循 `indexing-rules`（`[通用]`/`[1.21+]` 等）
- 卡片创建/内容变更后，同步更新 `indexes/knowledge/` 下对应索引

### 与相关机制的区分

| 机制 | 记录什么 | 落点 |
|------|----------|------|
| 术语登记（`term-registration`） | 标准译名（英→中） | `_uncategorized.csv` |
| 通用知识卡（本节） | 词汇/概念的知识要点、语境用法、翻译注意事项 | `<术语>.md` 知识卡 |
| 陷阱词（`use-glossary`） | 看似普通实为术语的查词触发词 | `trap_words.md` |

## 经验文件维护（.github/experience/，广义知识）

`.github/experience/` 沉淀翻译经验（广义知识），维护如下。

### 文件地图

| 文件 | 内容 | 写入门槛 |
|------|------|----------|
| `asr_fixes.md` | ASR 误识别（跨视频通用，按正确词聚合） | 只收跨视频可复用；~100 条上限 |
| `coverage_log.md` | 数据源覆盖流水 | 每视频一行流水 |
| `source_experience.md` | 数据源经验沉淀（收敛型） | 见「经验提炼规则」 |
| `glossary_categories.yaml` | 术语表分类预判关键词 | 文件头注释（Agent 协助维护） |
| `trap_words.md` | 术语陷阱词 | `use-glossary` |

### 写入规则（指针）

- ASR 分层登记 → `term-registration`「ASR 映射登记」（跨视频通用→全局 / 视频专属→`_work/<视频名>/asr_fixes.md`）
- 阶段三流水 + 经验提炼 → `translate-redstone` 阶段三

### 经验提炼规则（source_experience.md 写入门槛）

写之前逐条套"三问"（能力 / 盲区 / 下次去哪），**只有第 3 问的答案入库**。
入库条目必须为 **IF-THEN 句式**：`当〈触发条件〉时 → 查〈数据源/动作〉，因为〈原因〉。（案例：〈一行内嵌〉）`
写完**自检四问**：
1. 删掉日期/视频名/数字后还成立吗？——不成立 → 回 `coverage_log.md`
2. 能否指导下一个视频的决策？——不能 → 回 `coverage_log.md`
3. 写明了触发条件（何时用）吗？——没写 → 补上
4. 与已有条目重复吗？——重复 → 只合并案例，不新开条
若一次产出 >5 条"规律"→ 重新过一遍以上判据（规律是稀缺的，过多说明在罗列事实）。

### 日常维护（第③层，不随翻译触发）

- `asr_fixes.md` 超 ~100 条 → 将低价值/视频专属项移走归档到 `_work/<视频名>/asr_fixes.md`
- `source_experience.md` 重复结论去重、存量日志/经验定期提炼
- 破坏性清理（归档/压缩）遵循 `AGENTS.md` 核心原则 #6，**提示用户手动执行**

## 更新索引

内容变更后，更新 `indexes/knowledge/` 下对应索引文件。条目格式与版本标注按 `indexing-rules` Skill 执行。
- **时间戳**：索引文件的「生成时间/最近更新」是刷新判断依据，内容实质变更时同步更新；`_uncategorized.csv` 这类高频变动区只保留静态占位，其词条变动不触发索引更新、不更新时间戳（见 `indexing-rules`「索引时间戳与更新策略」）

## 运行脚本

| 操作 | 命令 |
|------|------|
| 拆分术语表 | `python scripts/glossary_split.py` |
| 检查术语表 | `python scripts/glossary_split.py --check` |
| 同步 submodule | `git submodule update --remote` |
| 检查索引是否过期 | `python scripts/check_index_stale.py` |

## 安全规则

- 删除规则见 `AGENTS.md` 核心原则 #6（禁止自动删除，需清理时提示用户手动操作）。
- 只写入 `knowledge/`、`indexes/`、`.cache/`（脚本生成），不触碰 `_repos/`（只读）。
- 修改 `knowledge/` 前确认版本信息准确。
