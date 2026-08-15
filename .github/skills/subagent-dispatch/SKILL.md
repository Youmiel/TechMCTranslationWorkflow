---
name: subagent-dispatch
description: subagent 派发规范——派发配方（任务文件+纪律母版+产物格式约定+知识卡+块数据的固定组装顺序）、纪律母版（全局纪律单一权威）、任务导航表（任务→任务文件）。约束 subagent 不过度思考、一次性产出（不展示中间态/不重读重写）、只报结构化结果、禁止参考其它工作文件。任何需要拆给 subagent 的任务派发时参考。
---

# subagent 派发模板

## 背景：subagent 是无状态的

每次派发的 subagent 都是**全新上下文**，看不到主会话已加载的术语/陷阱词/ASR 修正。因此**先验知识必须显式写进 subagent 的 prompt**，不能指望"主流程加载过一次就延续"。

## 派发边界（哪些派 subagent / 哪些主会话）

> 原则：**粗粒度、少打扰**——派发是执行机制，是否派由任务性质决定，**不需逐步骤报告**（考量沿用 [PIPELINE_ISOLATION.md §3](../../../docs/PIPELINE_ISOLATION.md)）。

**一律派 subagent**（reflow 阶段二补标点/翻译/分句、preprocess §1.1 术语识别）：统一路径，块数由骨架决定，**无需报告"用/不用"**——直接按派发配方派发。

**不派 subagent（主会话）**：需用户交互（术语确认 §1.3、审核循环 阶段二½）——能力约束；需全貌的跨切面决策（如 r03 分句对应、回填判断）。

**translate（未重构）**：阶段二仍是条件派发（长分块才 subagent），保留阶段入口报告 `本阶段 subagent 策略：用/不用 — N 个 — 原因`；重构后与 reflow 对齐。

## 派发前主 Agent 准备

