---
name: use-glossary
description: 项目术语表（Mojang/TechMC/项目自有）的使用规范、类别预判、加载策略和安全规则。翻译红石内容或检索术语时自动参考。
---

# 术语表使用规范

本项目涉及三个"词汇表"，容易混淆，必须先区分：

| 名称 | 位置 | 性质 | 说明 |
|------|------|------|------|
| **上游术语表** | `_repos/techmc-glossary/` | 第三类，只读 Submodule | TechMC-Glossary 社区维护的合并 CSV |
| **拆分术语缓存** | `.cache/glossary/` | 第二类，脚本生成 | 从上游按 Category 拆分的独立 CSV |
| **项目术语库** | `knowledge/01_terminology/` | 第一类，人工维护 | 本项目的译名标准、人物/组织名录等 |

**Agent 翻译时使用的术语来自拆分缓存 + 项目术语库，不是上游源文件。**

> 此表为"三个词汇表"区分的唯一权威来源，其他 Skill（如 `maintain-knowledge`）引用此处。

## 安全规则

- 删除规则见 `AGENTS.md` 核心原则 #6（禁止自动删除，`.cache/glossary/` 需清理时提示用户手动执行）。
- 拆分脚本只写入 `.cache/glossary/`（Git 忽略），不触碰项目其他目录。

## 核心规则

1. **禁止直接使用 `_repos/techmc-glossary/TechMC Glossary.csv`**（源文件是合并格式，且可能过时）
2. **必须使用 `.cache/glossary/` 下的拆分文件**（按类别独立，Agent 按需加载）
3. **使用前检查是否需要更新**
4. **查词/扫描用 `glossary_lookup.py`**（只读，自动 L1→L1.5→L2；手工 grep 仅作兜底）
   - 查单个词：`python scripts/glossary_lookup.py query <term> [<term>...]`
   - **扫文本找已收录术语（数据驱动触发，取代"像不像术语"判断）**：`python scripts/glossary_lookup.py scan <srt|chunk> --categories <分类> --levels L1,L2`。`--categories` **只按文件名过滤 L2**（`.cache/glossary/<文件名>.csv`）；L2 文件名与 `glossary_categories.yaml` 分类**部分重叠但不对应**（L2 另有 `general/other/people`），勿假设完全对应；**L1 始终全量加载**（体量小，文件分类与 yaml 是另一套命名）；L1.5（Mojang，再一套命名）需显式 `--levels L1,L1.5,L2`

> **语义联想为主，机械查找补漏**（2026-08-03 用户定调）：ASR 误识别修正、术语语义/语境理解、相关性判断靠 **Agent 自身的语义联想/推理**（注入领域术语集作上下文），**不用字符串相似度等算法**；"联想"=Agent 自己的语言理解，**非调用外部 LLM/API**。机械查找（`scan`）仅作**补充**——字面精确匹配把"已登记词确实出现"找全，治"已收录却漏翻"，不做任何理解/判定。

## 四级查找（位置与执行）

| 级 | 定位 | 查找位置 | 执行 |
|----|------|----------|------|
| **L1** | 热数据 | `knowledge/01_terminology/*.csv`、`.cache/mojang/redstone.csv` | `glossary_lookup.py` 自动 |
| **L1.5** | Mojang 非红石 | `.cache/mojang/*.csv` | `glossary_lookup.py` 自动；grep 兜底 |
| **L2** | 温数据 | `.cache/glossary/*.csv`（techmc 社区拆分译名）、`_repos/storage-archive/dictionary/`（存储科技术语词典，2026-08-28 新增源） | `glossary_lookup.py`、`dictionary_lookup.py` |
| **L3** | 未命中 | — | 入"待查列表" → translate-redstone §1.2 集中补齐 |

