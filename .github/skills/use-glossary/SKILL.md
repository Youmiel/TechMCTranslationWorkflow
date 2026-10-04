---
name: use-glossary
description: 项目术语表（Mojang/TechMC/项目自有）的使用规范、加载集判定（常驻+命中数候选+用户门禁）、术语源优先级和安全规则。翻译红石内容或检索术语时自动参考。
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
   - **扫文本找已收录术语（数据驱动触发，取代“像不像术语”判断）**：`python scripts/glossary_lookup.py scan <srt|chunk> --categories <分类> --levels L1,L2`。
     - `--categories` **只按文件名过滤 L2**（`.cache/glossary/<文件名>.csv`）
     - L2 文件名与 `glossary_categories.yaml` 分类**部分重叠但不对应**（L2 另有 `general` / `other` / `people`），勿假设完全对应
     - **L1 始终全量加载**（体量小，文件分类与 yaml 是另一套命名）
     - L1.5（Mojang，再一套命名）需显式 `--levels L1,L1.5,L2`

> **语义联想为主，机械查找补漏**（用户定调）：ASR 误识别修正、术语语义/语境理解、相关性判断靠 **Agent 自身的语义联想/推理**（注入领域术语集作上下文），**不用字符串相似度等算法**；"联想"=Agent 自己的语言理解，**非调用外部 LLM/API**。机械查找（`scan`）仅作**补充**——字面精确匹配把"已登记词确实出现"找全，治"已收录却漏翻"，不做任何理解/判定。

## 术语源优先级