1. 生成/读取该视频的**知识卡**（`02_terms.md`：已确认术语 + 陷阱词命中项 + ASR 修正映射）
2. 用 `scripts/text_chunk.py` 分块（见 [redstone-conventions#长视频分块](../redstone-conventions/SKILL.md#长视频分块全流程通用机制)；SRT 与非 SRT 统一，超阈值判定先跑 `context_estimate.py`）
3. 按「派发配方」组装每块 prompt（任务文件 + 纪律母版 + 产物格式约定 + 知识卡 + 块数据），一次派发一批
4. **组装好的 prompt 先落盘存档再派发**（见下「提示词存档」）——先存后发，供复盘回查

## 派发配方

> 每个可派发任务 = 一份**任务 prompt 文件**（放所属 skill 目录，如 `term-scan/task-term-recognition`、`reflow-redstone/task-punctuate`），内容是面向 subagent 的**现成任务指令**（目标 + 行为规则 + 输出契约），主 agent **即读即用、无需理解重组**。任务文件自带「## 先验知识」「## 本块数据」占位，派发时填充；任务**特有规则直接内联**在任务文件（不建独立规则文件）；**通用纪律**由下方「纪律母版」统一追加（单一权威，含工作区/输出门禁等）；**产物格式约定**（格式查找路径）由主 agent 组装时注入（见下）。

```
subagent prompt = 任务文件内容（含任务特有规则）
                + 纪律母版（下方，整体追加；通用纪律单一权威）
                + 产物格式约定（查找路径：PRODUCT_FORMATS 对应节，subagent 唯一允许的外部读取）
                + 知识卡（术语/陷阱词/ASR 修正映射，运行时）
                + 块数据（## BEFORE / ## OWNED / ## AFTER，取自 chunk_<k>.txt，内联进提示词）
                + 写盘/报告约定（输出路径 + 「已写入 <文件名>（N 行）」）
```

> **产物格式约定**：输出文件格式/折行/标记的权威在 `docs/PRODUCT_FORMATS.md` 对应节（任务文件已内联关键规则，细节以该节为准）；组装时把**查找路径**写进提示词（如 `PRODUCT_FORMATS#r01_results/chunk_<k>.txt（补标点块）`），subagent 按需查阅——这是唯一允许的外部读取，其余数据一律内联（见纪律母版 #8）。无外部格式权威的任务（如 `task-summary`）此项省略。

## 提示词存档（派发时必做，供复盘查阅）

> 派发不只是"调用"——组装好的**完整 prompt 落盘存档**：复盘 r02 翻译腔 / subagent 未按规则执行 / 审计 / 复现时按块回查，不靠会话回顾（会话会丢、不可重放）。

- **位置**：`_work/<视频名>/prompts/`（与 `reflow/` 等产物同级）；命名 `<任务>-chunk_<k>.txt`（如 `task-translate-chunk_002.txt`、`task-split-chunk_003.txt`）；不跨任务合并、不覆盖
- **内容** = 实际发给 subagent 的**完整原文**（任务文件内容 + 纪律母版 + 产物格式约定 + 知识卡 + 块数据 + 写盘/报告约定）
- **时机**：派发该 subagent **前**落盘（先存后发）；块级任务每块一份
- **保留**：属中间产物，**禁止自动删除**（AGENTS.md #6）
- **用途**：r02 质量回查（当时注入的先验知识/对照示范）、subagent 行为归因（看它实际收到什么）、同视频不同批次/版本对比

## 任务导航表（任务 → 任务文件）

> 每个可派发任务的**任务文件**（现成 prompt）与产物输出。任务文件在所属 skill 目录内；格式契约权威见各任务文件 + [PRODUCT_FORMATS](../../../docs/PRODUCT_FORMATS.md)。任务文件逐步建立，未建时按各工作流步骤的规则组装。

| 任务 | 任务文件 | 输出（`_work/<视频名>/`） |
|------|----------|--------------------------|
| 术语识别（preprocess §1.1） | `term-scan/task-term-recognition` | `_term_results/chunk_<k>.txt` |
| 补标点（reflow 步骤 1） | `reflow-redstone/task-punctuate` | `reflow/r01_results/chunk_<k>.txt` |
| 整段翻译（reflow 步骤 2） | `reflow-redstone/task-translate` | `reflow/r02_results/chunk_<k>.txt` |
| 分句对应（reflow 步骤 4） | `reflow-redstone/task-split` | `reflow/r03_results/chunk_<k>.txt` |
| 前文摘要（reflow 步骤 2 可选） | `reflow-redstone/task-summary` | `reflow/summary.md` |
| 合并（translate 阶段二） | `translate-redstone/task-merge` | `_merge_results/chunk_<k>.txt` |
| 翻译（translate 阶段二） | `translate-redstone/task-translate` | `_trans_results/chunk_<k>.txt` |
| 去翻译腔（translate 阶段二+） | `translate-redstone/task-humanize` | `_humanize_results/chunk_<k>.txt` |

## 纪律母版（派发时必须整体追加）

> 全局纪律**单一权威**在此；任务文件不重复内联。派发时随配方整体追加给 subagent。

1. **减少思考（执行型任务，直接产出）**：本任务是**执行型**——目标、规则、输出契约已在提示词中给定，**不做方案论证、不创造性发挥**：
   - **不展示思考过程**：回复与输出文件**不含**推理步骤、中间草稿、备选方案、风险清单（这些不会被执行，只增加噪音）
   - **不质疑设定**：给定规则/先验知识即执行依据，不提出改进建议、不解释"为什么这么做"；拿不准处按 #5 兜底标记，不展开讨论
2. **一次性产出（不展示中间态）**：输出文件**直接写最终结果**（覆盖写、一次成型），不先给草稿/中间版本再修订；所有要求（术语统一、去翻译腔、断句规则等）在写盘前**内部一次完成**——自查、对照、取舍都在内部，无需向主 Agent 汇报中间状态或分步确认
3. **不逐句确认**：不要每步问"这样可以吗""需要我继续吗"；有歧义默认处理 + 标注，交由主 Agent 汇总时统一确认
4. **只报结果**：结果写入指定分块文件后，回传 `已写入 <文件名>（N 行）` + 遗留标记（如 `CARRY`/`[待审核]`）；**勿在回复中粘贴结果全文**，不描述推理过程
5. **按规则兜底**：术语按知识卡；知识卡没有的按 `[待审核: 原词]` 标记，不阻塞任务
6. **只处理本块新内容**：**严禁重读或重写已产出/已处理过的内容**（写盘后不回头修订、不处理其它块/其它阶段产物）；`## BEFORE`/`## AFTER` 只读衔接，不产出、不翻译、不改写；只产出 `## OWNED` 对应的结果
7. **纯结果输出**：输出文件只含任务要求的结果文本，**不含任何检查备注、修订标记、解释性文字**（如"已按规则处理""此处译文待定"）；结构化遗留标记（`[待审核: …]`/`CARRY` 等）是契约允许的例外
8. **工作区纪律**：数据一律用提示词内联内容（块数据已在提示词中）+ 提示词明确给出的**产物格式约定**（`PRODUCT_FORMATS` 对应节，唯一允许的外部读取）；**禁止参考其它工作文件**——不自行读取 `_work/`、`_output/` 下其它任何文件（其它视频、本视频其它块/其它产物）作参考（需要的外部先验由主 agent 注入 `## 先验知识`）；**只写任务指定的 `_work/<当前视频名>/` 中间产物路径**（不写 `scripts/`、`_output/`——正式稿只收用户确认后）；**不删除任何文件/目录**
9. **text 类型保留组-片前缀**：结果按 OWNED 单元逐条产出（单元间空行），每单元首行以输入 OWNED 的 `<组>-<片>` 前缀开头（如 `块0-片2\t...`），供 `text_merge.py` 归位拼接；单元数 = 该块 OWNED 单元数
10. **不运行全局校验脚本**：全局校验（`srt_reflow_check_breaks` / `srt_reflow_check_words` / `check-r03` 块级模式，一次验全部块）是**主会话在所有块产出后的统一动作**；subagent 不调用全局校验、不做全量/他块校对，自查只限于本块格式完整（整段完整、行数正确、字段齐全）

## 合并（text_merge.py 全自动 + 异常清单，替代主 Agent 手工读头尾）

> 分块与合并的格式契约见 [PRODUCT_FORMATS#通用文本分块](../../../docs/PRODUCT_FORMATS.md)。主 Agent **不再手工读每块头尾**——合并交脚本，只读异常报告。

1. 按 subagent 报告的 `已写入` 确认各块文件齐全（缺块由 `text_merge.py` 异常清单兜底）
2. **跑合并脚本**：`python scripts/text_merge.py <chunks_dir> <results_dir> --out <合并产物> [--report <报告>] [--window N]`
   - 默认全自动拼接（text 同组无缝/组间空行；srt 全局段号重排）
3. **读合并报告**（`<merged>.report.md`）：
   - `## 结论: 无异常` → 直接进入第 4 步，**零读取**
   - `## 异常清单` → 只读清单 + `## 异常块头尾窗口`（每块 OWNED 头尾各 `--window` 行），按异常类型决策：
     - **行数不符/缺块** → 回对应块补跑 subagent
     - **重复产出**（srt 重叠）→ 保留更完整版本（默认 start 最早，见 [segment-subtitles#跨块未完成句](../segment-subtitles/SKILL.md#跨块未完成句结转规则)）
     - **gap/cue 缺口**（srt）→ 查 SRT 确认 gap 处是否空 cue（[Music] 等），是则并入相邻段、否则标记重译
     - **结转**：`CARRY: c<idx>` 对应产出段，确认未重复未遗漏
     - **片号不连续**（text）→ 查该组是否缺片，补跑
   - 已确认的 ASR 修正（`02_terms.md`）在组装期应用（合并后手动替换或脚本内处理）
4. 落盘最终产物（`s03_plan.md` / `s04_draft.srt` / `r03_plan.md` 等，见各工作流）
5. **全量机械校验交脚本**（覆盖完整/不重叠/边界⊆原集/格式）-> [segment-subtitles#输出与校验](../segment-subtitles/SKILL.md#输出与校验)；校验报错即回到对应块修复后重跑 `text_merge.py`
6. 阶段二½ 交用户审核
