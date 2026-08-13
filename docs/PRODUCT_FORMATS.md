# 产物格式与标记约定（PRODUCT_FORMATS）

> 全部工作流产物的格式 / 结构 / 分隔符 / 标记约定统一在此——共享 `01`/`02`（preprocess）、translate `s03`/`s04`、reflow `r00`–`r04` + `r03_anchored.jsonl`。
> 各 SKILL 步骤与脚本 docstring 只引用本文件、不重复展开；**处理某产物前先查本文件对应节**，勿现查代码猜格式。
> 脚本解析器（`plan.py parse_r03`、`srt_check_segments.py` 等）是格式的**实现标准**，本文件是**约定标准**——两者必须一致，变更需同步（见「变更同步清单」）。

## 通用约定

- **编码**：全部 UTF-8（无 BOM）
- **块间分隔 = 空行**（`r01_merged_en.txt` / `r02_translation_zh.txt` 的块边界唯一规范）；**手写产物禁止写任何标记文本**（`【强制断句】`/`[break]`/英文注释等都不写）
- **空隙标记 `【强制断句】`**：仅存在于 `r01_breaks.md` 的「补标点输入文本」内，由 `srt_reflow_breaks.py` 生成，Agent 不手写
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
| `r01_merged_en.txt` | reflow（**仅短视频不分块路径**；分块时用 `r01_results/`） | Agent（补标点） | `srt_reflow_check_breaks.py`、`srt_reflow_check_words.py`（块级模式验 `r01_results/`） |
| `r02_translation_zh.txt` | reflow（**仅短视频不分块路径**；分块时用 `r02_results/`） | Agent（整段翻译） | `check-r03`（ZH 忠实基准；块级模式用 `r02_results/`） |
| `r03_plan.md` | reflow | Agent（分句语义对应） | `plan.py parse_r03`、`check-r03` |
| `r04_draft.srt` | reflow | `srt_reflow.py reflow` | `srt_check_segments.py`、`check-duration` |
| `r04_bilingual.srt` | reflow | `srt_reflow.py attach-en` | `srt_check_width.py --order en-zh` |
| `r04_alerts.md` | reflow | `srt_reflow.py reflow` | Agent 参考 |
| `r03_anchored.jsonl` | reflow | `srt_reflow.py reflow` | 人工/机器审查 |

---

## 通用文本分块（text_chunk / text_merge）

