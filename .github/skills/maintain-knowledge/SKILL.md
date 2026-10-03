---
name: maintain-knowledge
description: 维护项目第一类知识（knowledge/）与索引（indexes/）的总入口：目录速查、维护任务路由（细节在各扩展 Skill）、通用知识卡维护、运行脚本、安全规则。修改 knowledge/、新建知识卡、或需决定"用哪个维护 Skill"时参考。
---

# 知识库维护

Agent 负责维护第一类知识（`knowledge/`）及相关设施。

## 目录速查

| 目录 | 性质 | 维护方式 |
|------|------|----------|
| `knowledge/` | 第一类，Git 追踪 | 人工撰写/审核，Agent 辅助 |
| `.cache/` | 第二类，Git 忽略 | 脚本生成，禁止手动编辑 |
| `_repos/` | 第三类，Submodule | 上游维护，只读引用 |
| `indexes/` | 索引，Git 追踪 | 内容变更后同步更新 |
| `.github/experience/` | 经验（广义知识），Git 追踪 | 随翻译追加 + 日常维护（见「经验文件维护」） |
| `scripts/` | 工具脚本 | 按需修改 |

## 维护任务决策

| 任务 | 用哪个 Skill |
|------|-------------|
| 术语登记（英→中） | `term-registration` |
| CSV 读写/表头列含义 | `csv-rules` |
| 索引格式/版本/时间戳 | `indexing-rules` |
| 外部仓库索引生成/更新判断 | `index-repos`（`scripts/check_index_stale.py`） |
| 术语表加载/术语源优先级 | `use-glossary` |
| 术语表统计/常驻集复审 | 本 Skill [#术语表统计与常驻集复审](#术语表统计与常驻集复审) 节 |
| Wiki 抓取/兜底 | `wiki-tools` |
| 通用知识卡 | 本 Skill [#通用知识卡](#通用知识卡) 节 |
| 经验/日志维护（ASR 分层、coverage 流水、经验提炼、超限整理） | 写入按 `term-registration` / `translate-redstone` 阶段三；超限整理按本 Skill「经验文件维护」 |

## 术语体系

三个"词汇表"的区分表见 `use-glossary` Skill 开头（项目术语库 / 拆分术语缓存 / 上游术语表），此处不重复。

维护视角：
- Agent **只写入** `knowledge/01_terminology/_uncategorized.csv`，不触碰 `.cache/glossary/`（脚本生成）与 `_repos/`（只读）
- 具体的术语文件清单见 `indexes/knowledge/`

## knowledge/ 目录结构

此目录不仅包含游戏术语，还包含翻译所需的各类参考信息：

```
knowledge/
├── _template_knowledge.md      # 通用知识卡模板（唯一权威，位于 knowledge/ 根）
├── 01_terminology/             # 术语表 CSV
└── 02_mechanic/                # 知识卡（唯一落点）

knowledge/01_terminology/
├── _example.csv            # 表头模板（所有 CSV 共享同一表头）
├── _uncategorized.csv      # Agent 自动登记的新术语（待人工分拣）
├── *.csv                   # 人工分拣后的各类术语表（redstone.csv、people.csv 等）
└── ...                     # 按需扩展
```

所有 CSV 共用 `_example.csv` 中的表头。Agent 只写入 `_uncategorized.csv`，不创建其他 CSV。具体的术语文件清单见 `indexes/knowledge/`。

## 术语同步机制

Agent 只写入 `_uncategorized.csv`，不擅自归类。人工定期分拣到对应类别的 CSV。

登记流程（触发条件、同步步骤、ASR 映射登记）统一按 `term-registration` Skill 执行。

### 文件格式与规范

- 长篇机制说明：`knowledge/02_mechanic/<词条>.md`（含 YAML frontmatter）
- 术语/人物/组织：CSV，共享 `_example.csv` 表头；Agent 新建术语只能写入 `_uncategorized.csv`
- **CSV 表头列含义**：`csv-rules` Skill（唯一权威）
- **CSV 读写规范**：`csv-rules` Skill（编码/解析/写入）
- **来源规范**（2026-09-17；登记细则见 `term-registration`，模板见 `knowledge/_template_knowledge.md`）：知识记录（术语 CSV 的 `notes`、知识卡的 `source`/“来源”、索引“来源”行、`experience/` 条目）的来源须满足：
  - **可移植**：只写**原始资料源**（`zh wiki<页面>页`、`Mojang 官方用语`）或**仓库内引用**（`_repos/…`、`knowledge/…`、`.github/…`）；**禁止**指向 `.cache/`（脚本生成的缓存）与 `_work/`（工作产物）——换环境即失效
  - **视频必带唯一 ID**：合格形式为 `<视频标题>（<视频 ID>）`，**至少** `<视频 ID>`（如 `A Closer Look at Minecraft's Storage Blocks（ZXGpmaIcMMo）`、`uVOFckoMdIU 视频 00:26:48`）。ID（YouTube ID / B站 BV 号）是本项目视频主键（`_input/<ID>_*.srt` 同名），标题会被改、作者不唯一——**只写标题或只写作者（如“cubicmetre 视频”“（FX）”）不算合格来源**；只写 ID 时标题可从 `.github/experience/coverage_log.md`（视频流水表）反查；位置定位（`c<块号>` / `HH:MM:SS`）附末尾；确实无法确定 ID 时标 `[ID 待补]`
- **版本标注**：`indexing-rules` Skill

## 通用知识卡

记录一条**词汇/概念/机制**的知识要点——定义、语境用法、翻译注意事项等（通用术语 CSV 未覆盖的部分）。

### 模板

- 唯一权威模板：`knowledge/_template_knowledge.md`
- 每词/每概念一卡，文件命名 `<英文术语>.md`，**统一放 `knowledge/02_mechanic/`**——该目录承载各类主题的知识卡，不按“术语 / 机制”分家
- 卡片结构：YAML frontmatter（`term`/`aliases`/`category`/`source`/`version`/`status`/`license`）+ 3 分区（`要点`/`翻译注意事项`/`备注`）

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
| 陷阱词（`use-glossary`） | 防固有思维漏查的陷阱词（触发层，与词汇表正交） | `trap_words.md` |

## 经验文件维护

`.github/experience/` 沉淀翻译经验（广义知识），维护如下。

### 文件地图

| 文件 | 内容 | 写入门槛 |
|------|------|----------|
| `asr_fixes.md` | ASR 误识别（跨视频通用，按正确词聚合） | 只收跨视频可复用；**不设硬上限**（超限靠注入时筛选，见「日常维护」） |
| `coverage_log.md` | 数据源覆盖流水 | 每视频一行流水 |
| `source_experience.md` | 数据源经验沉淀（收敛型） | 见「经验提炼规则」 |
| `glossary_categories.yaml` | 术语表分类关键词（**已不驱动加载**，仅人工参考） | 文件头注释（Agent 协助维护） |
| `trap_words.md` | 防固有思维漏查的陷阱词（触发层，与词汇表正交） | `use-glossary`（随视频识破即追加） |

### 写入规则

- ASR 分层登记 → 「term-registration#ASR 映射登记」（跨视频通用→全局 / 视频专属→`_work/<视频名>/asr_fixes.md`）
- 阶段三流水 + 经验提炼 → `translate-redstone` 阶段三

### 经验提炼规则

写之前逐条套"三问"（能力 / 盲区 / 下次去哪），**只有第 3 问的答案入库**。
入库条目必须为 **IF-THEN 句式**：`当<触发条件>时 → 查<数据源/动作>，因为<原因>。（案例：<一行内嵌>）`
写完**自检四问**：
1. 删掉日期/视频名/数字后还成立吗？——不成立 → 回 `coverage_log.md`
2. 能否指导下一个视频的决策？——不能 → 回 `coverage_log.md`
3. 写明了触发条件（何时用）吗？——没写 → 补上
4. 与已有条目重复吗？——重复 → 只合并案例，不新开条
若一次产出 >5 条"规律"→ 重新过一遍以上判据（规律是稀缺的，过多说明在罗列事实）。

### 日常维护

- `asr_fixes.md` **不按“通用/专属”删条目**——判据无法成立：条目出自现有语料，
  按“在几个视频出现”判必然循环（单视频条目可能只是别的视频还没遇到该话题）。
  超限时改用**注入时筛选**（扫本视频字幕命中即注入，实测省 ~89% 字符），全局表全量积累
- 确需下沉视频专属项时用 `python scripts/asr_fixes_scope.py`（出可勾选清单，非日常必跑）
- `source_experience.md` 重复结论去重、存量日志/经验定期提炼
- 破坏性清理（归档/压缩）遵循 `AGENTS.md` 核心原则 #6，**提示用户手动执行**

## 更新索引

内容变更后，更新 `indexes/knowledge/` 下对应索引文件。条目格式与版本标注按 `indexing-rules` Skill 执行。
- **时间戳**：索引文件的“生成时间/最近更新”是刷新判断依据，内容实质变更时同步更新；`_uncategorized.csv` 这类高频变动区只保留静态占位，其词条变动不触发索引更新、不更新时间戳（见 「indexing-rules#索引时间戳与更新策略」）

## 术语表统计与常驻集复审

常驻表清单由**表价值排名**得出（口径见 `use-glossary`），反映的是**统计当时**的语料。
下列情况应复算：新增/退役整张表、`_uncategorized.csv` 分拣后显著变小或新分类表增大、
累计处理了若干新视频。

1. **统计**（离线全量口径 = 主口径）：
   ```bash
   python scripts/glossary_hit_rate.py --root _input --history _work/_hit_rate_history.md
   ```
   - 语料用 `_input/`（待处理原始字幕）；`--root` 可多次合并多来源；每个根下支持
     **视频目录**（含 `00`/`01`/`scan_terms.txt`）与**平铺 `.srt`** 两种形态
   - **语料须 >10 个视频**：低于阈值脚本会告警、报告标注不可信——素材变少会误判，
     **不得据此改常驻表**，先补充字幕
2. **读报告** `_work/_glossary_hit_rate.md`：看**二、实际命中**下的“常驻候选”
   （净命中率 ≥80% 且噪声率 <30%）与“零命中表”；**六、噪声观测**的高频词命中是扫描
   判据弱，不是该表重要。**不用“现行扫描”列**——它读历史 `scan_terms.txt`，受当时加载
   范围限制，未加载的表必显示 0%（假零）
3. **判断**：新表进入原常驻表区间 → 纳入；原常驻表净命中率显著下降 → 移出。先看
   `_work/_hit_rate_history.md` 趋势（每次复算追加一行）区分漂移与单次波动
4. **改清单**：`scripts/glossary_load_plan.py` 的 `RESIDENT`（**唯一控制点**）——
   表清单与词数用 `--list-resident` 查（**不写进文档**）；同步 `use-glossary` /
   `redstone-preprocess` 中引用的表名

**口径与局限**：离线口径是**字面匹配**（术语词形恰为通用英文词时必然误命中，
如 `and` = 与门）→ 看净命中率与噪声率，不只原始命中率；语料是**已处理视频**，
对**新增领域**无预测力（新领域首视频仍靠门禁候选机制）；表价值公式偏重**复用广度**，
会低估低复用但不可缺的表（人名/专名）→ 按领域判断补充。

**表内冗余**（同一流程顺带做）：各分类表与 `_uncategorized.csv` 长期只增不减，会积累
**可推断词**（LLM 默认就能译对，如 `compare mode`→比较模式）——不改变输出，只是噪声。
判据 = `term-registration#不可推断判定`，范围优先 `_uncategorized.csv`。
**不可机械校验**（脚本只能给字面线索、错判率高，会清掉真术语）→ **只出候选交用户裁定**。
本项管“表里的词该不该在”，复审管“表该不该加载”；冗余词清掉后表变小，可能触发复算。

## 运行脚本

| 操作 | 命令 |
|------|------|
| 拆分术语表 | `python scripts/glossary_split.py` |
| 检查术语表 | `python scripts/glossary_split.py --check` |
| 同步 submodule | `git submodule update`（**同步第三方仓库纪律**；拉上游最新并重新锁定 → `git submodule update --remote`） |
| 检查索引是否过期 | `python scripts/check_index_stale.py` |
| 检查缓存新鲜度 | `python scripts/refresh_cache.py --dry-run`（Mojang/TechMC/Wiki 三类）；单页判定用 `--check-page <页面...>`（退出码 1 = 有需处理项） |
| 刷新 Wiki 缓存（wikitext/lossless） | `python scripts/fetch_wiki.py --refresh`（不带页面名 = 全量，维护场景）；**按需单页**加页面名（如术语查证命中过期缓存时）见 [wiki-tools#缓存过期与主动刷新](../wiki-tools/SKILL.md#缓存过期与主动刷新)；`--dry-run` 只探测；规范见 `docs/WIKI_CACHE_FORMAT.md` |

## 安全规则

- 删除规则见 `AGENTS.md` 核心原则 #6（禁止自动删除，需清理时提示用户手动操作）。
- 只写入 `knowledge/`、`indexes/`、`.cache/`（脚本生成），不触碰 `_repos/`（只读）。
- 修改 `knowledge/` 前确认版本信息准确。