- **执行建议**：首选 `python scripts/glossary_lookup.py <term> [<term>...]`（只读，自动按 L1→L1.5→L2 批量查询，命中输出来源）；**L2 存储科技术语词典（`_repos/storage-archive`）另用 `python scripts/dictionary_lookup.py query/scan` 查（含完整定义/缩写）**；工具不覆盖时用 grep_search 按上表位置兜底
- **新增词汇表源**：按上表「查找位置」判断归属级（新增 Mojang 表→L1.5；新增社区分类/词典→L2；新增项目库 CSV→L1），更新位置即可，Agent 据表快速识别（storage-archive 与 techmc 同属社区源，仅查询工具不同，**不新增层级**）

## 工作流程

### 翻译/检索前

```
1. 运行 python scripts/refresh_cache.py（统一检查三类缓存：Mojang/TechMC 自动刷新，Wiki 只告警不自动抓取；或按需单独 glossary_split.py --check）
2. 按下方"类别预判"规则确定领域 → 加载 .cache/glossary/<相关类别>.csv
```

### 类别预判（翻译前确定领域）

为节省上下文，不加载全部术语表。通过**视频标题/简介 + SRT 前 20 句**的关键词密度判断领域。

**规则定义在** `.github/experience/glossary_categories.yaml`。该文件由 Agent 协助维护（见下方"配置文件自维护"）。

预判流程：
1. 读 `.github/experience/glossary_categories.yaml`
2. 扫描视频元数据 + SRT 前 20 句，统计每个 `category` 下 `keywords` 的命中次数
3. 命中 ≥2 次的分类 → 作为**候选起点**，加载对应 `.cache/glossary/<category>.csv`（同名文件存在时）
4. 始终加载 `always_load` 中列出的分类
5. 若所有分类命中均 <2 次 → 进入"无法判断"流程

> **语义扩展（非机械对应）**：关键词命中只是**提示起点**，识别出的类别**不是唯一输出**——一个视频往往横跨多个方面（存储视频也可能涉及机械/人名/通用）。Agent 应在命中基础上**按语义关系**判断还要加载哪些相关词汇表（`scan --categories` 传可多个的 L2 文件名）；`knowledge/01_terminology/`（L1）由 `scan` 始终全量加载，其文件名与 yaml 分类是两套命名，勿按同名机械对应。勿把"命中≥2"当成机械的 1:1 加载规则。

> **领域确认（阶段〇必做交互，不得静默跳过）**：无论关键词命中与否，预判都要产出一个**领域判断**（分类 + 依据：命中关键词/语义线索），并在阶段〇**报告给用户确认**（轻量一句，如「预判领域：slimestone，依据 flying machine/piston ×3，对吗？」）。**当无法确定时**——所有分类命中均 <2 次、语义判断拿不准、或拿不准是否跨领域——**必须停下来**进入下方「无法判断时的处理」，列出候选请用户选择；**不得靠语义扩展静默加载跳过确认**（曾发生：Agent 凭语义直接加载分类、跳过领域确认，导致 `glossary_categories.yaml` 关键词长期零增长）。确认后若本视频暴露了该分类未收录的高频词，**顺手追加**到 yaml `keywords`（见下方「配置文件自维护」），使预判文件随正常流程积累。

### 无法判断时的处理（必须交互，配置文件自维护入口）

当所有分类命中均 <2 次、或语义判断拿不准、或拿不准是否跨领域时——**必须**执行以下交互，不得静默跳过：

1. 从 SRT 前 20 句中提取出现 ≥2 次的技术名词，列出清单给用户：
   ```
   无法自动判断视频领域。以下是在字幕开头高频出现的技术名词：
   - update suppression（3次）
   - CCE（2次）
   - light update（2次）
   
   请确认这些词属于哪个分类（可选多个），或输入自定义分类名：
   [mechanical / slimestone / tree_farm / mob_farm / storage / computational / contraptions / glitch / 1.12.2_magic]
   ```
