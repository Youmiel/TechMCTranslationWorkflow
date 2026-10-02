# reflow 产物格式（PRODUCT_FORMATS_REFLOW）

> reflow-redstone（方案二 语义回填重排；建立早于 reflow2）阶段三 专有产物的格式 / 结构 / 标记约定。
> 通用约定、共享产物（`01` / `02` / `term_*` / `wiki_*`）、通用文本分块、配置文件 → [PRODUCT_FORMATS](PRODUCT_FORMATS.md)。
> **reflow2 复用本文件的块骨架与 r01/r02/r03 格式**——reflow2 文件内只留短句 + 链接，不重复展开。

## 产物速查

| 产物 | 生成者 | 消费/校验脚本 |
|------|--------|----------------|
| `r00_gaps.md` | `srt_reflow_gap_scan.py` | Agent 参考 |
| `r00_gaps_active.tsv` | `srt_reflow_gap_scan.py`（人工可编辑） | `text_chunk.py --gaps-file`、`srt_reflow_check_breaks.py --gaps`（**生效空隙点集单一事实源**） |
| `r01_breaks.md` | `srt_reflow_breaks.py` + Agent 回填 | `srt_reflow_check_breaks.py` |
| `r01_normalized/chunk_<k>.txt` | 脚本 `srt_reflow_normalize.py`（一次性全目录） | Agent（补标点 subagent 输入） |
| `r01_results/chunk_<k>.txt` | Agent（补标点 subagent） | `srt_reflow_check_breaks.py`、`srt_reflow_check_words.py`（块级模式） |
| `r02_results/chunk_<k>.txt` | Agent（整段翻译 subagent） | `check-r03`（ZH 忠实基准） |
| `r03_normalized_1/chunk_<k>.txt` | 脚本 `srt_reflow_presplit.py`（EN 预分句 E1..En） | Agent（分句 subagent 输入） |
| `r03_normalized_2/chunk_<k>.txt` | 脚本 `srt_reflow_presplit.py`（ZH r03 模板骨架：Z 句 + 子句段预填） | Agent（分句 subagent 输入，[语义分句（LLM）](../.github/skills/reflow-redstone/semantic-reflow.md#语义分句) 填空） |
| `r03_zslim/chunk_<k>.txt` | 脚本 `srt_reflow_presplit.py`（`--zh-list-out`；ZH **整句级精简列表**） | Agent（句子匹配 subagent 输入，仅[脚本断句（机械）](../.github/skills/reflow-redstone/semantic-reflow.md#脚本断句)） |
| `r03_matches/chunk_<k>.txt` | Agent（句子匹配 subagent，[脚本断句（机械）](../.github/skills/reflow-redstone/semantic-reflow.md#脚本断句)） | 脚本 `srt_reflow_build_r03.py`（机械断句填回） |
| `r03_results/chunk_<k>.txt` | Agent（分句 subagent，[语义分句（LLM）](../.github/skills/reflow-redstone/semantic-reflow.md#语义分句)）或脚本 `srt_reflow_build_r03.py`（经 `r03_matches/`） | `parse_r03_dir`（回填直读）、`check-r03`、`join-r03` |
| `r03_plan.md` | 脚本 `join-r03`（按需，审核/审计用） | `plan.py parse_r03`、`check-r03` |
| `r04_draft.srt` | `srt_reflow.py reflow` | `srt_check_segments.py`、`check-duration` |
| `r04_bilingual.srt` | `srt_reflow.py attach-en` | `srt_check_width.py --order zh-en` |
| `r04_alerts.md` | `srt_reflow.py reflow` | Agent 参考 |
| `r03_anchored.jsonl` | `srt_reflow.py reflow` | 人工/机器审查 |

> 块级产物（`r01_normalized` / `r01_results` / `r02_results` / `r03_*`）的**块数 = 空隙组数 × 组内片数**。

## `r00_gaps.md` / `r00_gaps_active.tsv`

- 命名：`<工作目录>/reflow/r00_gaps.md`（默认）、同目录 `r00_gaps_active.tsv`
- 生成：`python scripts/srt_reflow_gap_scan.py <01> -o reflow/r00_gaps.md [--tsv reflow/r00_gaps_active.tsv]`
- **`r00_gaps.md`（人读报告）**：

```markdown
# r00 空隙探测报告 — <01 路径>
- 输入 / 阈值 / 非语音标记统计 / 长停顿总数（含疑似源缺陷数、已排除数、生效数）
## ⚠️ 疑似源切分缺陷（N 处，建议人工裁决）      ← 判据：① 前 cue 末尾无句末标点 ② 后 cue 首字母小写
### 1. c88 → c89（5.2s）[生效·待裁决]          ← 两条强信号同时成立的空隙
- 判据 / 区间 / 前 cue / 后 cue / 处置
## 长停顿清单（>5s，N 处，按时长降序）           ← 剪辑跳转 ⚠️ / 普通长停顿
### 1. c43 → c48（9.2s）⚠️ 剪辑跳转
- 区间 / 前 cue / 后 cue / 用途
## 非语音标记 cue

> [Music] 等，已跳过空隙判定
## 使用说明
```

- **`r00_gaps_active.tsv`（生效空隙点集 = 单一事实源，人工可编辑）**——下游分块 `--gaps-file` 与断句校验 `check_breaks --gaps` 统一读它，不再各自探测：

```
# a_idx	b_idx	gap_ms	kind	status	note
c88	c89	5150	suspect	suspect	前 cue 末尾无句末标点 + 后 cue 首字母小写（疑似源字幕切分缺陷：…）
c43	c48	9200	jump	active	剪辑跳转
```

| `kind` | 含义 |
|--------|------|
| `gap` | 普通长停顿 |
| `jump` | 剪辑跳转（>10s） |
| `suspect` | **疑似源切分缺陷**（前 cue 无句末标点 + 后 cue 首字母小写） |

| `status` | 含义 | 下游行为 |
|----------|------|----------|
| `active` | 真实空隙 | 分块硬边界 + 断句点 + 校验 |
| `suspect` | 疑似源缺陷，**待人工裁决（默认仍生效）** | 同 `active`（脚本只报告不改行为） |
| `excluded` | **人工确认排除** | 不分块 / 不断句 / 校验跳过 |

- **裁决方式**：把该行 `status` 改为 `excluded`（排除）或 `active`（生效）——**重跑 `gap_scan` 不覆盖人工决定**（同 `(a_idx,b_idx)` 的 status/note 保留）
- **排除空隙仅靠改 tsv**（勿去掉 `--gaps` 开关，也不要改 `r00_gaps.md` 格式以骗过校验正则——那些做法已废弃）

## `r01_breaks.md`

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
## 校验

> 补标点后必跑
```

- 消费：断句点清单供 **Agent 复核回填**（空隙点级，仅含清单、**不含 01 全文**）+ 补标点 subagent **先验知识注入**（空隙断句标记 `【强制断句】`，见 task-punctuate）
- 约束：`【强制断句】` 为空隙标记、**非本文档文本**（由断句点清单派生、经复核注入补标点先验知识），Agent 不手写

## `r01_normalized/chunk_<k>.txt`

- 命名：`<工作目录>/reflow/r01_normalized/chunk_<k>.txt`
- 生成：脚本 `srt_reflow_normalize.py`（`python scripts/srt_reflow_normalize.py reflow/chunks/ -o reflow/r01_normalized/`）——**一次性处理整个 chunks/ 目录**，每块独立合并、互不影响，命令只运行一次
- 格式：**保留分区结构 + 合并连续文本**——每块与 `chunks/chunk_<k>.txt` 同构（块头 `# CHUNK` + `## BEFORE`/`## OWNED`/`## AFTER` 分区），但**各分区内 cue 文本已预先合并**为一段连续文字（剔除 `[Music]`/`[Applause]` 等纯标记 cue）、经 `wrap_text` 折行 ≤1000 字符/行（英文空格处折、不拆词；中文按字符折）
  > ⚠️ **折行宽度为形态描述、非判据**：实际值由脚本 `MAX_LINE` 决定（`shared/srt_common.py`），改值以代码为准；本文件不重复取值范围定义。
- 定位：补标点 subagent 输入（替代直接读 `chunks/` 的 cue 结构，subagent 无需再自行拼接 OWNED 文本）——**仅作补标点输入，非校验基准**（校验仍读 `chunks/` 的 cue 区间 + `r01_results/`）
- 约束：折行为**显示性换行、非语义分行**——subagent 按整段解析、**忽略行尾换行**；纯标记块（无语音 cue）输出空块注释（`> 本块无语音 cue`），对应补标点产物为空块、校验跳过
- 消费：补标点 subagent（`r01_results/` 对应块）

## `r01_results/chunk_<k>.txt`

- 命名：`<工作目录>/reflow/r01_results/chunk_<k>.txt`
- 生成：Agent（逐块补标点 subagent；各块独立文件，块数 = 空隙组数 × 组内片数）
- 格式：**整段文字**，每块 = 对应 `reflow/chunks/chunk_<k>.txt` 的 OWNED 空隙组-片 = **一段连续英文**。
  - 块内加标点但**不按 cue 分行、不按句分行**（逐句 / cue 分行会孤立 ASR 残片导致误译）
  - **不带 `c<idx>\t时间码\t` 前缀**
  - **折行由脚本统一执行**（主会话产出后 `auto_wrap_file` 就地折行，subagent 输出不折行）——产物单行 ≤1000 字符（英文在空格处折、不拆词），属**显示性换行、非语义分行**（check_words 按整段解析）  - CONTEXT 仅作语境，**片边界跨块句允许补全**（见约束）
- 约束：
  - 仅加标点、不改措辞
  - 空隙断句标记处按复核方式断句
  - 词序列与对应 01 cue 段一致（`check_words` 块级模式按整段解析校验）
  - **跨块句补全（仅片边界）**：
    - OWNED 首句承接前块 → 行首 `【承接句】<完整句>`
    - 末句延伸后块 → 行首 `【延伸句】<完整句>`
    - 相邻块对同一跨块句都补全（块 k `【延伸句】` ≡ 块 k+1 `【承接句】`）；主会话“衔接归位”后**只在一侧留无标记完整句、另一侧不留该句文本**
  - 空隙边界不承接
- 消费：整段翻译（`r02_results/` 对应块）、预分句标号（`r03_normalized_1/`，见该节）、`check_breaks`/`check_words` 块级模式（`【承接句】`/`【延伸句】` 标记由校验脚本识别、不计入词序列）

## `r02_results/chunk_<k>.txt`

- 命名：`<工作目录>/reflow/r02_results/chunk_<k>.txt`
- 生成：Agent（逐块整段翻译 subagent，**先验知识注入 humanizer 注入版规则（humanizer-inject）**；各块独立文件，块数 = 空隙组数 × 组内片数）
- 格式：**整段中文译文**，每块 = 对应 `r01_results/chunk_<k>.txt` 的整段翻译。
  - 块内**不按 cue 分行、不按句分行、不编号、不输出原文**
  - **不带 `c<idx>\t时间码\t` 前缀**
  - **折行由脚本统一执行**（主会话产出后 `auto_wrap_file` 就地折行，subagent 输出不折行）——产物单行 ≤1000 字符（中文按字符折），属**显示性换行、非语义分行**（check-r03 按整段作 ZH 忠实基准）
  - CONTEXT 只读不产出
- 约束：r02 定稿即自然译文（去翻译腔内联）；`check-r03` 块级模式以本文件整段为 ZH 忠实基准（r03 逐字复用）
- 消费：ZH 归一化模板骨架（`r03_normalized_2/`，见该节）、分句（`r03_results/` 对应块）、`check-r03` 块级模式

## `r03_normalized_1/chunk_<k>.txt`

- 命名：`<工作目录>/reflow/r03_normalized_1/chunk_<k>.txt`
- 生成：脚本 `srt_reflow_presplit.py`（`python scripts/srt_reflow_presplit.py reflow/r01_results/ reflow/r02_results/ -o reflow/`，一次性全目录）——EN 按句末标点（角色表 `terminator`）预分句（常见缩写 Mr./Fig./e.g. 等保护、省略号不切分、跨块句标记剥离）标号 `E1..En`
- 格式：每句一行 `- E1: <句文本>`（句内 `wrap_text` 折行 ≤1000 字符、续行顶格，显示性换行非语义分行）
- 定位：分句 subagent 输入的**整句骨架**（替代自行逐句分句）——脚本只做句级初分，游离停顿词归属/长句语义再切仍由 agent 处理；**不形成中英对照**（与 `r03_normalized_2/` 各自编号）
- 消费：分句 subagent（`r03_results/` 对应块）

## `r03_normalized_2/chunk_<k>.txt`

- 命名：`<工作目录>/reflow/r03_normalized_2/chunk_<k>.txt`
- 生成：脚本 `srt_reflow_presplit.py`（一次性全目录）。命令：
  ```
  python scripts/srt_reflow_presplit.py reflow/r01_results/ reflow/r02_results/ -o reflow/
  ```
  - ZH 按句末标点（同一通用角色表；中文侧即 `。！？…`）预分句（括号配平保护）标号 `Z1..Zm`
  - 句内按标点切候选段 + 代价最小化拼合 [15,22]（硬 ≤27）
  > ⚠️ **宽度区间为脚本行为描述、非本文件判据**：由 `srt_reflow_presplit.py` 执行（阈值源自 `shared/srt_common.py`）；subagent **不折行、不自行断段**，无需据此计算。
    - **直读 `r02_results/` 原稿**（脚本读取不受行宽限制，无需折行副本）
- 格式：**r03 模板骨架**（r03 整句分组格式的 ZH 预填版），每 Z 句一组 `## S?_Z<n>（默认 E<n>）`：
  - `- ZH:` 整句原文预填
  - `- 关系:` 预填 1:1 / 1:n
  - `### S?_Z<n><a>` 子句段预填（带 `> 段宽` 注释）
  - `- EN:` 为 `<待填>` 占位
  - S 号 `S?_Z<n>` 为占位（待分句 agent 替换为块内连续 `S<号>`）
- 定位：分句 subagent 输入的**断句基线 + 填空模板**。
  - 脚本承担长短判断 / 宽度 / 忠实（子句段只在标点处切、不增删改，段拼接 == Z 原文 == r02）
  - agent 只做**填空与核对**（S 号 / EN / 关系 / 子单元 EN / 对应 / 游离词）
  - `默认 E<n>` 为按序启发式提示须核对
  - 不形成中英对照
- 参数：`--soft-min/--soft-max/--hard-max/--min-unit`（多语言通用）+ 标点角色表 `--punct-terminators/--punct-strong/--punct-clause/--punct-list`（**默认取跨语言通用表** `shared.srt_common.PUNCT_ROLE_CHARS`；改字符集会改 Z 句数、使 `align/` 失效，谨慎）；旧 `--punct-levels` 仍接受（按字符归属映射到角色，不推荐）
- 消费：分句 subagent（`r03_results/` 对应块）

## `r03_zslim/chunk_<k>.txt`

- 命名：`<工作目录>/reflow/r03_zslim/chunk_<k>.txt`
- 生成：脚本 `srt_reflow_presplit.py` 的 **`--zh-list-out <目录>`**（与 r03_normalized_2 同源 `split_zh`、同命令一次性生成），**独立产物路径**，不复用 / 替代 r03_normalized_2 模板骨架。命令：
  ```
  python scripts/srt_reflow_presplit.py reflow/r01_results/ reflow/r02_results/ -o reflow/ --zh-list-out reflow/r03_zslim
  ```
- 格式：**整句级 Z 精简列表**——每行 `Z<n> <整句文本>`（Z 号与 r03_normalized_2 的 `Z1..Zm` **一一对应**）。
  - 无 `## S?_Z<n>` 标题、`- EN: <待填>` 占位、`- 关系:`、`### S?_Z<n><a>` 子句段、`> 段宽/⚠️` 注释等脚手架
- 定位：**仅 5-2 句子匹配 subagent（`task-match`）的 ZH 输入**。
  - task-match 只做整句级 Z↔E 语义对应，只需整句文本，不需子句段 / 占位 / 注释（那些是 5-1 task-split 填空或 build-r03 机械填回才需要的）
  - 整句级信息仅占模板骨架 ~20%，本产物省 ~80% 输入 token
- 约束：
  - 不用于 5-1（task-split 仍读 r03_normalized_2 模板骨架填空）
  - 不用于 build-r03 填回（其子句段机械切分仍读 r03_normalized_2）
  - r03_normalized_2 与 r03_zslim 并存、各司其职
- 消费：句子匹配 subagent（`r03_matches/` 对应块）

## `r03_matches/chunk_<k>.txt`

- 命名：`<工作目录>/reflow/r03_matches/chunk_<k>.txt`
- 生成：Agent（句子匹配 subagent，`task-match`；各块独立文件，块数 = 空隙组数 × 组内片数）——LLM **只做句子匹配**（不做断句、不填 EN、不写 r03）
- 格式：**匹配文件**——每行一个整句：左 = 合并成该整句的 ZH 句组（Z 号升序、`+` 连接）、右 = 对应 EN 句组（E 号升序、`+` 连接）：
  ```
  Z5+Z6+Z7+Z8 = E5
  Z2 = E2
  ```
  - 行序不限（脚本按 Z 组最小号排序）；空行分隔可选；`#` 开头为注释行（如游离词归属 / 合并原因）
  - **只含号对应、不抄文本**（文本由脚本从预分句 / 模板回填）；不增删改原文
- 约束：**覆盖完整性**——全部 Z 号（`Z1..Zm`）与全部 E 号（`E1..En`）必须各出现恰好一次；漏任何一句 → `build-r03` 在 r03 产物写 `> ⚠️ 脚本断句·未匹配` 标记（漏句留空、不静默消失）
- 消费：脚本 `srt_reflow_build_r03.py`（机械断句填回 → `r03_results/`）

## `r03_plan.md`

- 命名：`<工作目录>/reflow/r03_plan.md`
- 生成：脚本 `join-r03`（`python scripts/srt_reflow.py join-r03 reflow/r03_results/ -o reflow/r03_plan.md [--chunks reflow/chunks/]`）——**按需**，仅审核/审计要人读完整方案时生成；**回填不经此文件**（直读 `r03_results/`，见该节）
- 拼接与校验（join-r03 内建）：按块序拼接 + **S 号全局重编号**（块内从 1 连续 → 全局唯一，合句重映射）+ 结构校验（缺块/重复 S<n>/每块可解析）；异常出清单返回 1，主会话只读报告
- 格式（`plan.py parse_r03` 解析标准，**不得改动**）：

```markdown
## S<n>

> 合句为 S<n+m>，如 S19+20
- EN: <整句英文全文>
- ZH: <整句中文>
- 关系: 1:1 | 1:n
### S<n><a>
- EN: <互斥英文片段>
- ZH: <中文片段>
```

- 头部可加 `> ` 注释（如残片剔除说明）
- **漏句留空（不静默丢弃，两路径通用）**：某 Z 句无法对应 EN / 超宽段切不动 → 产物中写 `> ⚠️ 未匹配 Z<n>：<文本>`（脚本断句路径由 `build-r03` 自动写 `> ⚠️ 脚本断句·未匹配 Z<n>: <文本>`）—— 漏句会让 check-r03 ④ ZH 忠实报缺句，留空标记便于按 `> ⚠️` 精确定位、定点补 / 回 r02 改
- 约束：
  - **EN/ZH 值单行**：`- EN:`/`- ZH:` 的值各占**恰好一行**，值内禁止换行/折行/空行（`plan.py parse_r03` 按行解析 `- EN:`/`- ZH:` 前缀；跨行破坏解析与忠实校验）
  - 子单元 ZH 拼接（去标点）== 整句 ZH（忠实铁律）；EN 片段互斥拼接 == 整句 EN
  - 拆句用整句号+小写后缀（`6a/6b`）；合句标题用 `## S<n+m>`（如 `S19+20`，不用方括号）；不手写 cue 集/区间
- 校验：`python scripts/srt_reflow.py check-r03 reflow/r03_results/ <01> reflow/r02_results/ --chunks reflow/chunks/`（锚定唯一 / 互斥 / 行宽 22-27 / ZH 忠实 / 括号引号配对 / 碎片 / 中英失配）

## `r03_results/chunk_<k>.txt`

- 命名：`<工作目录>/reflow/r03_results/chunk_<k>.txt`（每块一个，块数 = 空隙组数 × 组内片数）
- 生成：**两条路径任一**——
  - [语义分句（LLM）](../.github/skills/reflow-redstone/semantic-reflow.md#语义分句)：分句 subagent（`task-split`），读 `r03_normalized_1/`（EN 骨架）+ `r03_normalized_2/`（ZH 模板骨架）填空
  - [脚本断句（机械）](../.github/skills/reflow-redstone/semantic-reflow.md#脚本断句)：脚本 `srt_reflow_build_r03.py`，读 `r03_matches/`（号对应）+ 预分句骨架机械填回
- 格式：**同 `r03_plan.md`**（`## S<n>` 整句分组）——差别仅在 **S 号块内从 1 连续编号**（不跨块引用），回填时由 `parse_r03_dir` 按块序**全局重编号**
- 消费：回填直读（`parse_r03_dir`，零拼接）、`check-r03` 块级模式、`join-r03`（按需生成 `r03_plan.md`）

## `r04_draft.srt`

- 命名：`<工作目录>/reflow/r04_draft.srt`（预览，止步 `_work/`）
- 生成：`python scripts/srt_reflow.py reflow reflow/r03_results/ <01> -o reflow/r04_draft.srt [--anchored reflow/r03_anchored.jsonl] [--cjk-speed 5]`（r03 传目录，目录模式按块序解析 + S 号全局重编号；r03_plan.md 单文件兼容）
- 格式：标准 SRT，中文单语；时间轴 = 原轴合并/切分，允许 100ms 预测点（不入原边界集）
- 校验：`python scripts/srt_check_segments.py <输出> --orig <01>`、`python scripts/srt_reflow.py check-duration reflow/r04_draft.srt reflow/r03_results/`

## `r04_bilingual.srt`

- 命名：`<工作目录>/reflow/r04_bilingual.srt`
- 生成：`python scripts/srt_reflow.py attach-en reflow/r04_draft.srt reflow/r03_results/ -o reflow/r04_bilingual.srt`（r03 目录或文件均可）
- 格式：标准 SRT，双语 `zh-en`（中文行在前）；英文行 = r03 英文片段（拆句子单元取各自互斥片段，**不得复用整句原文**）
- 校验：`python scripts/srt_check_width.py <输出> --order zh-en`

## `r04_alerts.md`

- 命名：`<工作目录>/reflow/r04_alerts.md`
- 生成：`srt_reflow.py reflow` 同步落盘
- 格式：文本告警清单（每行一条）——时长分布 / ⏱️ 超长极短 / 🔪 长句碎片 / ⏱️ 独立短句 / 📖 阅读插值 / 单元内 gap / ✂️ 剪辑跳转 / 预测点 / 📏 行宽 >22
- 消费：Agent 复核（长句碎片回报裁决）、与 `r00_gaps.md` 对照

## `r03_anchored.jsonl`

- 命名：`<工作目录>/reflow/r03_anchored.jsonl`
- 生成：`srt_reflow.py reflow --anchored`（默认 r03 同目录）
- 格式：**JSONL**（每行一个整句对象，无缩进；`json.loads` 逐行可解析）
- 字段：`key` / `rel` / `en` / `zh` / `anchor`(unique/non-unique/failed) / `alloc`(cue/reading/ratio) / `start` / `end` / `span_ms` / `units[{key,en,zh,hit,cues}]`
- 消费：人工/机器逐行审查（哪些句非唯一/失败、哪些单元走了字数兜底 hit=false、哪些走了阅读插值 alloc=reading）
