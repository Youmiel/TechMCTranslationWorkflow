# 产物格式与标记约定（PRODUCT_FORMATS）

> 全部工作流产物格式 / 结构 / 分隔符 / 标记约定的**总入口**。本文件载**通用部分**，专有产物按工作流分列：

| 归属 | 文件 | 内容 |
|------|------|------|
| 通用（本文件） | `PRODUCT_FORMATS.md` | 通用约定 / 变更同步清单 / **产物速查（共享）** / 共享产物（阶段〇/一）/ 通用文本分块 / 配置文件 |
| translate | [PRODUCT_FORMATS_TRANSLATE.md](PRODUCT_FORMATS_TRANSLATE.md) | 产物速查 + `s03_plan.md` / `s04_draft.srt` / `_merge_results` / `_trans_results` / `_humanize_results` |
| reflow | [PRODUCT_FORMATS_REFLOW.md](PRODUCT_FORMATS_REFLOW.md) | 产物速查 + `r00`–`r04` / `r03_anchored.jsonl` / `r03_*` 分句输入 |
| reflow2 | [PRODUCT_FORMATS_REFLOW2.md](PRODUCT_FORMATS_REFLOW2.md) | 产物速查 + `en_timeline` / `zh_sentences` / `align` / reflow2 `r04_*` |

> 各 SKILL 步骤与脚本 docstring 只引用本文件（或对应分文件）、不重复展开；**处理某产物前先查对应节**，勿现查代码猜格式。
> 脚本解析器（`plan.py parse_r03`、`srt_check_segments.py` 等）是格式的**实现标准**，本文件是**约定标准**——两者必须一致，变更需同步（见「变更同步清单」）。
>
> **跨工作流复用约定的写法**：同一约定被多种工作流使用时，详细描述只写在**最早使用该约定的工作流文件**内，后建立的工作流文件只留短句 + 章节链接（建立顺序：translate 最早 → reflow → reflow2 最晚）。

## 通用约定

