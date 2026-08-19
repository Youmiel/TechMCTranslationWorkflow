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
3. **清理旧产物（重跑/重试前必做，mv 不删）**：目标结果文件若已存在（校验打回重跑、整轮重跑等场景），用 `Move-Item` 移到同目录的 `<结果目录>_bak_<时间戳>/`（如 `reflow/r01_results_bak_20260816_1530/`，时间戳取当前时刻），**只移动、不删除**——subagent 纪律 #8 禁删，主会话亦用 mv 规避删除；示例 `Get-ChildItem reflow/r01_results/chunk_*.txt | Move-Item -Destination "reflow/r01_results_bak_$(Get-Date -Format yyyyMMdd_HHmm)/" -Force`。**清理是写盘前提**：`create_file` 只新建、遇已存在即报错；结果文件多为超长单行（`read_file` 截断、走"读后改"必死循环）——故必须保证 subagent 写盘时目标路径不存在。**备份带时间戳即历史归档**（每轮独立、不覆盖、可审计可恢复），不删除、无需清退
4. **跑渲染脚本生成每块 prompt**：`python scripts/render_subagent_prompt.py <task> --video <视频工作目录> [--chunk <k> | --all] [--prior-file <文件>]`（渲染逻辑与任务映射见「派发配方」）——完整 prompt 落盘 `_work/<视频名>/prompts/<task>-chunk_<k>.txt`，**不经主会话**（完整 prompt 文本不进主会话历史，主会话只发短命令）；**数据文件只验证、不读取**：对引用的数据文件（块数据）用 `list_dir` 列目标目录验证**存在**（返回子项中命中 = 存在；**不用 `file_search`**——`_work/` 被 `.gitignore` 忽略，glob 搜不到；块数据为主会话刚生成，非空必然），**不 `read_file` 读取内容**（块内容不入主会话，省上下文）；块数据引用路径由渲染脚本按任务注入 `## 本块数据`
5. **渲染即存档**：渲染脚本已把完整 prompt 落盘 `prompts/`（先存后发，供复盘回查），无需另行 create_file 落盘；派发时按「派发引用 prompt」只给引用路径（完整 prompt 内容不再进主会话）

## 派发配方

> 每个可派发任务 = 一份**任务 prompt 文件**（放所属 skill 目录，如 `reflow-redstone/task-punctuate`），内容是面向 subagent 的**现成任务指令**（目标 + 行为规则 + 输出契约）。**完整 prompt 由渲染脚本 `scripts/render_subagent_prompt.py` 会话外组装落盘**（`_work/<视频名>/prompts/<task>-chunk_<k>.txt`）：读模板正文（`<k>`/`<视频名>` 占位替换）+ 逐字追加纪律母版（`_discipline.md` 单一权威）+ 注入产物格式约定 + 注入先验知识（术语直读 02_terms.md / humanizer-inject / 空隙断句标记）+ 生成块数据引用——**完整 prompt 文本不进主会话历史**，主 agent 只发渲染命令 + 派发引用。任务**特有规则直接内联**在任务文件（不建独立规则文件）；**通用纪律**由 `_discipline.md` 单一权威；**产物格式约定**（格式查找路径）由渲染脚本注入（见下）。

> **渲染脚本覆盖范围**：当前接入 `task-punctuate` / `task-translate` / `task-split`（reflow 块级任务）；`task-term-recognition` / `task-fix` / `task-summary` 未接入——仍按旧方式：主 agent 读模板 + 手工组装 + 落盘存档（内容不大时也可直接内联派发）。

> **执行型纪律与模型**：reflow 类执行任务**派发 `reflow-worker`（执行型 agent），使用无思考模型**——具体做法（派发入口 / agent 定义 / 模型名 / adapt）按你自己的编辑器执行，见 [EDITOR_COMPAT](../../../docs/EDITOR_COMPAT.md)（模型名读 `configs/subagent_model.yaml` 的 `execution_model`）。纪律母版 #0 与 agent 系统提示词同源，由渲染脚本随 prompt 整体注入（内联兜底 + 任务特定纪律 + 兜底）。