| 级 | 定位 | 查找位置 | 执行 |
|----|------|----------|------|
| **L1** | 热数据 | `knowledge/01_terminology/*.csv`、`.cache/mojang/redstone.csv` | `glossary_lookup.py` 自动 |
| **L1.5** | Mojang 非红石 | `.cache/mojang/*.csv` | `glossary_lookup.py` 自动；grep 兜底 |
| **L2** | 温数据 | `.cache/glossary/*.csv`（techmc 社区拆分译名）、`_repos/storage-archive/dictionary/`（存储科技术语词典） | `glossary_lookup.py`、`dictionary_lookup.py` |
| **L3** | 未命中 | — | 入"待查列表" → [集中补齐](../redstone-preprocess/SKILL.md#22-集中补齐) |

- **执行建议**：首选 `python scripts/glossary_lookup.py <term> [<term>...]`（只读，自动按 L1→L1.5→L2 批量查询，命中输出来源）；**L2 存储科技术语词典（`_repos/storage-archive`）另用 `python scripts/dictionary_lookup.py query/scan` 查（含完整定义/缩写）**；工具不覆盖时用**全文搜索工具**按上表位置兜底
- **新增词汇表源**：按上表“查找位置”判断归属级（新增 Mojang 表→L1.5；新增社区分类/词典→L2；新增项目库 CSV→L1），更新位置即可，Agent 据表快速识别（storage-archive 与 techmc 同属社区源，仅查询工具不同，**不新增层级**）
- **表头差异由适配层统一**：三套词汇表表头不同，解析一律走 `scripts/shared/glossary_sources.py`（**单一权威**：按列名取、位置兜底；含 `;` 同义词与 `(aka X)` 别名展开、缩写过滤）。**新增词汇表只需在该模块补列名**，勿在各工具里另写解析——曾因 `render_preprocess_prompt.load_glossary` 按固定列位取值，**L1 项目库整表被静默丢弃**（484 行 → 0 行），阶段〇 ASR 纠错长期拿不到项目自定译名
- **阶段〇 ASR 纠错通道的注入面** = **常驻集 + 门禁后保留的候选表**（术语识别通道同源）。**L1.5 默认不注入**——该层收录 `water`/`sand`/`thing` 类通用词，注入既稀释注意力又会诱发误纠（把本身正确的词“纠”成表内的词）。**缩写列（`short_form` / `Short Form`）一并注入**：`MSPT`/`CCE`/`DPE` 这类缩写正是 ASR 最易错、最需消歧的词形
- **常驻集**（无条件加载）：`knowledge/{engineering,_uncategorized,community,proper_nouns}.csv` + `mojang/redstone.csv` + `glossary/general.csv`
  - 前 5 张由表价值排名得出（`V = √无条件份额 × √次/词 ÷ 表词数`；无条件份额 = share × 广度，修正条件平均丢失广度的问题）
  - **`proper_nouns` 是特例常驻**：人名/社区名几乎每个视频都会出现，按需加载收益低；而模式触发会漏检（宽模式几乎全触发、等价常驻；紧模式漏掉大半）→ 直接常驻，保证不漏
  - **实际表清单与词数一律用 `python scripts/glossary_load_plan.py --list-resident` 查，文档与报告不写死**（随表增删而变；写死必滞后）

## 工作流程

### 翻译/检索前

```
1. 运行 python scripts/refresh_cache.py（统一检查三类缓存：Mojang/TechMC 自动刷新，Wiki 只告警不自动抓取——Wiki 过期页由查证/查询时主动刷新，见 [wiki-tools#缓存过期与主动刷新](../wiki-tools/SKILL.md#缓存过期与主动刷新)；或按需单独 glossary_split.py --check）
2. 跑 python scripts/glossary_load_plan.py <00_subtitle_snapped.srt> 定加载集（常驻 + 命中数候选）
3. 把报告报用户门禁确认 → 用户剔除后 --record 记入日志
```

### 加载集判定

加载集 = **常驻集 + 候选表**，候选由字幕实际命中得出：

```
python scripts/glossary_load_plan.py <00_subtitle_snapped.srt>
```

脚本做三件事：

1. **常驻集无条件加载**
2. **用完整字幕逐表扫描全部非 L1.5 表** → `命中词条数 ≥ 3` 的表列为**候选**
   （报告附：命中数、命中样例、**未达阈值全貌**、常驻表命中对照）
3. **把报告报用户门禁确认**——由用户剔除非必要表；裁定后：

```
python scripts/glossary_load_plan.py <字幕> --record "表1,表2"   # 剔除
python scripts/glossary_load_plan.py <字幕> --record            # 候选全保留
```

**为何用阈值而非算法挑表**：子代理上下文远未用满，**宁可多纳候选、由用户在门禁处剔除**
——不用算法替代人的判断。阈值不合适时用户可 `--threshold N` 调整
（日志里的“未达阈值”列就是调阈值的依据）。

**计数用“命中词条数”而非总次数**：总次数被长视频与重复词支配——一个噪声词反复出现即可刷高。
条数单位是表内词条（`;` 同义词与 `(aka X)` 别名已展开为独立词条），不折叠形态变体。

#### 门禁交互：阶段一必做，不得静默跳过

**必须把候选清单报给用户**，格式大致：

```
拟加载 = 常驻集 + 候选 2 表：
  redstone_concepts.csv（命中 8 条：block update / component / loop …）
  common.csv（命中 5 条：instrument / slot …）

以下表未达阈值：contraptions:1、storage:1 …

请剔除用不到的表（直接回复表名，或我跑 --record）
```

- 用户剔除后**务必跑 `--record`** —— 否则日志缺记，长期分析失效
- 用户说“都行/不剔” → 跑 `--record`（无参）= 候选全保留

#### 门禁日志：自动记录，供长期分析

`_work/<视频>/glossary_gate_log.md`（**追加式**，每次门禁写一行）：

| 日期 | 视频 | 阈值 | 候选（表:命中） | 未达阈值（表:命中） | 用户剔除 | 最终增载 | 备注 |
|---|---|---|---|---|---|---|---|

**为何要记“未达阈值”的表**：只记候选 → 看不到“差一点就进的”，日后无法判断
阈值定高还是定低；哪些表反复冒头却总差一点，正是调阈值的依据。

### 无法判断时的处理

命中数方案下**不会出现“无法判断”**（总有命中数可数），而是出现**无候选**：

- 报告显示“**（无候选）**”时 → 说明字幕未触及任何阈值以上的表
- **处理**：直接告知用户“无领域表超出阈值，仅用常驻集”，并附上未达阈值表全貌供用户
  判断是否仍有需要的表；用户可手动指定额外加载的表（或降 `--threshold`）
- **不得因无候选而静默跳过报告**——用户仍需知道探到了什么

### 运行中反哺：加载集修正

> 扫到未加载表里的词 → 记入日志，供调阈值与改进门禁。

加载集由“命中数候选 + 用户门禁”定出，两个环节都可能漏：阈值偏低误纳、用户剔除错表。
故运行中若发现真实需要的词来自**未加载的表**，应记录：

- **识别**：术语识别 / 查词 / 读知识卡时命中了**未加载表**（未达阈值且未手动指定、或被用户剔除）里的词，
  且确认本视频确实需要它
- **处理**：将 `表名 + 实际命中词` 报用户；用户认同则**立即补充加载**继续流程
- **沉淀**：阶段末把这次“漏刷”记入该视频的 `glossary_gate_log.md` 备注（或用 `--note`），
  作为**调阈值 / 判断哪张表总被错剔**的依据
- **注意**：`--record` 只记“用户剔了什么”，事后发现的漏刷要手动追记备注

> **旧的 keywords 回填机制已取消**——加载集不再由 `glossary_categories.yaml` 决定，
> 回填 keywords 不再影响加载。yaml 仅留作人工参考（见其文件头警示）。

### 陷阱词清单

部分术语是**拼写正常的普通英文单词**（如 `filter`、`main storage`），按"看着像术语"的直觉扫描会漏过、不触发查词。此类词按分类沉淀在 `.github/experience/trap_words.md`——它是与普通词汇表（术语 → 译名）**正交的防呆提示层**：词汇表负责"查到是什么"，trap_words 负责"提醒记得去查"。

- **加载**：清单**整体注入**翻译与术语识别任务的 subagent prompt（渲染脚本 `traps` 先验），不随门禁加载集裁剪
- **扫描**：遍历字幕时，对清单中的词（含词形变体）**强制走 L1/L2 术语查找**，即使它们看起来是普通英文、即使已登记入 L1（入 L1 只保证 `scan` 字面覆盖，不保证语义扫描想起查）；翻译侧则直接按清单的标准译名/禁译列执行
- **维护**：识破“没想到是术语”的新陷阱词就追加到 `trap_words.md`（**与是否已登记入 L1 无关**，只追加不删改既有条目）；已登记入 `_uncategorized.csv`/`knowledge/` 的词照常走 `term-registration`（登记是知识层，trap_words 是触发层，两者独立）

### 翻译日志 vs 配置文件自维护

两个机制各司其职，不可混淆：

| | `.github/experience/coverage_log.md` + `source_experience.md` | `.github/experience/glossary_categories.yaml` |
|---|---|---|
| 记录什么 | 数据源检索流水（coverage_log）+ 可复用经验结论（source_experience，IF-THEN） | 领域关键词→分类映射（**已不驱动加载**，仅人工参考） |
| 维护者 | Agent 自动追加 + 提炼 | Agent 提案 + 用户确认后写入 |
| 触发时机 | 翻译后（阶段三） | 仅在人工查阅时 |
| 目的 | 优化"去哪找" | 保留分类语义供参考 |

### 术语对照规则

- CSV 中 `Chinese` 列为标准译名，`Description (Chinese)` 列为中文释义
- `English` 列为标准英文术语
- 若 CSV 中无对应术语，标记 `[待审核: English Term]`
- 严禁自创译名覆盖已有标准

### CSV 解析注意事项

- 编码、解析、写入统一按 `csv-rules` Skill 执行（`utf-8-sig` 读 / `utf-8` 写、`csv` 模块解析）
- 一句话要点：`definition`/`description`/`notes` 列常含逗号，**禁止** `split(',')` 或**全文搜索工具**按逗号分列，提取译名务必读取完整行用 `csv.DictReader` 解析

## 注意事项

- `.cache/glossary/` 是 Git 忽略的临时缓存，可随时删除后重跑脚本
- 上游术语表通过 `git submodule update --remote` 同步
- 如果 `--check` 报错（源文件缺失），可能是 submodule 未初始化，运行 `git submodule update --init`