- **编码**：全部 UTF-8（无 BOM）
- **块间分隔 = 空行**（`r01_results/`/`r02_results/` 各块文件的段落边界唯一规范）；**手写产物禁止写任何标记文本**（`[break]`/英文注释等都不写）；跨块句补全标记仅限 `【承接句】`/`【延伸句】`（见 [PRODUCT_FORMATS_REFLOW#r01_results](PRODUCT_FORMATS_REFLOW.md#r01_resultschunk_ktxt补标点块) 节）
- **空隙标记 `【强制断句】`**：**非产物文本**——由 `srt_reflow_breaks.py` 断句点清单派生、经 Agent 复核后作为先验知识注入补标点 subagent（见 task-punctuate），Agent 不手写
- **结构标记**（`## S<n>`/`- EN:`/`- ZH:`/`- 关系:`/`### S<n><a>`、`段号|cX-cY|`、术语表表头）是脚本解析标准，不得改动格式

## 变更同步清单

改动任何产物的**格式 / 分隔符 / 字段**时必须同步：

1. **对应格式文件**——通用机制与共享产物改本文件；工作流专有产物改对应分文件（[translate](PRODUCT_FORMATS_TRANSLATE.md) / [reflow](PRODUCT_FORMATS_REFLOW.md) / [reflow2](PRODUCT_FORMATS_REFLOW2.md)）
2. **生成 / 解析脚本**：
   - reflow：`srt_reflow_gap_scan.py`、`srt_reflow_breaks.py`、`srt_reflow_check_breaks.py`、`srt_reflow_check_words.py`、`srt_reflow_check_sentence_len.py`、`srt_reflow_presplit.py`、`srt_reflow_build_r03.py`、`srt_reflow_core/{io,plan,allocate,alerts,reflow,attach}.py`
   - reflow2：`srt_reflow2_etimeline.py`、`srt_reflow2_stitch.py`、`srt_reflow2_zsent.py`、`srt_reflow2_backfill.py`（源头固化链 + 跨块句衔接归位）
   - 字幕通用：`srt_join_parts.py`、`text_chunk.py`、`text_merge.py`
   - 校验：`srt_check_segments.py`、`srt_check_width.py`、`srt_check_plan_words.py`（translate 断句措辞）、`srt_check_terms.py`（reflow r02 / translate 译文术语，跨工作流）
3. **引用 SKILL 步骤**：`reflow-redstone`（步骤 1/2/4/5/6）、`reflow2`（步骤 1-7）、`translate-redstone`（阶段二）、`redstone-preprocess`（产物契约）、`segment-subtitles`（断句/行宽）
4. **脚本 docstring**（格式描述与实现一致）

> 本文件是格式约定的事实标准；脚本若与本文冲突，以本文为准并修脚本（或先改本文再改脚本，保持同步）。

---

## 产物速查（共享）

> 本表只列**共享产物**（不属任何单一工作流，阶段〇/一产出或跨阶段使用）。
> 各工作流专有产物的速查表在对应文件顶部：[translate](PRODUCT_FORMATS_TRANSLATE.md#产物速查) · [reflow](PRODUCT_FORMATS_REFLOW.md#产物速查) · [reflow2](PRODUCT_FORMATS_REFLOW2.md#产物速查)。
> 各产物**详细规格**（命名 / 生成 / 格式 / 约束 / 校验）：共享产物见本文件「共享产物」节；专有产物见各自文件对应节。

| 产物 | 生成者 | 消费/校验脚本 |
|------|--------|----------------|
| `01_subtitle_asr_fixed.srt` | Agent（英文预整理 subagent 分块派发 + `srt_join_parts.py` 合并） | `srt_check_segments.py --cue-exact`；reflow gap/breaks/words |
| `_en_results/chunk_<k>.srt` | Agent（英文预整理 subagent） | `srt_join_parts.py`、`srt_check_segments.py --cue-exact` |
| `02_terms.md` | Agent（用户确认） | 翻译固定译名、ASR 修正组装 |
| `term_pending.md` / `term_pending_<i>.md` | Agent（主会话汇总后写；按 30 条/块拆分） | `term-researcher`（分批派发输入） |
| `term_resolve_<i>.md` | Agent（`term-researcher` 研究型 agent） | 阶段一 §1.3 确认、阶段三 coverage_log |
| `wiki_pending_<i>.md` | Agent（主会话；仅批量 Wiki 请求才建） | `wiki-researcher`（派发输入） |
| `wiki_resolve_<i>.md` | Agent（`wiki-researcher` 研究型 agent） | 主会话取结论、阶段三 coverage_log |
| `prompts/<任务>-chunk_<k>.txt`（派发存档） | 渲染脚本 `render_subagent_prompt.py`（reflow/reflow2/translate 阶段二）/ Agent 手工（term-recognition/en-preprocess/fix/summary，未接入渲染脚本） | 复盘查阅（无自动校验，规则见 subagent-dispatch「提示词存档」） |

---

## 通用文本分块（text_chunk / text_merge）

> 长视频分块的**统一格式契约**——SRT 与非 SRT 产物共用。
> - 工具：`scripts/text_chunk.py`（分块）+ `scripts/text_merge.py`（合并）
> - 用法与调度见 [redstone-conventions#长视频分块](../.github/skills/redstone-conventions/SKILL.md#长视频分块全流程通用机制) 与 [subagent-dispatch](../.github/skills/subagent-dispatch/SKILL.md)
> - 旧 `scripts/srt_chunk.py` 保留兼容（历史产物 / 旧流程），**新任务一律用 `text_chunk.py`**
>
> **产物一律块级（产物单轨）**：分块与不分块同一处理逻辑、同一产物契约。
> - 块级 `chunk_<k>.txt` + 需合并的产物（如 reflow 的 `r04_draft.srt`）按块序 / 骨架拼接
> - 每块 OWNED + CONTEXT、独立处理、中间不拼全文
> - reflow 回填**直读 `r03_results/` 目录**（`parse_r03_dir` 按块序解析 + S 号全局重编号），无需拼 r03_plan.md
> - 逻辑一致 ⇒ 小输入即可验证分块流程逻辑（reflow 的**空隙点强制切块**与 `--owned` 语义见「块级流水线」节）

### 块文件格式（`text_chunk.py` 输出，`chunk_<k>.txt`）

- **块头（首行，机器可解析元数据）**：`# CHUNK <k>/<N>  SRC: <文件名>  TYPE: <srt|text>  UNIT: <语义单位>  OWN: <组标识列表>  CTX: BEFORE <B> AFTER <A>`
- **标记语言统一（全英文大写简单词）**：
  - `#` = 说明 / 元数据行（块头 `# CHUNK`、分区内 `# SOURCE` / `--- PREV/NEXT ---` 等标注）
  - `##` = 分区标记（`## BEFORE` / `## OWNED` / `## AFTER`，脚本硬依赖）
  - 不用中文 / `###` 混标
- **分区顺序（LLM 语义优先）**：
  1. `## BEFORE`（本块之前，只读，非空才输出）
  2. `## OWNED`（本块负责产出）
  3. `## AFTER`（本块之后，只读，非空才输出）
  - 前文在前、内容中间、后文在后，subagent 按语义顺序阅读；首块无 BEFORE、末块无 AFTER
- **`## OWNED`**：subagent 必须产出的内容；srt 每行一条 `c<idx>\t<时间码>\t<文本>`；text **单元间空行分隔**、单元首行 `<组>-<片>\t<内容>`（内容可多行，如 r03 markdown）
- **`## BEFORE` / `## AFTER`**：前后只读上下文，格式同 OWNED；解析脚本按 `## ` 分区通用判断切 OWNED（任意分区标题切换），不受顺序/缺区影响；旧块头格式（`# chunk ... 源:`）不兼容新解析，历史产物不再重新合并
- **`manifest.md`**：块清单（组/片 → 块号映射），`text_merge.py` 与人工核对用
- **类型与语义单位**：
  - `srt`：单位=cue（`01_subtitle_asr_fixed.srt`、双语段 SRT），`--owned` 默认 100、`--ctx` 默认 6；**`--gaps-file <tsv>`**（推荐，读生效空隙点集）或 **`--gaps`**（脚本自行探测，兼容）时块标识 =「空隙组-片」（如 `块0`、`块1-片10`），空隙点强制切块（reflow，见「块级流水线」）
  - `text`：单位=`段`（空行分隔，r01/r02 默认）/ `句`（按标点，同组多句片号连续）/ `整句组`（r03 的 `## S<n>`），`--owned` 默认 1、`--ctx` 默认 1
- **超长单位细分**：text 单原子单位超过 `--max-chars`（默认 6000 字符）时拆为「组-片」（如 `块0-片2`）；**同组多片合并时无缝拼接**（中文空连接、英文空格），解决 r01 块 0 拆 0a..0f 场景
- **约束**：块边界永远在单位边界（不切开 cue / 语义段）；text 单元可多行；确定性输出

### 块级流水线（从 01 分块，reflow r01→r02→r03 中间不拼全文）

> 目标：让 reflow 的 r01 / r02 / r03 各子块**独立处理、按块传递**：
> - 中间**不拼全文**，校验**逐块化**——只有最终 r04 是必须合并的
> - r03 回填**直读 `r03_results/` 目录**（零拼接、LLM 不读全量）
> - `r03_plan.md` 仅审核 / 审计时 `join-r03` 按需生成
>
> 减少「拼全文 → 整读 → 再分块」的反复。

- **一次分块（从 01）**：`python scripts/text_chunk.py <01.srt> --type srt --gaps-file <r00_gaps_active.tsv> --owned <每块cue数> --ctx <衔接cue数> --out reflow/chunks/`
  - 块 = 「空隙组-片」（**空隙点强制切块 = 语义硬边界**、组内按 `--owned` 分片 = 容量控制）
  - 块边界 = 明确 cue 区间
  - `--gaps-file` 读**生效空隙点集**（`status=excluded` 自动跳过 = 排除源切分缺陷的正式通道）；旧 `--gaps` 保留兼容（自行探测，不读人工裁决）
- **分块前先验证 gap**：`srt_reflow_gap_scan.py` → `r00_gaps.md`（人读报告：长停顿 >5s / 剪辑跳转 >10s / **疑似源切分缺陷**分节）+ `r00_gaps_active.tsv`（生效集，人工可编辑）。
  - **已有 tsv 则复用，勿重复探测**；人工裁决改 tsv 的 `status` 列（`excluded` = 排除），**重跑不覆盖人工决定**
- **各阶段共用同一套块**：：r01 合并文本读 `chunks/`、r01 补标点读 `r01_normalized/`、r02 翻译读 `r01_results/` 对应块、r03 分句读 `r01_results/` + `r02_results/` 对应块对照——**块边界始终来自 01 分块骨架，不做链式继承**
- **中间产物只落块级（产物单轨）**：`reflow/r01_results/`、`r02_results/`、`r03_results/`（每块独立文件，块数 = 空隙组数 × 组内片数），不再有 `r01_merged_en.txt`/`r02_translation_zh.txt` 完整文件形态
- **校验逐块化**：`check_words` / `check_breaks` / `check-r03` 支持块级模式（传 `reflow/<阶段>_results/` + `--chunks reflow/chunks/` + `--gaps r00_gaps_active.tsv`），逐块校验 + 空隙点检查，不需要先合并全文。
  - **全局校验（块级模式一次验全部块）由主会话在所有块 subagent 全部完成后统一执行一次**
  - subagent 不调用全局校验（见 [subagent-dispatch#纪律母版](../.github/skills/subagent-dispatch/SKILL.md#纪律母版派发时必须整体追加)「五、工作区与工具纪律」）
- **回填直读 r03_results/（零拼接）**：`srt_reflow.py reflow` / `attach-en` / `check-duration` 的 r03 参数接受目录（`parse_r03_dir` 按块序解析 + **S 号全局重编号**）或单文件 r03_plan.md（兼容）。
  - **必须合并的**仅 `r04_draft.srt`（最终产物，由 `srt_reflow.py reflow` 生成）；合并后走全局校验
- **约束（r01/r02/r03 块文件格式）**：reflow 补标点 / 翻译块（`r01_results/` / `r02_results/`）为**整段文字**，每块一个空隙组-片 = 一段连续文字。
  - 块内**不按 cue / 句分行、不带 cue 前缀**（逐句 / cue 分行会孤立 ASR 残片导致误译；校验脚本按整段解析）
  - **折行由脚本统一执行**（主会话产出后 `auto_wrap_file` 就地折行 / `text_merge --wrap`，subagent 输出不折行）——产物单行 ≤1000 字符（英文词边界不拆词），属**显示性换行、非语义分行**，校验按整段解析不受影响
  > ⚠️ **折行宽度为形态描述、非判据**：实际值由脚本 `MAX_LINE` 决定（`shared/srt_common.py`）。**行宽判据**（目标区间/硬限制）权威在 `segment-subtitles`「行宽规则」，本文件不复述。
  - 仅 r03 分句块（`r03_results/`）用整句分组格式（`## S<n>`）
  - 仅 translate 的 srt 类型结果保留 `段号|cue范围|` 前缀
  - 分句语义对应仍需全貌（块内保持整句 / 单元语义完整，不跨块拆句——空隙为硬边界）
- **旧 `--inherit` 已弃用（deprecated）**：仅兼容旧流程，新方案从 01 分块 + 块级独立流转，不需要继承边界

### subagent 结果文件（`text_merge.py` 输入）

- 命名：`_work/<视频名>/<任务目录>/chunk_<k>.txt`。任务目录：
  - merge → `_merge_results/`
  - translate → `_trans_results/`
  - term → `_term_results/`
  - humanize → `_humanize_results/`
- **text 类型**（组-片前缀契约权威所在）：
  - 单元间空行分隔
  - 每单元首行 `<组>-<片>\t<产出文本>`（内容可多行；**保留输入 OWNED 的组-片前缀**；单元数 = 该块 OWNED 单元数）
  - text 类型任务文件输出节引用本节
- **srt 类型**：每行 `段号|cue范围[~]|文本`（`~`=估算切分点，同 `s03_plan.md`）；`CARRY: c<idx>` 结转标记行独立成行
- **reflow 例外**：r01 / r02 / r03 块文件**不经 text_merge**。
  - 原因：r01/r02 = 整段文字、r03 = `## S<n>` 整句分组，均无 `# CHUNK` 块头元数据，`parse_chunk_head` 无法解析
  - 回填**直读 `r03_results/` 目录**（`parse_r03_dir`）；`r03_plan.md` 由 `join-r03` 按需生成（审核 / 审计用）
  - term 结果（`_term_results`）由主会话按 `term_en` 合并去重，亦不经 text_merge
- **preprocess 例外**：`_en_results/chunk_<k>.srt`（第一次遍历英文预整理，裸 SRT 片段）**不经 text_merge**。
  - 原因：text_merge 的 srt 模式面向断句合并（`段号|cue范围|文本` 前缀、丢时间码）
  - 01 需保留逐 cue 时间码，由 `srt_join_parts.py` 按块序拼接 + 全局段号重排 + cue 数强制校验
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

模型窗口 + 分块/输出阈值的**单一事实源**；`context_estimate.py` 配置来源。上下文长度估算与分块建议的确定性输出。

**值按使用者的模型填写**（不同模型容量差异大，无通用默认值）；格式（五项）：

```json
{"context_length": <模型有效窗口>, "max_output": <单次生成上限>, "split_ratio": 0.05, "output_ratio": <0.0-1.0>, "amplification": <倍数>}
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
  - **放大倍数**：最重环节（分句）读中英两倍材料（r01 EN + r02 ZH 对照）+ 输出 r03 ≈ 对照 2×，单请求 ≈ **4×单语言材料**（实测 4.2×），故需要放大倍数预测最重环节 token 消耗。
    - 放大已并入「单块容量上限」：输入预算靠 `split_ratio` 隐含分句余量（示例 0.05 → 分句放大 4× 后 ≈ 窗口×20%）、输出预算靠 `÷amplification` 显式
    - 二者经 min 统一后 **`--owned ≈ 单块容量上限 × 1.5 ÷ 每 cue 平均字符数`，不再额外除以放大常数**
  - **`split_ratio` 推荐取 0.05**（比例类参数，不随模型容量变）：执行在 subagent（全新上下文）。
    - 示例：0.05 → 512k 窗口 ≈ 25k token，分句放大 4× 后 ≈ 窗口×20%，仍可一次处理
    - 0.015 试点过激（处处分片）、旧 0.3×512k 偏松（分句放大后吃力），取中间值；拿不准用 0.05
  - **为何 `--window` 填实际有效窗口**：**不是当前剩余窗口**（剩余受会话历史/压缩影响，agent 无法精确感知）；**标称 ≠ 实际有效**——填实际有效窗口（非标称上限），拿不准按保守 128k 配置
- 约束：
  - **只放这五项**，不写模型名等冗余
  - config 缺失/无效 → `context_estimate.py` 降级代码内置兜底值并提示 agent 询问用户期望后写入（部署时一次；**兜底值仅为应急，可能与你模型不符**）
  - 变更需同步：本文件 + `context_estimate.py`（默认值/提示文案）+ `redstone-conventions`（分块章节引用）+ `reflow-redstone`（步骤 1b 定容量）

---

## 共享产物（阶段〇/一，redstone-preprocess）

### `01_subtitle_asr_fixed.srt`

- 命名：`<工作目录>/01_subtitle_asr_fixed.srt`
- 生成：preprocess §1.1 步骤 2（第一次遍历 subagent 分块派发 → `srt_join_parts.py` 拼接 `_en_results/` 各块 SRT 片段 → 01）
- 格式：标准 SRT——`序号\nHH:MM:SS,mmm --> HH:MM:SS,mmm\n文本`，块间空行
- 约束：
  - **只改文本、保留原时间码、不增删 cue**（时间轴骨架）
  - `[Music]` 等纯方括号标记 cue（去括号后无文本）**保留原样**，勿手动删——下游 `gap_scan`/`breaks`/`check_breaks` 动态识别跳过，reflow 核心 `io.parse_srt` 亦剔除
  - **内嵌非语音事件标记**（DownSub/YouTube 自动字幕的 `[laughter]`/`[clears throat]` 等，夹在语音文本中）由第一次遍历 subagent **语义识别并剔除**（不进 01 词序列；剔除后空文本 cue 保留时间码）——与纯标记 cue 不同，内嵌标记**无法硬编码枚举/规则探测**，靠 agent 语义判断（见 `term-scan/task-en-preprocess` 规则 4）
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

- 约束：
  - `原文` = 01 修正后文本
  - `ASR 修正` 列记录误识别映射（供组装期替换与 `asr_fixes.md` 沉淀）
  - 表头固定不得改
  - 来源列可标 `[ASR 推测]` / `[推断]` / `[待审核]` / `[通用词]`——`[通用词]` = 通用标准译名（公认译名、无需项目约定），确认后**不入库**（见 `term-registration`「通用标准译名判定」）

### `term_pending.md` / `term_resolve_<i>.md`（§1.2 查证产物）

- 命名：`<工作目录>/term_pending.md`（主会话写**全量**待查列表）、`<工作目录>/term_pending_<i>.md`（分块，每块 ≤30 条）、`<工作目录>/term_resolve_<i>.md`（各块查证结果，与待查列表**同名前缀**）
- 生成：preprocess §1.2——全量待查列表由主会话 §1.1 汇总后写，按 30 条/块拆分后**逐块串行派发**；各块结果由 `term-researcher`（研究型 agent）写盘，主会话合并
- 格式：
  - `term_pending.md` / `term_pending_<i>.md`：每行 `term_en | 首次时间戳 | 已给候选/依据`（L3 未命中 + 决策行）
  - `term_resolve_<i>.md`：每行 `term_en\t候选译名\t数据源\t依据\t[标记]`（标记 = `[推断]`/`[待审核]`；数据源 = 缓存路径 / MCP 名 / indexes/repos 路径）
- 消费：§1.3 用户确认表（候选译名/依据）、阶段三 coverage_log（数据源命中统计）、断点恢复（粒度 = 块）
- 约束：查证 agent **不返回页面原文**（页面只进一次性上下文，返回每词一行压缩总结）；`[待审核]` 必须带候选，不得只留原文；命中缓存时数据源列**须附刷新状态**（`已刷新` / `未过期` / `未过期判定：仅核查存在性` / `刷新失败：<原因>`，见 `docs/WIKI_CACHE_FORMAT.md`「刷新策略」）

### `wiki_pending_<i>.md` / `wiki_resolve_<i>.md`（翻译过程 Wiki 查询产物）

- 命名：`<工作目录>/wiki_pending_<i>.md`（待查清单，批量才建；无编号 `wiki_pending.md`）、`<工作目录>/wiki_resolve_<i>.md`（查证结果，与清单**同名前缀**）
- 生成：翻译过程任意阶段需请求 Wiki 时——主会话写待查清单，派 `wiki-researcher`（研究型 agent，任务文件 `wiki-tools/task-wiki-query.md`）逐项执行（缓存 → 过期判定 → 主动刷新 → 降级链），写盘结果；单个问题不建清单文件，直接以问题文本作引用
- 格式：
  - `wiki_pending_<i>.md`：每行 `查询项 | 待解答的具体问题 | 已知线索`
  - `wiki_resolve_<i>.md`：每行 `查询项\t结论\t数据源\t刷新状态\t[标记]`（刷新状态 = `未过期`/`已刷新`/`新抓取`/`刷新失败：<原因>`/`未过期判定：仅核查存在性`；数据源 = 缓存路径 / MCP 名 / indexes/repos 路径 / `fetch_wiki` / `browser`）
- 消费：主会话取结论（不读页面原文）；阶段三 coverage_log（数据源命中统计）
- 约束：查证 agent **不返回页面原文**（只进一次性上下文，返回每问一行压缩总结）；**过期缓存不得静默复用**（刷新失败须在刷新状态列显式标注）；`[待审核]` 必须带候选；`[需浏览器]` 由主会话执行兜底抓取
- 与 `term_*` 的分工：**术语译名**走 `term_pending`/`term_resolve`（`task-term-resolve.md`）；**其余 Wiki 请求**走 `wiki_pending`/`wiki_resolve`（`task-wiki-query.md`）