> **组装原则（内联 vs 引用，单一权威）**：**默认全部内联，仅数据文件例外**——任务规则、纪律母版、`## 先验知识`（术语表/陷阱词/ASR 修正/humanizer 注入等）等一切规则与知识内容由渲染脚本**直接内联进 prompt 文件**；**唯一例外 = 块数据**（`## 本块数据` 单独注明数据文件路径，subagent 按引用读取）；subagent 侧只读边界见纪律母版 #8。

```
（以下各项均由渲染脚本 render_subagent_prompt.py 注入产出）
subagent prompt = 任务文件内容（含任务特有规则）
                + 纪律母版（_discipline.md 整体追加；通用纪律单一权威）
                + 产物格式约定（查找路径：PRODUCT_FORMATS 对应节，subagent 唯一允许的外部读取）
                + 知识卡（术语/陷阱词/ASR 修正映射；脚本直读 02_terms.md 等）
                + 块数据（## 本块数据 单独注明数据文件路径——唯一引用例外，其余全部内联，见「组装原则」）
                + 写盘/报告约定（输出路径 + 「已写入 <文件名>」；**不数行数**——行数/非空由脚本统计校验，见「合并」）
```

> **产物格式约定**：输出文件格式/折行/标记的权威在 `docs/PRODUCT_FORMATS.md` 对应节（任务文件已内联关键规则，细节以该节为准）；渲染脚本按任务把**查找路径**注入 prompt（如 `docs/PRODUCT_FORMATS.md` 的 `r01_results/chunk_<k>.txt（补标点块）` 节），subagent 按需查阅——这是唯一允许的外部读取；内联/引用分工见「组装原则」与纪律母版 #8。无外部格式权威的任务（如 `task-summary`）此项省略。
> **`## 先验知识` 内部顺序**（渲染脚本按任务配置注入，**高优先级靠前、紧贴对应任务规则**，不得打乱）：如 task-punctuate 的空隙断句标记先于其他、task-translate 的 humanizer 注入版先于术语表；任务文件底部未注明的按「纪律 → 格式 → 知识 → 数据」序。需主会话判断的额外先验（块边界情况、前文摘要等）用 `--prior-file` 传文件追加到 `## 先验知识`。

## 提示词渲染与存档（render_subagent_prompt.py 会话外落盘）

> 完整 prompt 由渲染脚本**会话外组装落盘**（`_work/<视频名>/prompts/<task>-chunk_<k>.txt`）——**不经主会话**，完整 prompt 文本不进主会话历史；存档既是复盘材料（会话会丢、不可重放），也是派发时 subagent 引用的唯一任务指令。

- **位置**：`_work/<视频名>/prompts/`（与 `reflow/` 等产物同级）；命名 `<任务>-chunk_<k>.txt`（如 `task-translate-chunk_002.txt`、`task-split-chunk_003.txt`）；不跨任务合并、不覆盖
- **内容** = 实际发给 subagent 的**完整原文**（任务文件内容 + 纪律母版 + 产物格式约定 + 先验知识 + 块数据引用路径 + 写盘/报告约定；复盘按路径读对应块文件）
- **时机**：派发该 subagent **前**渲染（先存后发）；块级任务每块一份
- **保留**：属中间产物，**禁止自动删除**（AGENTS.md #6）
- **用途**：r02 质量回查（当时注入的先验知识/对照示范）、subagent 行为归因（看它实际收到什么）、同视频不同批次/版本对比

## 派发引用 prompt

> 派发 `runSubagent` 时**不内联完整 prompt**——只给 ~5 行引用，subagent 先 read 任务指令文件再执行。核心收益：完整 prompt 只在 subagent 的一次性上下文出现，**不进主会话历史**（历史只增不减、每轮都付）。

- **派发 prompt 模板**（按实际情况填充）：

```
你的完整任务指令在存档文件：`_work/<视频名>/prompts/<task>-chunk_<k>.txt`

**先用 read 工具读取该文件**，严格按其中「任务规则」「纪律母版」「先验知识」「本块数据」执行。

关键执行要求（与本块特殊说明一致）：
- <每块特殊说明，从 --prior-file 关键点提一句（可选）>
- **必须执行写盘动作**：用新建文件动作创建 <输出路径>（目录已存在），内容按任务规则
- 只读不写 = 未完成任务；写盘后报告 `已写入 <文件名>`（不数行数，不粘贴任何内容）
```

