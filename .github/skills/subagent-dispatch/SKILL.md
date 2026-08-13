---
name: subagent-dispatch
description: 派发 subagent 处理长视频分块任务的模板与纪律。约束 subagent 不过度思考、不逐句确认、只报结构化结果，并在 prompt 中显式注入先验知识（知识卡）。长视频分块合并/翻译、批量校验等需要拆给 subagent 的任务使用。
---

# subagent 派发模板

## 背景：subagent 是无状态的

每次派发的 subagent 都是**全新上下文**，看不到主会话已加载的术语/陷阱词/ASR 修正。因此**先验知识必须显式写进 subagent 的 prompt**，不能指望"主流程加载过一次就延续"。

## subagent 决策（阶段级报告）

> 原则：**粗粒度、少打扰**——在固定阶段入口报一次，不逐步骤打断；路由由 Agent 自主规划（考量沿用 [PIPELINE_ISOLATION.md §3](../../docs/PIPELINE_ISOLATION.md)，非硬性规定）。

**倾向 subagent（隔离）**：长分块 / 批量任务（术语扫描、分块合并/翻译）；输入可独立（子集产物）、输出可固化（落盘为下一步输入）、规则可外置（Skill/模板）；上下文余量紧张（长视频、步骤重）。

**倾向主会话**：需用户交互（术语确认 §1.3、审核循环 阶段二½）——能力约束；需全貌的跨切面决策（如 r03 分句对应、回填判断）；极轻量步骤（隔离收益 < 调度成本）。

**报告格式**（各工作流固定阶段入口执行：translate/reflow 阶段二、preprocess §1.1）：
`本阶段 subagent 策略：用/不用 — N 个 — 原因（长分块 / 依赖全貌 / 需交互 / 极轻量…）`

## 派发前主 Agent 准备

