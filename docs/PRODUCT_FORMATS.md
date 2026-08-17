# 产物格式与标记约定（PRODUCT_FORMATS）

> 全部工作流产物的格式 / 结构 / 分隔符 / 标记约定统一在此——共享 `01`/`02`（preprocess）、translate `s03`/`s04`、reflow `r00`–`r04` + `r03_anchored.jsonl`。
> 各 SKILL 步骤与脚本 docstring 只引用本文件、不重复展开；**处理某产物前先查本文件对应节**，勿现查代码猜格式。
> 脚本解析器（`plan.py parse_r03`、`srt_check_segments.py` 等）是格式的**实现标准**，本文件是**约定标准**——两者必须一致，变更需同步（见「变更同步清单」）。

## 通用约定

- **编码**：全部 UTF-8（无 BOM）
- **块间分隔 = 空行**（`r01_results/`/`r02_results/` 各块文件的段落边界唯一规范）；**手写产物禁止写任何标记文本**（`[break]`/英文注释等都不写）；跨块句补全标记仅限 `【承接句】`/`【延伸句】`（见 `r01_results` 节）
- **空隙标记 `【强制断句】`**：**非产物文本**——由 `srt_reflow_breaks.py` 断句点清单派生、经 Agent 复核后作为先验知识注入补标点 subagent（见 task-punctuate），Agent 不手写
- **结构标记**（`## S<n>`/`- EN:`/`- ZH:`/`- 关系:`/`### S<n><a>`、`段号|cX-cY|`、术语表表头）是脚本解析标准，不得改动格式

## 变更同步清单

改动任何产物的**格式 / 分隔符 / 字段**时必须同步：

1. **本文件**（PRODUCT_FORMATS.md）
2. **生成/解析脚本**：`srt_reflow_gap_scan.py`、`srt_reflow_breaks.py`、`srt_reflow_check_breaks.py`、`srt_reflow_check_words.py`、`srt_reflow_core/{io,plan,allocate,alerts,reflow,attach}.py`、`srt_check_segments.py`、`srt_check_width.py`
3. **引用 SKILL 步骤**：`reflow-redstone`（步骤 1/2/4/5/6）、`translate-redstone`（阶段二）、`redstone-preprocess`（产物契约）、`segment-subtitles`（断句/行宽）
4. **脚本 docstring**（格式描述与实现一致）

> 本文件是格式约定的事实标准；脚本若与本文冲突，以本文为准并修脚本（或先改本文再改脚本，保持同步）。

---

## 产物总表

| 产物 | 工作流 | 生成者 | 消费/校验脚本 |
|------|--------|--------|----------------|
| `01_subtitle_asr_fixed.srt` | 共享（阶段〇/一） | Agent（ASR 修正） | `srt_check_segments.py --cue-exact`；reflow gap/breaks/words |
| `02_terms.md` | 共享（阶段〇/一） | Agent（用户确认） | 翻译固定译名、ASR 修正组装 |
| `s03_plan.md` | translate | Agent（断句定稿） | `srt_check_segments.py`（md 模式） |
| `s04_draft.srt` | translate | Agent（逐段翻译） | `srt_check_segments.py`、`srt_check_width.py` |
| `r00_gaps.md` | reflow | `srt_reflow_gap_scan.py` | Agent 参考 |
| `r01_breaks.md` | reflow | `srt_reflow_breaks.py` + Agent 回填 | `srt_reflow_check_breaks.py` |
| `r01_normalized/chunk_<k>.txt` | reflow（块数 = 空隙组×片数） | 脚本 `srt_reflow_normalize.py`（一次性全目录） | Agent（补标点 subagent 输入） |
| `r01_results/chunk_<k>.txt` | reflow（块数 = 空隙组×片数） | Agent（补标点 subagent） | `srt_reflow_check_breaks.py`、`srt_reflow_check_words.py`（块级模式） |
| `r02_results/chunk_<k>.txt` | reflow（块数 = 空隙组×片数） | Agent（整段翻译 subagent） | `check-r03`（ZH 忠实基准） |
| `r02_normalized/chunk_<k>.txt` | reflow（块数 = 空隙组×片数） | 脚本 `srt_reflow_normalize.py`（复制+折行） | Agent（分句 subagent 输入） |
| `r03_plan.md` | reflow | 脚本 `join-r03`（按需，审核/审计用；回填直读 `r03_results/`） | `plan.py parse_r03`、`check-r03` |
| `r04_draft.srt` | reflow | `srt_reflow.py reflow` | `srt_check_segments.py`、`check-duration` |
| `r04_bilingual.srt` | reflow | `srt_reflow.py attach-en` | `srt_check_width.py --order en-zh` |
| `r04_alerts.md` | reflow | `srt_reflow.py reflow` | Agent 参考 |
| `r03_anchored.jsonl` | reflow | `srt_reflow.py reflow` | 人工/机器审查 |
| `prompts/<任务>-chunk_<k>.txt` | 共享（派发存档） | Agent（派发前落盘完整 subagent prompt） | 复盘查阅（无自动校验，规则见 subagent-dispatch「提示词存档」） |