- **约束**：
  - 引用路径必须精确（`_work/<视频名>/prompts/<task>-chunk_<k>.txt`），路径错则 subagent 读不到
  - 首条必须是「先 read 该文件」强指令（no-think agent 可能不读就做）
  - 假完成兜底（「收信号即验」）不因引用式改变，仍生效

## 收信号即验（`已写入` 真实性门禁，拦截假完成）

> subagent 可能**只读不写**——读了 `## 本块数据` 输入、却未执行任何写盘动作就直接返回 `已写入`（模型行为不可靠，完成信号不可信）。主会话**每收到一个 `已写入` 信号立即校验真实性**，不等到全部完成（内容正确性校验仍按「统一验证时间点」等所有块 subagent 全部完成后一次跑）。

- **校验（用工具，不跑终端命令，不读文件内容）**：目标文件**存在**——用 `list_dir` 列目标目录（如 `_work/<视频名>/reflow/r01_results`），在返回子项中确认目标文件在列：**命中 = 存在 = 通过**；未命中 = 假完成（**不用 `file_search`**——`_work/` 被 `.gitignore` 忽略，glob 搜不到）。**禁用 `read_file`**（结果文件是超长单行，读必截断）；**非空不在此验**——假完成 = "只读不写" = 文件不存在，即时拦存在即可；空文件由合并阶段脚本统计兜底（`text_merge` 异常清单 / `(Get-Content -LiteralPath <file>).Count`）
- **通过** → 记该块已产出，继续派发下一块
- **不通过（缺文件 / 空文件 = 假完成）** → 该块**立即打回重派**：先按「派发前主 Agent 准备」#3 用 mv 清理残留（仅此低频场景用终端命令），再重派同一块，**不等待其它块**
- 同一块连续多次假完成 → 升级主 Agent/用户排查（模型或写盘工具问题），不再空转重派

## 定点修正（surgical-fix）：校验打回先小规模修，不整块重派

> 动机：整块打回重派 = subagent 全文重读重写（token 代价大）；校验脚本已精确给出错位置（`check_breaks` → 空隙点 cue+块；`check_words` → 块+第 i 词+01/r01 具体词；`check-r03` → 块+`S<n>`+子单元 `S<n><a>`）。大部分错误是单点/单节（措辞小误、缺断句标点、行宽超限、断点调整）——**可小规模决策与改动**，无需重派全文。

### 三档决策（按错误范围与目标文件结构）

| 档位 | 执行者 | 适用 | 操作 |
|------|--------|------|------|
| **A 档 · 单节定点改** | 主会话（零 subagent） | r03 结构化单节（`## S<n>`）错误：行宽 >26 切分、拆句互斥、括号/引号配对、断点调整 | `grep_search` 定位 `## S<n>` → `read_file` 读该节小窗口 → `replace_string_in_file` 精确替换该节；**其余节不动** |
| **B 档 · 修复 subagent** | `reflow-worker` subagent（`task-fix` 任务模板） | r01/r02 整段文件（措辞改回 01、空隙断句）；r03 需整句语义重排 | 跑完校验后**一次派发** `task-fix`，`## 修复范围` = **全部错误清单**（每处含文件+坐标+摘录+目标）；subagent **逐处用定点编辑工具只改被指出的位置**（不读全文、不输出全文）；无法定点匹配才单处回退读+覆盖写 |
| **C 档 · 整块重派** | `reflow-worker` subagent（全文重派） | 错误范围大 / 无法定位 / 连续定点修仍失败 / 整块语义问题（如整块翻译腔） | mv 清理 + 全文重派（见「派发前主 Agent 准备」#3） |


### 决策原则