2. 用户确认后，Agent 编辑 `.github/experience/glossary_categories.yaml`，将新关键词追加到对应分类的 `keywords` 列表中
3. 然后按确认的分类加载术语表，继续翻译流程
4. **注意**：Agent 只能追加关键词，不能修改分类结构或删除已有关键词

### 运行中反哺（非预期命中 → 回填 categories）

阶段〇预判只是起点：翻译/扫描过程中若在**非当前预判集合**的分类词汇表（L2 文件 / 知识卡 `02_mechanic/` / L1.5 非红石按需）命中并实际使用了词，说明该视频实际涉及该分类，应回填 yaml：

- **识别**：`scan --categories` 命中的词若来自未预判的 L2 分类、或 Agent 手动查词/读知识卡命中了未预判分类 → 记录该分类 + 实际命中的词
- **回填**：阶段末（阶段一/二结束）把该分类纳入 yaml——追加 `keywords`（含实际命中词）或标注「该视频涉及」，**交用户确认后写入**（Agent 提案 + 用户确认，同上方「无法判断时的处理」）
- **目的**：yaml 随真实使用积累，避免「预判一次定终身」导致分类关键词与实际领域脱节（与「领域确认必做交互」互补：预判时确认 + 运行中反哺）

### 陷阱词清单（防固有思维漏查的查词触发词）

部分术语是**拼写正常的普通英文单词**（如 `filter`、`main storage`），按"看着像术语"的直觉扫描会漏过、不触发查词。此类词按分类沉淀在 `.github/experience/trap_words.md`——它是与普通词汇表（术语 → 译名）**正交的防呆提示层**：词汇表负责"查到是什么"，trap_words 负责"提醒记得去查"。

- **加载**：类别预判命中某分类时，同时加载该分类的陷阱词清单
- **扫描**：遍历字幕时，对清单中的词（含词形变体）**强制走 L1/L2 术语查找**，即使它们看起来是普通英文、即使已登记入 L1（入 L1 只保证 `scan` 字面覆盖，不保证语义扫描想起查）
- **维护**：识破「没想到是术语」的新陷阱词就追加到 `trap_words.md`（**与是否已登记入 L1 无关**，只追加不删改既有条目，分类与 `glossary_categories.yaml` 一致）；已登记入 `_uncategorized.csv`/`knowledge/` 的词照常走 `term-registration`（登记是知识层，trap_words 是触发层，两者独立）

### 翻译日志 vs 配置文件自维护

两个机制各司其职，不可混淆：

| | `.github/experience/coverage_log.md` + `source_experience.md` | `.github/experience/glossary_categories.yaml` |
|---|---|---|
| 记录什么 | 数据源检索流水（coverage_log）+ 可复用经验结论（source_experience，IF-THEN） | 领域关键词→分类映射 |
| 维护者 | Agent 自动追加 + 提炼 | Agent 提案 + 用户确认后写入 |
| 触发时机 | 翻译后（阶段三） | 翻译前（阶段〇无法判断时） |
| 目的 | 优化"去哪找" | 优化"加载哪些术语表" |

### 术语对照规则

- CSV 中 `Chinese` 列为标准译名，`Description (Chinese)` 列为中文释义
- `English` 列为标准英文术语
- 若 CSV 中无对应术语，标记 `[待审核: English Term]`
- 严禁自创译名覆盖已有标准

### CSV 解析注意事项

- 编码、解析、写入统一按 `csv-rules` Skill 执行（`utf-8-sig` 读 / `utf-8` 写、`csv` 模块解析）
- 一句话要点：`definition`/`description`/`notes` 列常含逗号，**禁止** `split(',')` 或 `grep_search` 按逗号分列，提取译名务必读取完整行用 `csv.DictReader` 解析

## 注意事项

- `.cache/glossary/` 是 Git 忽略的临时缓存，可随时删除后重跑脚本
- 上游术语表通过 `git submodule update --remote` 同步
- 如果 `--check` 报错（源文件缺失），可能是 submodule 未初始化，运行 `git submodule update --init`