---

## 通用文本分块（text_chunk / text_merge）

> 长视频分块的**统一格式契约**——SRT 与非 SRT 产物共用。工具：`scripts/text_chunk.py`（分块）+ `scripts/text_merge.py`（合并）。用法与调度见 [redstone-conventions#长视频分块](../.github/skills/redstone-conventions/SKILL.md#长视频分块全流程通用机制) 与 [subagent-dispatch](../.github/skills/subagent-dispatch/SKILL.md)。
> 旧 `scripts/srt_chunk.py` 保留兼容（历史产物/旧流程），**新任务一律用 `text_chunk.py`**。
> **产物一律块级（产物单轨）**：分块与不分块同一处理逻辑、同一产物契约——块级 `chunk_<k>.txt` + 需合并的产物（如 reflow 的 `r04_draft.srt`）按块序/骨架拼接；每块 OWNED+CONTEXT、独立处理、中间不拼全文。reflow 回填**直读 `r03_results/` 目录**（`parse_r03_dir` 按块序解析 + S 号全局重编号），无需拼 r03_plan.md。逻辑一致 ⇒ 小输入即可验证分块流程逻辑（reflow 的**空隙点强制切块**与 `--owned` 语义见「块级流水线」节）。

### 块文件格式（`text_chunk.py` 输出，`chunk_<k>.txt`）

- **块头（首行，机器可解析元数据）**：`# CHUNK <k>/<N>  SRC: <文件名>  TYPE: <srt|text>  UNIT: <语义单位>  OWN: <组标识列表>  CTX: BEFORE <B> AFTER <A>`
- **标记语言统一（全英文大写简单词）**：`#` = 说明/元数据行（块头 `# CHUNK`、分区内 `# SOURCE`/`--- PREV/NEXT ---` 等标注）；`##` = 分区标记（`## BEFORE`/`## OWNED`/`## AFTER`，脚本硬依赖）；不用中文/`###` 混标
- **分区顺序（LLM 语义优先）**：`## BEFORE`（本块之前，只读，非空才输出）→ `## OWNED`（本块负责产出）→ `## AFTER`（本块之后，只读，非空才输出）——前文在前、内容中间、后文在后，subagent 按语义顺序阅读；首块无 BEFORE、末块无 AFTER
- **`## OWNED`**：subagent 必须产出的内容；srt 每行一条 `c<idx>\t<时间码>\t<文本>`；text **单元间空行分隔**、单元首行 `<组>-<片>\t<内容>`（内容可多行，如 r03 markdown）
- **`## BEFORE` / `## AFTER`**：前后只读上下文，格式同 OWNED；解析脚本按 `## ` 分区通用判断切 OWNED（任意分区标题切换），不受顺序/缺区影响；旧块头格式（`# chunk ... 源:`）不兼容新解析，历史产物不再重新合并
- **`manifest.md`**：块清单（组/片 → 块号映射），`text_merge.py` 与人工核对用
- **类型与语义单位**：
  - `srt`：单位=cue（`01_subtitle_asr_fixed.srt`、双语段 SRT），`--owned` 默认 100、`--ctx` 默认 6；**`--gaps`** 时块标识 =「空隙组-片」（如 `块0`、`块1-片10`），空隙点强制切块（reflow，见「块级流水线」）
  - `text`：单位=`段`（空行分隔，r01/r02 默认）/ `句`（按标点，同组多句片号连续）/ `整句组`（r03 的 `## S<n>`），`--owned` 默认 1、`--ctx` 默认 1
- **超长单位细分**：text 单原子单位超过 `--max-chars`（默认 6000 字符）时拆为「组-片」（如 `块0-片2`）；**同组多片合并时无缝拼接**（中文空连接、英文空格），解决 r01 块 0 拆 0a..0f 场景
- **约束**：块边界永远在单位边界（不切开 cue / 语义段）；text 单元可多行；确定性输出

### 块级流水线（从 01 分块，reflow r01→r02→r03 中间不拼全文）

> 目标：让 reflow 的 r01→r02→r03 各子块**独立处理、按块传递**，中间**不拼全文**，校验**逐块化**——只有最终 r04 是必须合并的；r03 回填**直读 `r03_results/` 目录**（零拼接、LLM 不读全量），`r03_plan.md` 仅审核/审计时 `join-r03` 按需生成。减少"拼全文→整读→再分块"的反复。

- **一次分块（从 01）**：`python scripts/text_chunk.py <01.srt> --type srt --gaps --owned <每块cue数> --ctx <衔接cue数> --out reflow/chunks/`——块 = 「空隙组-片」（**空隙点强制切块=语义硬边界**、组内按 `--owned` 分片=容量控制）；块边界 = 明确 cue 区间
- **分块前先验证 gap**：`srt_reflow_gap_scan.py` → `r00_gaps.md` 空隙点清单（长停顿 >5s / 剪辑跳转 >10s）人工确认后作为 `--gaps` 分块的组边界依据；**已有 r00_gaps.md 则复用，勿重复探测**
- **各阶段共用同一套块**：：r01 合并文本读 `chunks/`、r01 补标点读 `r01_normalized/`、r02 翻译读 `r01_results/` 对应块、r03 分句读 `r01_results/` + `r02_results/` 对应块对照——**块边界始终来自 01 分块骨架，不做链式继承**
- **中间产物只落块级（产物单轨）**：`reflow/r01_results/`、`r02_results/`、`r03_results/`（每块独立文件，块数 = 空隙组数 × 组内片数），不再有 `r01_merged_en.txt`/`r02_translation_zh.txt` 完整文件形态
- **校验逐块化**：`check_words`/`check_breaks`/`check-r03` 支持块级模式（传 `reflow/<阶段>_results/` + `--chunks reflow/chunks/` + `--gaps r00_gaps.md`），逐块校验 + 空隙点检查，不需要先合并全文；**全局校验（块级模式一次验全部块）由主会话在所有块 subagent 全部完成后统一执行一次**，subagent 不调用全局校验（见 [subagent-dispatch#subagent 纪律](../.github/skills/subagent-dispatch/SKILL.md#subagent-纪律生成-prompt-时必须包含)）
- **回填直读 r03_results/（零拼接）**：`srt_reflow.py reflow/attach-en/check-duration` 的 r03 参数接受目录（`parse_r03_dir` 按块序解析 + **S 号全局重编号**）或单文件 r03_plan.md（兼容）——**必须合并的**仅 `r04_draft.srt`（最终产物，由 `srt_reflow.py reflow` 生成）；合并后走全局校验
- **约束（r01/r02/r03 块文件格式）**：reflow 补标点/翻译块（`r01_results/`/`r02_results/`）为**整段文字**——每块一个空隙组-片 = 一段连续文字，块内**不按 cue/句分行、不带 cue 前缀**（逐句/cue 分行会孤立 ASR 残片导致误译；校验脚本按整段解析）；**折行由脚本统一执行**（主会话产出后 `auto_wrap_file` 就地折行 / `text_merge --wrap`，subagent 输出不折行）——产物单行 ≤1000 字符（英文词边界不拆词），属**显示性换行、非语义分行**，校验按整段解析不受影响（read_file 可读）；仅 r03 分句块（`r03_results/`）用整句分组格式（`## S<n>`）、仅 translate 的 srt 类型结果保留 `段号|cue范围|` 前缀。分句语义对应仍需全貌（块内保持整句/单元语义完整，不跨块拆句——空隙为硬边界）
- **旧 `--inherit` 已弃用（deprecated）**：仅兼容旧流程，新方案从 01 分块 + 块级独立流转，不再需要继承边界

### subagent 结果文件（`text_merge.py` 输入）

- 命名：`_work/<视频名>/<任务目录>/chunk_<k>.txt`（merge→`_merge_results/`、translate→`_trans_results/`、term→`_term_results/`、humanize→`_humanize_results/`）
- **text 类型**（组-片前缀契约权威所在）：单元间空行分隔；每单元首行 `<组>-<片>\t<产出文本>`（内容可多行；**保留输入 OWNED 的组-片前缀**；单元数 = 该块 OWNED 单元数）——text 类型任务文件输出节引用本节
- **srt 类型**：每行 `段号|cue范围[~]|文本`（`~`=估算切分点，同 `s03_plan.md`）；`CARRY: c<idx>` 结转标记行独立成行
- **reflow 例外**：r01/r02/r03 块文件**不经 text_merge**（r01/r02 = 整段文字、r03 = `## S<n>` 整句分组，均无 `# CHUNK` 块头元数据，`parse_chunk_head` 无法解析）；回填**直读 `r03_results/` 目录**（`parse_r03_dir`），`r03_plan.md` 由 `join-r03` 按需生成（审核/审计用）。term 结果（`_term_results`）由主会话按 `term_en` 合并去重，亦不经 text_merge
- 写后只报 `已写入 <文件名>（N 行）`，不返回全文（见 subagent-dispatch 纪律）

### 合并产物（`text_merge.py` 输出）

- **合并产物** `<merged>`：
  - text 类型：同组片按片号无缝拼接，组间空行分隔（块结构还原）
  - srt 类型：按块序 + 全局段号重排，输出 `段号|cue范围[~]|文本` 行（即 `s03_plan.md` 行格式）
- **合并报告** `<merged>.report.md`（A 模式）：
  - 无异常 → `## 结论: 无异常（全自动合并，主 Agent 无需读取）`
  - 有异常 → `## 异常清单`（缺块 / 行数不符 / 重复产出 / 片号不连续 / cue 重叠 / cue 缺口 / CARRY）+ `## 异常块头尾窗口`（每块 OWNED 头尾各 `--window` 行 + 结果头尾，供 Agent 只读衔接窗口决策）
- 参数：`--window`（异常块头尾窗口行数，默认 3）

### 变更同步

改动上述格式时同步：本文件 + `scripts/text_chunk.py` / `scripts/text_merge.py`（docstring 与解析器）+ `redstone-conventions`（分块章节）+ `subagent-dispatch`（模板/组装）+ 各工作流主 skill（步骤引用）。

---

## 配置文件（分块机制依赖，非工作流产物）

### `configs/context_window.json`

模型窗口 + 分块/输出阈值的**单一事实源**；`context_estimate.py` 配置来源。上下文长度估算与分块建议的确定性输出。默认配置：

```json
{"context_length": 1000000, "max_output": 384000, "split_ratio": 0.05, "output_ratio": 0.8,  "amplification": 10}
```

- **`context_estimate.py` CLI 参数**（默认读 config、CLI 可覆盖）：
  - `--window`：模型总窗口上限。默认读 `context_length`
  - `--split-ratio`：单块材料占用窗口的比例上限。默认读 `split_ratio`
  - `--amplification`：最重环节预测放大倍数。默认读 `amplification`
  - `--no-amplification`：不使用放大倍数参数

- **格式（五项语义）**：
  - `context_length`：模型**实际有效**窗口上限（整数 token；输入+输出共享；非标称上限——标称 ≠ 实际有效，见下方「算法解释」）
  - `max_output`：模型**单次生成最大输出**（整数 token；输出阈值基数，通常远小于窗口）
  - `split_ratio`：**输入阈值比例** = 窗口 × 该比例 → 单块输入材料上限（须 (0,1)，宁低勿高）
  - `output_ratio`：**输出阈值比例** = max_output × 该比例 → 单块最大输出文件上限（留余量 <1，建议 0.7–0.9）
  - `amplification`：**断句等最重环节预测放大倍数**（>1；预测最大输出 = 输入材料 × 该倍数）
  - 计算结果同时受输入阈值和输出阈值限制，提供分块大小依据：
    - min落到输入侧 = 输入预算成瓶颈，单块输入上限取输入侧值、按此分块
    - min落到输出侧 = 输出预算成瓶颈，单块输入上限取输出侧值、按此分块

- **计算方式**（同时报三指标；两种预测阈值算法二选一）：
  - `输入阈值` = `窗口 × split_ratio`——单块输入材料上限
  - `输出阈值` = `max_output × output_ratio`——单块最大输出文件上限（以模型单次生成上限为基数、留余量）
  - `amplification`——最重环节预测放大倍数（预测最大输出 = 输入材料 × amplification）
  - **使用放大倍数参数**：`单块输入上限 = min(输入阈值, 输出阈值 ÷ amplification)`——输入材料同时受窗口预算与最大预测输出项约束
  - **不使用放大倍数参数**（`--no-amplification`）：`单块输入上限 = min(输入阈值, 输出阈值)`——输出侧不除以 amplification

- **算法解释**：
  - **双阈值**：字幕翻译**不接受上下文压缩**（压缩丢细节 → 失真），单块材料既不能贴近窗口上限（读约束 = 输入阈值），也不能让放大后输出超模型单次生成上限（写约束 = 输出阈值）——取 `min` 协调、宁低勿高
  - **放大倍数**：最重环节（分句）读中英两倍材料（r01 EN + r02 ZH 对照）+ 输出 r03 ≈ 对照 2×，单请求 ≈ **4×单语言材料**（实测 4.2×），故需要放大倍数预测最重环节 token 消耗——放大已并入「单块容量上限」：输入预算靠 `split_ratio` 隐含分句余量（示例 0.05 → 分句放大 4× 后 ≈ 窗口×20%）、输出预算靠 `÷amplification` 显式，二者经 min 统一后 **`--owned ≈ 单块容量上限 × 1.5 ÷ 每 cue 平均字符数`，不再额外除以放大常数**
  - **`split_ratio` 默认取 0.05**：执行在 subagent（全新上下文）；示例 0.05 → 1M 窗口 ≈ 50k token，分句放大 4× 后 ≈ 窗口×20% 仍可一次处理；0.015 试点过激（处处分片）、旧 0.3×512k 偏松（分句放大后吃力），取中间值；拿不准用默认
  - **为何 `--window` 填实际有效窗口**：**不是当前剩余窗口**（剩余受会话历史/压缩影响，agent 无法精确感知）；**标称 ≠ 实际有效**——填实际有效窗口（非标称上限），拿不准按保守 128k 配置
- 约束：
  - **只放这五项**，不写模型名等冗余
  - config 缺失/无效 → `context_estimate.py` 降级代码默认并提示 agent 询问用户期望后写入（部署时一次）
  - 变更需同步：本文件 + `context_estimate.py`（默认值/提示文案）+ `redstone-conventions`（分块章节引用）+ `reflow-redstone`（步骤 1b 定容量）

---

## 共享产物（阶段〇/一，redstone-preprocess）

### `01_subtitle_asr_fixed.srt`

- 命名：`<工作目录>/01_subtitle_asr_fixed.srt`
- 生成：preprocess §1.1（ASR 修正）
- 格式：标准 SRT——`序号\nHH:MM:SS,mmm --> HH:MM:SS,mmm\n文本`，块间空行
- 约束：
  - **只改文本、保留原时间码、不增删 cue**（时间轴骨架）
  - `[Music]` 等纯方括号标记 cue（去括号后无文本）**保留原样**，勿手动删——下游 `gap_scan`/`breaks`/`check_breaks` 动态识别跳过，reflow 核心 `io.parse_srt` 亦剔除
- 校验：`python scripts/srt_check_segments.py 01_subtitle_asr_fixed.srt --orig <原始ASR.srt> --cue-exact`

### `02_terms.md`

- 命名：`<工作目录>/02_terms.md`
- 生成：preprocess §1.3（术语确认，用户确认后定稿）
- 格式：

```markdown
# 02 术语确认表 — <视频名>

> 视频：<id/作者/时长/cue 数>
> 领域：<领域预判>
> 确认日期：<日期（用户已确认）>

## 术语映射表

| 时间戳 | 原文 | 译名 | 来源 | ASR 修正 |
|---|---|---|---|---|
| 00:00:16 | Terry Andrew Davis | 特里·安德鲁·戴维斯 | 维基 | Terra/Tara 等多处 |
```

- 约束：`原文` = 01 修正后文本；`ASR 修正` 列记录误识别映射（供组装期替换与 `asr_fixes.md` 沉淀）；表头固定不得改

---

## translate 产物（阶段二）

### `s03_plan.md`

- 命名：`<工作目录>/s03_plan.md`
- 生成：Agent（合并断句定稿，交用户审核前落盘）
- 格式：**每行一段**：

```
段号|cstart[-cend][~]|文本
```

- `cstart`/`cend` = 该段覆盖的原字幕 cue 号区间；`~` 标注该侧为估算切分点（受控例外，见 segment-subtitles）
- 示例：`1|c1-c3|This is why I am literally the smartest programmer that ever lived.`
- 校验：`python scripts/srt_check_segments.py s03_plan.md --orig <01>`

### `s04_draft.srt`

- 命名：`<工作目录>/s04_draft.srt`
- 生成：Agent（逐段翻译，逐段落盘断点续译）
- 格式：标准 SRT，双语 `en-zh`（英文行在前、中文行在后）
- 约束：时间边界 **⊆ 原字幕边界集合**（translate 特有，不允许新造时间点）；行宽软 22 / 硬 26
- 校验：`python scripts/srt_check_segments.py s04_draft.srt --orig <01>`、`python scripts/srt_check_width.py s04_draft.srt --order en-zh`

---

## reflow 产物（阶段二）

### `r00_gaps.md`

- 命名：`<工作目录>/reflow/r00_gaps.md`（默认）
- 生成：`python scripts/srt_reflow_gap_scan.py <01> -o reflow/r00_gaps.md`
- 格式（脚本生成，只读参考）：

```markdown
# r00 空隙探测报告 — <01 路径>
- 输入 / 阈值 / 非语音标记统计
## 长停顿清单
### 1. c43 → c48（9.2s）⚠️ 剪辑跳转
- 区间 / 前 cue / 后 cue / 用途
## 非语音标记 cue（[Music] 等，已跳过空隙判定）
## 使用说明
```

### `r01_breaks.md`

- 命名：`<工作目录>/reflow/r01_breaks.md`（默认）
- 生成：`python scripts/srt_reflow_breaks.py <01> -o reflow/r01_breaks.md` + **Agent 复核回填**
- 格式：

```markdown
# r01 硬性断句点清单 — <01 路径>
- 输入 / 空隙点 / 用途
## 断句点清单
### 1. c43 → c48（9.2s）⚠️ 剪辑跳转
- 区间: ...
- 前 cue c43（尾锚）: `...`
- 后 cue c48（首锚）: `...
- 强制: 两锚之间必须断句
- **Agent 复核（回填）**:
  - 性质判定: [x] 剪辑跳转… [ ] 语义停顿…
  - 断句方式: [x] 独立成段…
  - ⚠️ 游离停顿词提示（可选）
## 校验（补标点后必跑）
```

- 消费：断句点清单供 **Agent 复核回填**（空隙点级，仅含清单、**不含 01 全文**）+ 补标点 subagent **先验知识注入**（空隙断句标记 `【强制断句】`，见 task-punctuate）
- 约束：`【强制断句】` 为空隙标记、**非本文档文本**（由断句点清单派生、经复核注入补标点先验知识），Agent 不手写

### `r01_normalized/chunk_<k>.txt`（归一化输入）

- 命名：`<工作目录>/reflow/r01_normalized/chunk_<k>.txt`
- 生成：脚本 `srt_reflow_normalize.py`（`python scripts/srt_reflow_normalize.py reflow/chunks/ -o reflow/r01_normalized/`）——**一次性处理整个 chunks/ 目录**，每块独立合并、互不影响，命令只运行一次
- 格式：**保留分区结构 + 合并连续文本**——每块与 `chunks/chunk_<k>.txt` 同构（块头 `# CHUNK` + `## BEFORE`/`## OWNED`/`## AFTER` 分区），但**各分区内 cue 文本已预先合并**为一段连续文字（剔除 `[Music]`/`[Applause]` 等纯标记 cue）、经 `wrap_text` 折行 ≤1000 字符/行（英文空格处折、不拆词；中文按字符折）
- 定位：补标点 subagent 输入（替代直接读 `chunks/` 的 cue 结构，subagent 无需再自行拼接 OWNED 文本）——**仅作补标点输入，非校验基准**（校验仍读 `chunks/` 的 cue 区间 + `r01_results/`）
- 约束：折行为**显示性换行、非语义分行**——subagent 按整段解析、**忽略行尾换行**；纯标记块（无语音 cue）输出空块注释（`> 本块无语音 cue`），对应补标点产物为空块、校验跳过
- 消费：步骤 3 补标点 subagent（`r01_results/` 对应块）

### `r01_results/chunk_<k>.txt`（补标点块）

- 命名：`<工作目录>/reflow/r01_results/chunk_<k>.txt`
- 生成：Agent（步骤 1 逐块补标点 subagent；各块独立文件，块数 = 空隙组数 × 组内片数）
- 格式：**整段文字**——每块 = 对应 `reflow/chunks/chunk_<k>.txt` 的 OWNED 空隙组-片 = **一段连续英文**；块内加标点但**不按 cue 分行、不按句分行**（逐句/cue 分行会孤立 ASR 残片导致误译）；**不带 `c<idx>\t时间码\t` 前缀**；**折行由脚本统一执行**（主会话产出后 `auto_wrap_file` 就地折行，subagent 输出不折行）——产物单行 ≤1000 字符（英文在空格处折、不拆词），属**显示性换行、非语义分行**（read_file 可读、check_words 按整段解析）；CONTEXT 仅作语境，**片边界跨块句允许补全**（见约束）
- 约束：仅加标点、不改措辞；空隙断句标记处按复核方式断句；词序列与对应 01 cue 段一致（`check_words` 块级模式按整段解析校验）；**跨块句补全（仅片边界）**——OWNED 首句承接前块 → 行首 `【承接句】<完整句>`；末句延伸后块 → 行首 `【延伸句】<完整句>`；相邻块对同一跨块句都补全（块 k `【延伸句】` ≡ 块 k+1 `【承接句】`），主会话「衔接归位」后**只在一侧留无标记完整句、另一侧不留该句文本**；空隙边界不承接
- 消费：步骤 2 整段翻译（`r02_results/` 对应块）、`check_breaks`/`check_words` 块级模式（`【承接句】`/`【延伸句】` 标记由校验脚本识别、不计入词序列）

### `r02_results/chunk_<k>.txt`（翻译块）

- 命名：`<工作目录>/reflow/r02_results/chunk_<k>.txt`
- 生成：Agent（步骤 2 逐块整段翻译 subagent，**先验知识注入 humanizer 注入版规则（humanizer-inject）**；各块独立文件，块数 = 空隙组数 × 组内片数）
- 格式：**整段中文译文**——每块 = 对应 `r01_results/chunk_<k>.txt` 的整段翻译；块内**不按 cue 分行、不按句分行、不编号、不输出原文**；**不带 `c<idx>\t时间码\t` 前缀**；**折行由脚本统一执行**（主会话产出后 `auto_wrap_file` 就地折行，subagent 输出不折行）——产物单行 ≤1000 字符（中文按字符折），属**显示性换行、非语义分行**（read_file 可读、check-r03 按整段作 ZH 忠实基准）；CONTEXT 只读不产出
- 约束：r02 定稿即自然译文（去翻译腔内联）；`check-r03` 块级模式以本文件整段为 ZH 忠实基准（r03 逐字复用）
- 消费：归一化（`r02_normalized/` 折行副本）、分句（`r03_results/` 对应块）、`check-r03` 块级模式

### `r02_normalized/chunk_<k>.txt`（分句输入·r02 折行副本）

- 命名：`<工作目录>/reflow/r02_normalized/chunk_<k>.txt`
- 生成：脚本 `srt_reflow_normalize.py` 纯文本模式（`python scripts/srt_reflow_normalize.py reflow/r02_results/ -o reflow/r02_normalized/`）——**复制 + 长度限制**：把 r02 译文复制为折行副本（≤1000 字符/行），一次性整个目录跑完（每块独立）
- 格式：与 `r02_results/` 同内容（整段中文译文），仅按 `wrap_text` 折行 ≤1000 字符/行（中文按字符折）——**显示性换行、非语义分行**，分句 subagent 按整段解析、忽略行尾换行
- 定位：分句 subagent 输入（替代直接读可能超长单行的 r02 原稿）；**不改 r02 原稿**——ZH 忠实校验（check-r03 ④）与术语核对（check_terms）仍以 `r02_results/` 为基准
- 消费：分句 subagent（`r03_results/` 对应块）

### `r03_plan.md`

- 命名：`<工作目录>/reflow/r03_plan.md`
- 生成：脚本 `join-r03`（`python scripts/srt_reflow.py join-r03 reflow/r03_results/ -o reflow/r03_plan.md [--chunks reflow/chunks/]`）——**按需**，仅审核/审计要人读完整方案时生成；**回填不经此文件**（直读 `r03_results/`，见该节）
- 拼接与校验（join-r03 内建）：按块序拼接 + **S 号全局重编号**（块内从 1 连续 → 全局唯一，合句重映射）+ 结构校验（缺块/重复 S<n>/每块可解析）；异常出清单返回 1，主会话只读报告
- 格式（`plan.py parse_r03` 解析标准，**不得改动**）：

```markdown
## S<n>            （合句为 S<n+m>，如 S19+20）
- EN: <整句英文全文>
- ZH: <整句中文>
- 关系: 1:1 | 1:n
### S<n><a>
- EN: <互斥英文片段>
- ZH: <中文片段>
```

- 头部可加 `> ` 注释（如残片剔除说明）
- 约束：
  - **EN/ZH 值单行**：`- EN:`/`- ZH:` 的值各占**恰好一行**，值内禁止换行/折行/空行（`plan.py parse_r03` 按行解析 `- EN:`/`- ZH:` 前缀；跨行破坏解析与忠实校验）
  - 子单元 ZH 拼接（去标点）== 整句 ZH（忠实铁律）；EN 片段互斥拼接 == 整句 EN
  - 拆句用整句号+小写后缀（`6a/6b`）；合句标题用 `## S<n+m>`（如 `S19+20`，不用方括号）；不手写 cue 集/区间
- 校验：`python scripts/srt_reflow.py check-r03 reflow/r03_results/ <01> reflow/r02_results/ --chunks reflow/chunks/`（锚定唯一 / 互斥 / 行宽 22-26 / ZH 忠实 / 括号引号配对 / 碎片 / 中英失配）

### `r04_draft.srt`

- 命名：`<工作目录>/reflow/r04_draft.srt`（预览，止步 `_work/`）
- 生成：`python scripts/srt_reflow.py reflow reflow/r03_results/ <01> -o reflow/r04_draft.srt [--anchored reflow/r03_anchored.jsonl] [--cjk-speed 5]`（r03 传目录，目录模式按块序解析 + S 号全局重编号；r03_plan.md 单文件兼容）
- 格式：标准 SRT，中文单语；时间轴 = 原轴合并/切分，允许 100ms 预测点（不入原边界集）
- 校验：`python scripts/srt_check_segments.py <输出> --orig <01>`、`python scripts/srt_reflow.py check-duration reflow/r04_draft.srt reflow/r03_results/`

### `r04_bilingual.srt`

- 命名：`<工作目录>/reflow/r04_bilingual.srt`
- 生成：`python scripts/srt_reflow.py attach-en reflow/r04_draft.srt reflow/r03_results/ -o reflow/r04_bilingual.srt`（r03 目录或文件均可）
- 格式：标准 SRT，双语 `en-zh`；英文行 = r03 英文片段（拆句子单元取各自互斥片段，**不得复用整句原文**）
- 校验：`python scripts/srt_check_width.py <输出> --order en-zh`

### `r04_alerts.md`

- 命名：`<工作目录>/reflow/r04_alerts.md`
- 生成：`srt_reflow.py reflow` 同步落盘
- 格式：文本告警清单（每行一条）——时长分布 / ⏱️ 超长极短 / 🔪 长句碎片 / ⏱️ 独立短句 / 📖 阅读插值 / 单元内 gap / ✂️ 剪辑跳转 / 预测点 / 📏 行宽 >22
- 消费：Agent 复核（长句碎片回报裁决）、与 `r00_gaps.md` 对照

### `r03_anchored.jsonl`

- 命名：`<工作目录>/reflow/r03_anchored.jsonl`
- 生成：`srt_reflow.py reflow --anchored`（默认 r03 同目录）
- 格式：**JSONL**（每行一个整句对象，无缩进；`json.loads` 逐行可解析）
- 字段：`key` / `rel` / `en` / `zh` / `anchor`(unique/non-unique/failed) / `alloc`(cue/reading/ratio) / `start` / `end` / `span_ms` / `units[{key,en,zh,hit,cues}]`
- 消费：人工/机器逐行审查（哪些句非唯一/失败、哪些单元走了字数兜底 hit=false、哪些走了阅读插值 alloc=reading）