1. **校验输出已给修复所需信息 → A 档**：主会话上下文含 01 原文 / 前后 cue / `S<n>` 坐标即够（校验已打印），不派 subagent、不读全文件
2. **需读目标文件上下文 → B 档（批处理，摊薄固定提示词）**：r01/r02 整段、r03 整句重排——跑完校验、**收集全部错误清单后一次派发** `task-fix`（固定提示词只付一次；逐处派发会重复付固定成本，N 处错误 = N 次），subagent **逐处用定点编辑工具只改指出处**（不读全文、不输出全文；单处无法匹配才回退读+覆盖写——不整块重写语义，token 远低于全文重派）
3. **超出定点能力 → C 档**：错误多、散，或属语义级（整句翻译腔、锚定需改写原文）——直接重派，不空转定点修
4. **纪律分层不可破**：r03 只许切不许译（忠实铁律；改译文词 → 回 r02，非定点修范围）；r01 仅加标点 / 按 01 改回措辞，不自行改写
5. **修正后复验闭环（方案 3 = 单轮批量 + 残留增量）**：A/B 档修正后重跑触发它的校验（`check_breaks`/`check_words`/`check-r03` 均脚本全块跑，成本可忽略）——**通过才继续**；仍有残留错误（FALLBACK 或新错）→ **第二轮 B 档只派增量残留清单**（小，逐轮收敛）；连续多轮仍失败 → 升级 C 档，不空转定点修
6. **方案定型**：定点修复采用 **B 档批量（方案 3）**；**逐处派发（方案 2）弃用**——主会话每轮要完整输出 N 份 prompt（含 `dispatch`）为确定性高单价劣势；**不实现 subagent 内部自主循环（方案 4）**——实现繁琐且实际修复大概率一轮过（权衡理由见 `Project_Plan/2026-08-17_定点修复方案权衡.md`）；未来若实测多轮频繁，优先上「规则引用化」轻量增强（主会话每轮只输出增量清单）

## 任务导航表（任务 → 任务文件）

> 每个可派发任务的**任务文件**（现成 prompt）与产物输出。任务文件在所属 skill 目录内；格式契约权威见各任务文件 + [PRODUCT_FORMATS](../../../docs/PRODUCT_FORMATS.md)。任务文件逐步建立，未建时按各工作流步骤的规则组装。

| 任务 | 任务文件 | 输出（`_work/<视频名>/`） |
|------|----------|--------------------------|
| 术语识别（preprocess §1.1） | `term-scan/task-term-recognition` | `_term_results/chunk_<k>.txt` |
| 补标点（reflow 步骤 1） | `reflow-redstone/task-punctuate` | `reflow/r01_results/chunk_<k>.txt` |
| 整段翻译（reflow 步骤 2） | `reflow-redstone/task-translate` | `reflow/r02_results/chunk_<k>.txt` |
| 分句对应（reflow 步骤 4） | `reflow-redstone/task-split` | `reflow/r03_results/chunk_<k>.txt` |
| 定点修复（校验打回 B 档） | `reflow-redstone/task-fix` | 覆盖写 `## 目标文件` 同一路径 |
| 前文摘要（reflow 步骤 2 可选） | `reflow-redstone/task-summary` | `reflow/summary.md` |
| 合并（translate 阶段二） | `translate-redstone/task-merge`（**未建**——translate 未重构，按 SKILL 步骤组装） | `_merge_results/chunk_<k>.txt` |
| 翻译（translate 阶段二） | `translate-redstone/task-translate`（**未建**——同上） | `_trans_results/chunk_<k>.txt` |
| 去翻译腔（translate 阶段二+） | `translate-redstone/task-humanize`（**未建**——同上） | `_humanize_results/chunk_<k>.txt` |

## 纪律母版（派发时必须整体追加）

> 全局纪律**单一权威**在 [_discipline.md](_discipline.md)（正文 = 5 类纪律：执行型定位 / 一次性产出 / 报告与结果格式 / 内容边界 / 工作区与工具纪律 + 结果格式契约说明）——任务文件不重复内联；派发时由渲染脚本 `scripts/render_subagent_prompt.py` 逐字追加（`{TASK_ROLE}` 按任务替换）；未走渲染脚本的派发由主会话按该文件整体追加。

## 合并（text_merge.py 全自动 + 异常清单，替代主 Agent 手工读头尾）

> 分块与合并的格式契约见 [PRODUCT_FORMATS#通用文本分块](../../../docs/PRODUCT_FORMATS.md)。主 Agent **不再手工读每块头尾**——合并交脚本，只读异常报告。

1. 按 subagent 报告的 `已写入` 确认各块文件齐全；**行数/非空由脚本统计**——走 merge 的产物由 `text_merge.py` 异常清单（缺块/行数不符）兜底，不走 merge 的（reflow r01/r02/r03、term）由主会话确定性统计（`(Get-Content -LiteralPath <file>).Count`）校验非空
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