> 长视频分块的**统一格式契约**——SRT 与非 SRT 产物共用。工具：`scripts/text_chunk.py`（分块）+ `scripts/text_merge.py`（合并）。用法与调度见 [redstone-conventions#长视频分块](../.github/skills/redstone-conventions/SKILL.md#长视频分块全流程通用机制) 与 [subagent-dispatch](../.github/skills/subagent-dispatch/SKILL.md)。
> 旧 `scripts/srt_chunk.py` 保留兼容（历史产物/旧流程），**新任务一律用 `text_chunk.py`**。
> **分块与不分块共用同一套处理逻辑；不分块 = 分块只有一块（N=1）的特例**：处理步骤一致，只差块数与产物格式——分块（N>1）= 块级 `r01_results/`/`r02_results/`/`r03_results/` + 拼 `r03_plan.md`（块边界优先在空隙点=语义硬边界、组内按 N cue 分片；每块 OWNED+CONTEXT、独立处理、中间不拼全文）；不分块（N=1）= 单块直接产出完整 `r01_merged_en.txt`/`r02_translation_zh.txt`/`r03_plan.md`。逻辑一致 ⇒ 单块即小规模测试。

### 块文件格式（`text_chunk.py` 输出，`chunk_<k>.txt`）

- **块头（首行，机器可解析元数据）**：`# chunk <k>/<N>  源: <文件名>  类型: <srt|text>  单位: <语义单位>  负责: <组标识列表>  上下文: 前<B> 后<A>`
- **`## OWNED（本块负责产出）`**：subagent 必须产出的内容；srt 每行一条 `c<idx>\t<时间码>\t<文本>`；text **单元间空行分隔**、单元首行 `<组>-<片>\t<内容>`（内容可多行，如 r03 markdown）
- **`## CONTEXT（只读衔接，不产出）`**：前后只读上下文，格式同 OWNED
- **`manifest.md`**：块清单（组/片 → 块号映射），`text_merge.py` 与人工核对用
- **类型与语义单位**：
  - `srt`：单位=cue（`01_subtitle_asr_fixed.srt`、双语段 SRT），`--owned` 默认 100、`--ctx` 默认 6；**`--gaps`** 时块标识 =「空隙组-片」（如 `块0`、`块1-片10`），块边界优先在空隙点
  - `text`：单位=`段`（空行分隔，r01/r02 默认）/ `句`（按标点，同组多句片号连续）/ `整句组`（r03 的 `## S<n>`），`--owned` 默认 1、`--ctx` 默认 1
- **超长单位细分**：text 单原子单位超过 `--max-chars`（默认 6000 字符）时拆为「组-片」（如 `块0-片2`）；**同组多片合并时无缝拼接**（中文空连接、英文空格），解决 r01 块 0 拆 0a..0f 场景
- **约束**：块边界永远在单位边界（不切开 cue / 语义段）；text 单元可多行；确定性输出

### 块级流水线（从 01 分块，reflow r01→r02→r03 中间不拼全文）

> 目标：让 reflow 的 r01→r02→r03 各子块**独立处理、按块传递**，中间**不拼全文**，校验**逐块化**——只有 r03→r03_plan.md（回填输入）与最终 r04 是必须合并的。减少"拼全文→整读→再分块"的反复。

- **一次分块（从 01）**：`python scripts/text_chunk.py <01.srt> --type srt --gaps --owned <N> --ctx <M> --out reflow/chunks/`——块 = 「空隙组-片」（块边界优先在空隙点=语义硬边界、组内按 N cue 分片=窗口控制）；块边界 = 明确 cue 区间
- **分块前先验证 gap**：`srt_reflow_gap_scan.py` → `r00_gaps.md` 空隙点清单（长停顿 >5s / 剪辑跳转 >10s）人工确认后作为 `--gaps` 分块的组边界依据；**已有 r00_gaps.md 则复用，勿重复探测**
- **各阶段共用同一套块**：r01 补标点读 chunks/ 的 cue 区间、r02 翻译读 `r01_results/` 对应块、r03 分句读 `r01_results/` + `r02_results/` 对应块对照——**块边界始终来自 01 分块骨架，不做链式继承**
- **中间产物只落块级**：`reflow/r01_results/`、`r02_results/`、`r03_results/`（每块独立文件，**不生成 r01_merged_en.txt / r02_translation_zh.txt**——分块时彻底只留块级；仅短视频不分块路径才有这两个完整文件）
- **校验逐块化**：`check_words`/`check_breaks`/`check-r03` 支持块级模式（传 `reflow/<阶段>_results/` + `--chunks reflow/chunks/` + `--gaps r00_gaps.md`），逐块校验 + 空隙点检查，不需要先合并全文；**全局校验（块级模式一次验全部块）由主会话在所有块产出后统一执行一次**，subagent 不调用全局校验（见 [subagent-dispatch#subagent 纪律](../.github/skills/subagent-dispatch/SKILL.md#subagent-纪律生成-prompt-时必须包含)）
- **必须合并的**：`r03_plan.md`（`srt_reflow.py` 回填输入，各块 r03 方案按块序直接拼接）、`r04_draft.srt`（最终产物，由 `srt_reflow.py reflow` 生成）——这两个合并后走全局校验
- **约束（r01/r02/r03 块文件格式）**：reflow 补标点/翻译块（`r01_results/`/`r02_results/`）为**整段文字**——每块一个空隙组-片 = 一段连续文字，块内**不按 cue/句分行、不带 cue 前缀**（逐句/cue 分行会孤立 ASR 残片导致误译；校验脚本按整段解析）；仅 r03 分句块（`r03_results/`）用整句分组格式（`## S<n>`）、仅 translate 的 srt 类型结果保留 `段号|cue范围|` 前缀。分句语义对应仍需全貌（块内保持整句/单元语义完整，不跨块拆句——空隙为硬边界）
- **旧 `--inherit` 已弃用（deprecated）**：仅兼容旧流程，新方案从 01 分块 + 块级独立流转，不再需要继承边界

### subagent 结果文件（`text_merge.py` 输入）

- 命名：`_work/<视频名>/<任务目录>/chunk_<k>.txt`（merge→`_merge_results/`、translate→`_trans_results/`、term→`_term_results/`、humanize→`_humanize_results/`）
- **text 类型**：单元间空行分隔；每单元首行 `<组>-<片>\t<产出文本>`（内容可多行；**保留输入 OWNED 的组-片前缀**；单元数 = 该块 OWNED 单元数）
- **srt 类型**：每行 `段号|cue范围[~]|文本`（`~`=估算切分点，同 `s03_plan.md`）；`CARRY: c<idx>` 结转标记行独立成行
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

- 角色：模型窗口上限的**单一事实源**（`context_estimate.py` 的 `--window` 默认读它）
- 格式：仅 `context_length` 一个字段（整数 = 模型**实际有效**窗口上限，token；非标称上限，见 redstone-conventions「标称 ≠ 实际有效」）

```json
{ "context_length": 128000 }
```

- 约束：
  - **只放一个值**，不写模型名等冗余
  - config 缺失/无效 → `context_estimate.py` 降级默认（128000）并提示 agent 询问用户期望窗口后写入（部署时一次）
  - 变更需同步：本文件 + `context_estimate.py`（默认值/提示文案）+ `redstone-conventions`（分块 `--window` 口径）

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
- 后 cue c48（首锚）: `...`
- 强制: 两锚之间必须断句
- **Agent 复核（回填）**:
  - 性质判定: [x] 剪辑跳转… [ ] 语义停顿…
  - 断句方式: [x] 独立成段…
  - ⚠️ 游离停顿词提示（可选）
## 补标点输入文本（直接交给 LLM，保留空隙断句标记）
> 说明
```text
<按 cue 拼接文本>
【强制断句】        ← 空隙处注入的标记行（脚本生成，Agent 不手写）
<按 cue 拼接文本>
```
## 校验（补标点后必跑）
```

- 约束：`【强制断句】` 行是**空隙标记**，仅在本文档「补标点输入文本」内，由脚本注入

### `r01_results/chunk_<k>.txt`（分块路径补标点块）

- 命名：`<工作目录>/reflow/r01_results/chunk_<k>.txt`
- 生成：Agent（步骤 1b 逐块补标点 subagent）
- 格式：**整段文字**——每块 = 对应 `reflow/chunks/chunk_<k>.txt` 的 OWNED 空隙组-片 = **一段连续英文**；块内加标点但**不按 cue 分行、不按句分行**（逐句/cue 分行会孤立 ASR 残片导致误译）；**不带 `c<idx>\t时间码\t` 前缀**；CONTEXT 只读不产出
- 约束：仅加标点、不改措辞；空隙断句标记处按复核方式断句；词序列与对应 01 cue 段一致（`check_words` 块级模式按整段解析校验）
- 消费：步骤 2 整段翻译（`r02_results/` 对应块）、`check_breaks`/`check_words` 块级模式

### `r01_merged_en.txt`

- 命名：`<工作目录>/reflow/r01_merged_en.txt`
- 生成：Agent（步骤 1 补标点，基于「补标点输入文本」）
- 格式：**块结构**——每块 = 空隙间一段连续英文文本；块内加标点但**不按句分行**；**块间空行分隔**
- 约束：
  - **禁写任何标记文本**（块边界就是空行；`【强制断句】`/`[break]`/英文注释一律不写）
  - 空隙标记处按复核方式强制断句（不跨空隙合句）；仅加标点、不改措辞
- 校验：`python scripts/srt_reflow_check_breaks.py <01> reflow/r01_merged_en.txt`、`python scripts/srt_reflow_check_words.py <01> reflow/r01_merged_en.txt`

> **分块/不分块格式对齐**：`r01_results/chunk_<k>.txt`（分块）与 `r01_merged_en.txt` 的一个块（不分块）格式语义一致——都是「空隙组-片/空隙间一段连续英文」；差异仅在分块时一块一个文件、不分块时整段一个文件。

### `r02_results/chunk_<k>.txt`（分块路径翻译块）

- 命名：`<工作目录>/reflow/r02_results/chunk_<k>.txt`
- 生成：Agent（步骤 2a 逐块整段翻译 subagent，**先验知识注入 humanizer-zh 规则**）
- 格式：**整段中文译文**——每块 = 对应 `r01_results/chunk_<k>.txt` 的整段翻译；块内**不按 cue 分行、不按句分行、不编号、不输出原文**；**不带 `c<idx>\t时间码\t` 前缀**；CONTEXT 只读不产出
- 约束：r02 定稿即自然译文（去翻译腔内联）；`check-r03` 块级模式以本文件整段为 ZH 忠实基准（r03 逐字复用）
- 消费：步骤 4 分句（`r03_results/` 对应块）、`check-r03` 块级模式

### `r02_translation_zh.txt`

- 命名：`<工作目录>/reflow/r02_translation_zh.txt`
- 生成：Agent（步骤 2 整段翻译）
- 格式：**块结构，与 `r01_merged_en.txt` 的块一一对应**——每块 = 对应 r01 空隙块的整段中文翻译；块内不按句分行、不编号、不输出原文、保留全部标点；**块间空行分隔**
- 约束：r02 定稿即自然译文（去翻译腔内联）；`check-r03` 以 r02 为 ZH 忠实基准（r03 逐字复用）
- 消费：步骤 4 分句、步骤 5 回填

> **分块/不分块格式对齐**：`r02_results/chunk_<k>.txt`（分块）与 `r02_translation_zh.txt` 的一个块（不分块）格式语义一致——都是「对应 r01 块的整段中文」；差异仅在分块时一块一个文件、不分块时整段一个文件。

### `r03_plan.md`

- 命名：`<工作目录>/reflow/r03_plan.md`
- 生成：Agent（步骤 4 分句语义对应）
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
  - 子单元 ZH 拼接（去标点）== 整句 ZH（忠实铁律）；EN 片段互斥拼接 == 整句 EN
  - 拆句用整句号+小写后缀（`6a/6b`）；合句标 `[19+20]`；不手写 cue 集/区间
- 校验：`python scripts/srt_reflow.py check-r03 reflow/r03_plan.md <01> reflow/r02_translation_zh.txt`（锚定唯一 / 互斥 / 行宽 22-26 / ZH 忠实 / 括号引号配对 / 碎片 / 中英失配）

### `r04_draft.srt`

- 命名：`<工作目录>/reflow/r04_draft.srt`（预览，止步 `_work/`）
- 生成：`python scripts/srt_reflow.py reflow r03_plan.md <01> -o reflow/r04_draft.srt [--anchored reflow/r03_anchored.jsonl] [--cjk-speed 5]`
- 格式：标准 SRT，中文单语；时间轴 = 原轴合并/切分，允许 100ms 预测点（不入原边界集）
- 校验：`python scripts/srt_check_segments.py <输出> --orig <01>`、`python scripts/srt_reflow.py check-duration reflow/r04_draft.srt r03_plan.md`

### `r04_bilingual.srt`

- 命名：`<工作目录>/reflow/r04_bilingual.srt`
- 生成：`python scripts/srt_reflow.py attach-en reflow/r04_draft.srt r03_plan.md -o reflow/r04_bilingual.srt`
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