1. 生成/读取该视频的**知识卡**（`02_terms.md`：已确认术语 + 陷阱词命中项 + ASR 修正映射）
2. 用 `scripts/text_chunk.py` 分块（见 [redstone-conventions#长视频分块](../redstone-conventions/SKILL.md#长视频分块全流程通用机制)；SRT 与非 SRT 统一，超阈值判定先跑 `context_estimate.py`）
3. 为每块组装 prompt（模板见下），一次派发一批

## 每块 prompt 模板

```
任务：对以下第 <k>/<N> 块字幕做 <合并|翻译>。

## 先验知识（必须遵守）
<知识卡：全量术语表 + 按本块命中词过滤，至少含已确认术语、scan 命中项（按本块 cue 过滤）、陷阱词命中项、ASR 修正映射>
<各工作流可要求额外注入本任务规则——由主 Agent 按当前工作流组装，通用模板不预置>

## 本块数据（OWNED=负责产出；CONTEXT=只读衔接，见 segment-subtitles）
<chunk_k.txt 内容>

## 纪律
- 直接执行，不要向用户确认任何步骤；不要复述计划或询问"是否继续"
- 有歧义时按默认规则处理并在结果里标注，不阻塞
- 只输出结构化结果（见下），不要描述推理过程

## 输出（写文件，勿返回全文）
- 将结果写入 `_work/<视频名>/<任务目录>/chunk_<k>.txt`（任务目录 = 下方「各任务输出格式」表，主 Agent 按任务指定）
- 格式（utf-8，覆盖写本块文件，勿追加、勿碰其它文件）——按本块**类型三选一**（关键行如下，细节权威见各工作流/产物契约）：
  - **srt 类型（translate merge/翻译）**：每行 `段号|cue范围|<文本>`；`CARRY: c<idx>` 结转标记独立成行（权威 [PRODUCT_FORMATS#s03_plan.md](../../docs/PRODUCT_FORMATS.md)）
  - **text 类型（术语扫描/去翻译腔/r03 分句）**：单元间空行分隔；每单元首行 `<组>-<片>\t<产出文本>`（保留输入 OWNED 的组-片前缀；内容可多行；单元数 = OWNED 单元数）（权威 [PRODUCT_FORMATS#通用文本分块](../../docs/PRODUCT_FORMATS.md)）
  - **reflow 整段文字（r01/r02 块）**：把 OWNED cue 文本按顺序拼成**一段连续文字**输出（补标点后英文 / 整段中文译文）；块内**不按 cue 分行、不按句分行、不带 `c<idx>\t时间码\t` 前缀、不编号**；一个空隙组-片 = 一段（CONTEXT 只读不产出）——逐句/cue 分行会孤立 ASR 残片导致误译，校验脚本按整段解析（权威 [PRODUCT_FORMATS#r01_results / r02_results](../../docs/PRODUCT_FORMATS.md)）
- 写完后报告 `已写入 <文件名>（N 行）`，不要粘贴结果全文
```

## 各任务输出格式（导航表）

> 各任务输入/输出/格式权威见 [reflow-redstone](../reflow-redstone/SKILL.md)、[translate-redstone](../translate-redstone/SKILL.md)、[term-scan](../term-scan/SKILL.md) 各步骤 + [PRODUCT_FORMATS#通用文本分块](../../docs/PRODUCT_FORMATS.md)

| 任务 | 输入 | 输出（`_work/<视频名>/`） | 格式权威 |
|------|------|-------------------------|----------|
| 合并（translate） | OWNED cue + CONTEXT | `_merge_results/chunk_<k>.txt` | [translate-redstone#阶段二](../translate-redstone/SKILL.md) + [PRODUCT_FORMATS#s03_plan.md](../../docs/PRODUCT_FORMATS.md) |
| 翻译（translate） | OWNED 段 + 知识卡 | `_trans_results/chunk_<k>.txt` | [translate-redstone#阶段二](../translate-redstone/SKILL.md) + [PRODUCT_FORMATS#s03_plan.md](../../docs/PRODUCT_FORMATS.md) |
| 术语扫描（preprocess） | OWNED cue + scan 命中项（按块过滤）+ 知识卡 | `_term_results/chunk_<k>.txt` | [term-scan#术语识别](../term-scan/SKILL.md#术语识别subagent) |
| 去翻译腔（translate） | 04 全稿/分块 + humanizer 规则 | `_humanize_results/chunk_<k>.txt` | [translate-redstone#阶段二+ 去翻译腔](../translate-redstone/SKILL.md#阶段二去翻译腔可选独立上下文) |
| 补标点（reflow 步骤 1） | `reflow/chunks/chunk_<k>.txt`（OWNED cue 区间 + 空隙断句标记） | `reflow/r01_results/chunk_<k>.txt` | [PRODUCT_FORMATS#r01_results](../../docs/PRODUCT_FORMATS.md) + [reflow-redstone#步骤 1b](../reflow-redstone/SKILL.md) |
| 整段翻译（reflow 步骤 2） | `r01_results/` 对应块 + 前后块 CONTEXT + 知识卡 | `reflow/r02_results/chunk_<k>.txt` | [PRODUCT_FORMATS#r02_results](../../docs/PRODUCT_FORMATS.md) + [reflow-redstone#步骤 2](../reflow-redstone/SKILL.md)（humanizer-zh 规则注入见此处） |
| 分句对应（reflow 步骤 4） | `r01_results/` + `r02_results/` 对应块对照 | `reflow/r03_results/chunk_<k>.txt` | [reflow-redstone#步骤 4](../reflow-redstone/SKILL.md)（r03 整句分组格式，`parse_r03` 解析） |

## subagent 纪律（生成 prompt 时必须包含）

1. **不过度思考**：不要输出大量分析、备选方案、风险清单；只做被要求的事
2. **不逐句确认**：不要每步问"这样可以吗""需要我继续吗"；有歧义默认处理 + 标注，交由主 Agent 汇总时统一确认
3. **只报结果**：结果写入指定分块文件后，回传 `已写入 <文件名>（N 行）` + 遗留标记（如 `CARRY`/`[待审核]`）；**勿在回复中粘贴结果全文**，不描述推理过程
4. **按规则兜底**：术语按知识卡；知识卡没有的按 `[待审核: 原词]` 标记，不阻塞任务
5. **不翻阅其它视频历史文件**：只用 prompt 提供的数据与知识卡，不自行读取 `_work/`、`_output/` 下其它视频的文件作参考（见 `translate-redstone`「目录约定」）
6. **text 类型保留组-片前缀**：结果按 OWNED 单元逐条产出（单元间空行），每单元首行以输入 OWNED 的 `<组>-<片>` 前缀开头（如 `块0-片2\t...`），供 `text_merge.py` 归位拼接；单元数 = 该块 OWNED 单元数
7. **不运行全局校验脚本**：全局校验（`srt_reflow_check_breaks` / `srt_reflow_check_words` / `check-r03` 块级模式，一次验全部块）是**主会话在所有块产出后的统一动作**；subagent 不调用全局校验、不做全量/他块校对，自查只限于本块格式完整（整段完整、行数正确、字段齐全）

## 合并（text_merge.py 全自动 + 异常清单，替代主 Agent 手工读头尾）

> 分块与合并的格式契约见 [PRODUCT_FORMATS#通用文本分块](../../docs/PRODUCT_FORMATS.md)。主 Agent **不再手工读每块头尾**——合并交脚本，只读异常报告。

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
4. 落盘最终产物（`03_segments.md` / `04_translation_draft.srt` / `r01_merged_en.txt` 等，见各工作流）
5. **全量机械校验交脚本**（覆盖完整/不重叠/边界⊆原集/格式）-> [segment-subtitles#输出与校验](../segment-subtitles/SKILL.md#输出与校验)；校验报错即回到对应块修复后重跑 `text_merge.py`
6. 阶段二½ 交用户审核
