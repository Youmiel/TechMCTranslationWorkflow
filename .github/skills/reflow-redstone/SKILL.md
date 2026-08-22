---
name: reflow-redstone
description: Minecraft 红石技术视频字幕的语义回填（reflow）工作流——以原字幕时间轴为骨架，合并全文补标点、整段翻译、分句建立"整句↔译文单元"、脚本化回填重排时间轴。共享 translate-redstone 的阶段〇/一（redstone-preprocess）、审核（redstone-review）、收尾（redstone-finalize），核心差异在阶段二。
---

# 红石字幕语义回填（reflow-redstone）

> 定位：以原字幕时间轴为骨架的**语义回填**（reflow）——合并全文补标点、整段翻译、翻译后分句建立"整句 ↔ 译文单元"、**脚本化回填重排时间轴**（碎片合并 / 整句锚定 / 单元级分配 / 预测切分点）。与 translate 的区别在阶段二；阶段〇/一/二½/三 共享。

## 适用范围

- **一次一个视频**，精细处理，不批量
- **输入无关**：优质人工字幕 / ASR 碎片字幕统一处理（不做质量判定、不分支）——两条路径由同一"合并补标点 → 分句对应 → 回填"机制覆盖
- **阅读舒适优先**：单条字幕以"读得舒服"为准（≤22 字、语义完整、节奏自然）；原轴只是时间骨架 + 真实 cue 边界参考，不因"尊重原轴"保留超长句
- 不检测 / 不处理"ASR 相对音频的时间偏移"（需画面/音频，超出纯文本范围）
- 纯文本翻译，不依赖视频画面/音频

## 输入 / 输出

### 工作目录

| 目录 | 角色 | 读写 |
|------|------|------|
| `_input/` | 待处理字幕入口 | 只读输入 |
| `_output/` | 最终交付输出 | 写正式稿 |
| `_work/<视频名>/` | 中间产物 + 断点恢复 + 临时脚本 | 只读写**当前视频**子目录 |

> 工作区隔离（临时脚本禁写 `scripts/`、禁止参考其它视频等）见 [redstone-conventions#工作区隔离](../redstone-conventions/SKILL.md#工作区隔离)。

### 输入

- `<工作目录>/../_input/<文件名>.srt`（带时间码）——必须有原轴可回填
- YouTube transcript（无时间码）**不适用**本工作流，走 translate

### 输出

- `<工作目录>/../_output/<文件名>.reflow.srt`，默认双语 en-zh（英文行 = 分句原文，中文行 = 对应译文），时间轴 = 以原轴为基础局部合并/切分
- 输出变体（`bilingual` 默认 / `zh-only` / `annotated`）见 [redstone-conventions#语言顺序与输出变体](../redstone-conventions/SKILL.md#语言顺序与输出变体)

### 中间产物与断点恢复

**全流程各阶段（子 skill）的输入与产物**：

1. **阶段〇/一 领域预判与术语补齐**（`redstone-preprocess`）——输入 `_input/` 原始字幕 → 产物 `<工作目录>/01_subtitle_asr_fixed.srt`、`<工作目录>/02_terms.md`
2. **阶段二 语义回填**（本工作流，产物在 `<工作目录>/reflow/`）
   - 输入：`01` + `02`
   - **`context_estimate.py` 只定 `--owned`（每块 cue 数）；执行一律 subagent**（块数由空隙组 × 组内分片决定，见 conventions「长视频分块」）。产物统一块级，按序：
     - 步骤 1 空隙探测 + 硬性断句 → `r00_gaps.md`、`r01_breaks.md`
     - 步骤 2 确定块大小 + 分块 → `chunks/`（从 01 `--gaps` 分块：空隙点强制切块，块数下限 = 空隙点数+1）
     - 步骤 3 归一化 → `r01_normalized/chunk_<k>.txt`
     - 步骤 3 处理（补标点）→ `r01_results/chunk_<k>.txt`
     - 步骤 4 处理（翻译 + 术语核对）→ `r02_results/chunk_<k>.txt`
     - 步骤 5 归一化（预分句 + ZH 机械化断句）→ `r03_normalized_1/chunk_<k>.txt`（EN 预分句 E 号）+ `r03_normalized_2/chunk_<k>.txt`（ZH r03 模板骨架：Z 句 + 子句段预填）
     - 步骤 5 处理（分句，5-1/5-2 二选一）→ **5-1 LLM 语义分句**（老，现状）：`task-split` 直接写；**5-2 脚本断句**（新，省 token）：`r03_matches/chunk_<k>.txt`（匹配文件，LLM 只做句子匹配）→ `build-r03` 机械填回——两路径产物 `r03_results/chunk_<k>.txt`（S 号块内从 1 连续编号；**回填输入 = 目录直读**，`parse_r03_dir` 按块序解析 + 全局重编号，零拼接）——`r03_plan.md` 仅审核/审计时 `join-r03` 按需生成
     - 步骤 6 处理（回填）→ `r04_draft.srt`（预览，止步 `_work/`）、`r03_anchored.jsonl`（锚定明细，JSONL 每行一整句：锚定状态 + 单元 cue 命中）
     - 步骤 7 处理（组装）→ `r04_bilingual.srt`（双语预览 en-zh）

> **产物格式/分隔符/标记约定（单一权威）**：各产物结构（r00–r04、r03_anchored.jsonl）见 [PRODUCT_FORMATS](../../../docs/PRODUCT_FORMATS.md)——处理前先查对应节，勿现查代码猜格式；块间分隔一律空行、手写标记仅限跨块句补全的 `【承接句】`/`【延伸句】`（`【强制断句】` 为空隙标记、非产物文本，经复核注入补标点先验知识）。
3. **阶段二½ 人工审核**（`redstone-review`）——输入 `r03` + `r04` → 用户确认（无新落盘）
4. **阶段三 数据源总结**（`redstone-finalize`）——`.github/experience/` 追加

**中断恢复路由**：检查 `_work/<视频名>/` 最完整产物，**从产出该产物的阶段/步骤开头继续**（假设该阶段异常中断、产物可能不完整）：

1. 无任何产物 → 从头开始（阶段〇）
2. 仅 `01_subtitle_asr_fixed.srt` → preprocess §1.1 开头（有 `_en_chunks/` + 部分 `_en_results/` → §1.1 步骤 2 补派缺失块后 `srt_join_parts.py` 合并）
3. 有 `02_terms.md` → preprocess §1.3 开头（§1.4 入库照做）
4. 有 `r00_gaps.md`/`r01_breaks.md`（断句骨架）→ 步骤 2 开头（从确定块大小 + 分块续）
5. 有 `reflow/chunks/`（01 分块骨架）→ 步骤 3 归一化（跑 `srt_reflow_normalize.py` → `r01_normalized/`）
6. 有 `reflow/r01_normalized/`（归一化输入）→ 步骤 3 逐块补标点续
7. 有 `reflow/r01_results/`（逐块中间产物）→ 步骤 3 校验（从补标点校验续）
8. 有 `reflow/r02_results/`（逐块中间产物）→ 步骤 4 第 1 步（从逐块翻译续）
9. 有 `reflow/r03_normalized_1/` + `reflow/r03_normalized_2/`（EN 预分句 + ZH r03 模板骨架）→ 步骤 5（归一化已完成，从 5-1 / 5-2 选择续）
9.5. 有 `reflow/r03_matches/`（匹配文件，5-2）→ 步骤 5-2 步骤 2（从 `build-r03` 机械填回续）
10. 有 `reflow/r03_results/`（逐块中间产物）→ 步骤 5-1 第 1 步（从分句续；5-2 产物亦可直接回填；回填直读 r03_results/，无需拼接）
11. 有 `r03_plan.md`（仅审核/审计产物，非回填输入）→ 不设独立恢复点，回填以 r03_results/ 为准
12. 有 `r04_draft.srt` → 步骤 6 开头（重新回填）

> 各阶段结束**立即落盘**（conventions「断点恢复」）；中间产物是工作底稿，**禁止自动删除**（AGENTS.md #6）。

## 依赖

| 话题 | 权威 Skill |
|------|-----------|
| 通用规则（环境/工作区/分块/门禁等） | `redstone-conventions` |
| 翻译前置（阶段〇/一） | `redstone-preprocess` |
| 人工审核（阶段二½）+ 输出门禁 | `redstone-review` |
| 数据源总结（阶段三） | `redstone-finalize` |
| 去翻译腔 | `humanizer-zh` |
| 断句/行宽/时间不重叠机制 | `segment-subtitles` |
| subagent 派发（派发配方/纪律母版/任务导航） | `subagent-dispatch` |

## 注意事项

### 通用规则

见 [redstone-conventions](../redstone-conventions/SKILL.md) + [AGENTS.md](../../../AGENTS.md)（项目原则）。

### 特有规则

- **输出门禁**：`_output/` 只收阶段二½ 用户确认后的正式稿（见 `redstone-review`）
- **定点修复（校验打回统一处置）**：硬违规先定点修正（`task-fix` 整批派发，见 [subagent-dispatch#定点修正](../subagent-dispatch/SKILL.md#定点修正surgical-fix校验打回先小规模修不整块重派)）；多轮尝试或违规严重、定点修不了才打回「处理」重跑（重跑前先 mv 清理已存在结果）；勿在主会话进行全量校对

## 固定工作流指令

本工作流四个阶段 + 一个人工审核循环。

---

### 阶段〇 / 阶段一：领域预判 + 术语补齐

按 [redstone-preprocess](../redstone-preprocess/SKILL.md) 原样执行（阶段〇 预判 / §1.1 扫描 → `01_subtitle_asr_fixed.srt` / §1.2 补齐 / §1.3 确认 → `02_terms.md` / §1.4 入库）。`--cue-exact` 校验保留（保护原轴骨架）。**阶段门禁：`01`/`02` 交用户确认后才进入阶段二，不得擅自跨阶段**（阶段间确认是本工作流的流程控制）。

> **实践建议**（补丁，机制设计不变）：阶段〇/一 分块（preprocess §1.1 第一次遍历 `_en_chunks/`）`--owned` 按 **≤300 cue** 封顶——实践得出；封顶只在取值时做，`context_estimate.py --no-amplification` 定 N 与分块机制不变

---

### 阶段二：语义回填

> 语义工作（合并补标点 / 翻译 / 分句对应 / 回填判断）由 Agent 承担；确定性时间运算由 `scripts/srt_reflow*.py` 承担（见各步骤）。

> **派发边界**：本阶段补标点/翻译/分句**一律派 subagent**（每任务按骨架块数派发），无需报告策略——见 [subagent-dispatch#派发边界](../subagent-dispatch/SKILL.md#派发边界哪些派-subagent--哪些主会话)。
> **执行型纪律与模型**：纪律母版 #0 内联执行型纪律；**派发入口 / 运行模型名不在 skill 硬编码**——见 [EDITOR_COMPAT#各编辑器派发 subagent 命令表](../../../docs/EDITOR_COMPAT.md)（模型名读 `configs/subagent_model.yaml`）。

> **行文结构**：本阶段各步骤按「1. 归一化 → 2. 处理 → 3. 校验」三段标题组织（无归一化环节的步骤标注「无」预留位）；步骤 1 空隙探测+硬性断句 / 步骤 2 定 N+分块 为前置步骤，与后续补标点、翻译、分句、回填、组装并列。

#### 步骤 1：空隙探测 + 硬性断句

##### 归一化

1. 无——直接使用 `01_subtitle_asr_fixed.srt` 字幕

##### 处理

1. **空隙探测（先验证 gap 准确性）**：`python scripts/srt_reflow_gap_scan.py <01> -o reflow/r00_gaps.md`——空隙点清单（长停顿 >5s / 剪辑跳转 >10s）即分块组边界依据；**已有 r00_gaps.md 则复用，勿重复探测**；探测结果人工确认后作为 `--gaps` 分块的空隙点集
  - **统一阈值参数（全流程引用同一值）**：
    - 长停顿 **5s** / 剪辑跳转 **10s**：
      - ① 步骤 2 `--gaps` 分块空隙组（空隙点 = 长停顿 >5s / 剪辑跳转 >10s）；
      - ② 步骤 6 单元内部空隙告警（`gap > 5s` / 跳转 `> 10s`）；
      - ③ 游离停顿词归属（大空隙 > 5s 前最后 cue **时间层归前句句尾**——r01 复核时文本归前句、r03 分句时仍独立成单元覆盖自身 cue，两层不冲突，见 task-split 规则 5）
2. **硬性断句输入**：`python scripts/srt_reflow_breaks.py <01> -o reflow/r01_breaks.md`——断句点清单（含 Agent 复核字段），供复核回填 + 补标点先验知识注入（`【强制断句】` 空隙标记，见 task-punctuate）

##### 校验

1. **Agent 复核断句点清单**（回填 r01_breaks.md）：每空隙点判定**性质**（剪辑跳转→断死 / 语义停顿→可松断）、**断句方式**（独立成句 / 分段 / 归前句句尾）、**游离停顿词归属**


#### 步骤 2：确定块大小 + 分块

分块机制见 [redstone-conventions#长视频分块](../redstone-conventions/SKILL.md#长视频分块全流程通用机制) + [PRODUCT_FORMATS#通用文本分块](../../../docs/PRODUCT_FORMATS.md)。后续步骤共用此步骤的块骨架，块数为 1 时即单块骨架。

输入： `01_subtitle_asr_fixed.srt` + `r00_gaps.md`（空隙点集）

##### 归一化

1. 无——直接使用 `01_subtitle_asr_fixed.srt` 字幕

##### 处理

1. **定容量**：`python scripts/context_estimate.py <01>`
  - 参数默认读 `configs/context_window.json`、CLI 可覆盖
  - 输出：估算 token / 单块容量上限（min 统一、已含放大）/ 每 cue 平均字符 / `--owned` 建议值（= 单块容量上限 × 1.5 ÷ 每 cue 平均字符）
  - **实践建议**（补丁，机制设计不变）：`--owned` 取值按 **≤200 cue** 封顶——实践发现单块 >200 cue 时分句 subagent 处理不了（no-think 输出超限中断，只能拆半重派）；封顶只在取值时做，`context_estimate.py` 反推公式与分块机制不变
2. **分块**：`python scripts/text_chunk.py <01.srt> --type srt --gaps --owned <每块cue数> --ctx <衔接cue数> --out reflow/chunks/`
  - 块 = 「空隙组-片」，
  - `--owned` 填上一步建议值
  - `--ctx 10`（每侧衔接 cue 数，约覆盖前块末尾 1–2 句）
  - **空隙点强制切块（语义硬边界，与容量无关）**：`--gaps` 把 01 按空隙点切成「空隙组」，**每个空隙组至少一块**——块数下限 = 空隙点数 + 1；仅 01 无空隙点才 1 块
  - **组内按 `--owned` 拆片（容量控制）**：空隙组 cue 数 > `--owned` 时组内再拆多片；≤ `--owned` 则每组恰一块——**组内不分片 ≠ 不分块**（空隙点仍强制切块）

##### 校验

1. 无——分块正确性由后续补标点/校验兜底

#### 步骤 3：合并全文 + 补充标点

##### 归一化

1. **chunks 块文本归一化（脚本一次性全目录）**：`python scripts/srt_reflow_normalize.py reflow/chunks/ -o reflow/r01_normalized/`
  - 每块 `## BEFORE`/`## OWNED`/`## AFTER` 分区内 cue 文本**预先合并**为连续文本（剔除 `[Music]` 等纯标记 cue），折行 ≤1000 字符/行（英文不拆词、中文按字符）；**对整个目录一次跑完**（每块独立合并，命令只运行一次）
  - 产物：`reflow/r01_normalized/chunk_<k>.txt`（保留块头 + 分区结构；纯标记块输出空块注释）——**仅作补标点输入，非校验基准**（校验仍读 `chunks/` cue 区间 + `r01_results/`）

##### 处理

1. **补标点（逐块）**：每块派一个 subagent，**完整 prompt 由渲染脚本生成**（见 [subagent-dispatch#派发配方](../subagent-dispatch/SKILL.md#派发配方)），派发时按「派发引用 prompt」只给引用路径
  - 渲染命令：`python scripts/render_subagent_prompt.py task-punctuate --video <工作目录> [--chunk <k> | --all]`（先验知识自动注入空隙断句标记 + 术语表；派发前数据文件只验证、不读取，见 subagent-dispatch「派发前主 Agent 准备」）
  - 输入：`reflow/r01_normalized/chunk_<k>.txt`（已归一化：OWNED 为合并连续文本），**数据文件引用**（渲染脚本注入 `## 本块数据`）——**行尾换行为显示性折行、非语义分行，subagent 按整段解析忽略**
  - 产物：`reflow/r01_results/chunk_<k>.txt`，各块独立文件
    - 整段文字，格式/折行见 [PRODUCT_FORMATS](../../../docs/PRODUCT_FORMATS.md) 与任务文件，**中间不拼全文**；
    - 块首/块尾跨块句已按 [task-punctuate#规则 4](task-punctuate.md) 补全并标记——相邻块对同一跨块句都补全，待「校验」阶段衔接归位
    - 每块独立处理，**不交给 subagent 运行全局校验**（校验见「3. 校验」段，主会话统一跑
    - subagent 自查只限本块格式完整 + 片边界跨块句补全标记 `【承接句】`/`【延伸句】`）

##### 校验

**任务**：主会话统一跑，所有块 subagent 全部完成后一次执行；各校验项逐条跑，问题统一走「定点修复」。

**告警定位约定**（reflow 校验脚本通用）：问题项统一带「文件:行号 + 行上下文」（如 `chunk_008.txt:行28`），**主会话只读此清单作派发素材、不得**按行号自行 read_file 定位核对/编辑——定点修复一律下放 B 档 `task-fix`（见 [subagent-dispatch#定点修正](../subagent-dispatch/SKILL.md#定点修正surgical-fix校验打回先小规模修不整块重派)，A 档已废弃）；通过项只汇总计数不逐项（`--verbose` 展开）。

1. **硬性校验**（任务：逐空隙点查句末标点 `.?!`）
  - 脚本：`python scripts/srt_reflow_check_breaks.py <01> reflow/r01_results/ --chunks reflow/chunks/ --gaps reflow/r00_gaps.md`
  - 处理方式：复用 r00_gaps 已验证空隙点；脚本先剥离跨块句标记 `【承接句】`/`【延伸句】` 再判，避免标记补全文本干扰空隙断句；剥离衔接句后无文本的块（纯标记/空块）对应空隙跳过校验（未定位提示人工核对），**不计打回**
  - 特例：空隙断句缺失 → 定点修复（B 档 `task-fix` 在空隙点补断句标点）；语义停顿可作受控例外放行（须 r03 不跨空隙成单元）
2. **措辞校验 + 跨块句衔接**（任务：逐块词序列与对应 01 cue 段一致）
  - 脚本：`python scripts/srt_reflow_check_words.py <01> reflow/r01_results/ --chunks reflow/chunks/`——脚本剥离 `【承接句】`/`【延伸句】` 标记后比对
  - 特例：含跨块句标记的块缺词 → ⚠️ 提示、归位时确认，**不计打回**；无标记块缺词/多词 → 定点修复（按校验输出 `01=[词] r01=[词]` 改回 01 措辞）
  - 跨块句衔接校验：相邻块 `【延伸句】` ⇔ `【承接句】` 标记互补、两半文本拼接 = 完整句（脚本/人工抽查）
3. **补标点质量校验（逗号堆砌/超长句/断句稀疏/疑似可断句）**（任务：逐块按 `.?!` 分句，检测补标点质量）
  - 脚本：`python scripts/srt_reflow_check_sentence_len.py reflow/r01_results/`——**分级告警**：
    - **硬（打回）**：单句逗号数 >10（逗号连接未断句，实测 E5/E22 的 11 逗号为堆砌）/ 单句 >600 字符（绝对超长）/ 块内句均 >350（断句稀疏，整块仅 1–2 个句号）
    - **软（提示复核，不阻断）**：单句逗号 ≥8 且字符 ≥250（疑似可断句——中等超长、语义断点用了逗号，如 E15「there we go, the next thing...」）
  - 处理方式：硬命中 → 定点修复（B 档 `task-fix` 在语义断点补句末标点 `?!.`）；软命中 → 主会话/用户复核确认语义断点后**并入 B 档 `task-fix` 清单一并修**（主会话不自行定点编辑）；块内句数正常、句均正常（真实长句 ~500 字符内）→ 放行
4. **衔接归位**（任务：相邻块跨块句重复——块 k `【延伸句】` ≡ 块 k+1 `【承接句】`；时机：校验通过后、进入步骤 4 前）
  - 处理方式：脚本取各块**头尾句**（按标点分句取首/末句；`r01_normalized/` 已折行 1000 字符/行，直接取首末句亦可），交 agent 综合吸收——**只在一侧留无标记完整句，另一侧直接不留该句文本**（删去）
  - **单边标记兜底**：若某块标了 `【延伸句】`/`【承接句】` 而无相邻块配对（对侧 subagent 漏标/漏补全）——**不能静默放过**：该句是真实句子，回填 `01_subtitle_asr_fixed.srt` cue 拼接原文，在本块留无标记完整句、删标记，并核对相邻块是否缺句（uVOFckoMdIU chunk_002 S94 事故：chunk_003 漏标 `【承接句】` 且删了跨块句前半，`【延伸句】` 孤立残留一路到 r04）
  - 结果：归位后每块句子完整、无跨块重复，供步骤 4 整段翻译；**归位后不再跑块级措辞校验**（跨块句已移/删，全局词守恒由 r04 审核兜底）


#### 步骤 4：翻译 + 术语核对

##### 归一化

1. 翻译前将英文输入归一化成每 1000 字符左右一行、按词断开的文本——由 `scripts/srt_reflow_common.py` 的 `auto_wrap_file`（MAX_LINE=1000：英文词边界不拆词、中文按字符，显示性换行非语义分行）就地折行；超长单行在校验脚本（`check_words` 等）中自动触发，亦可 `text_merge --wrap 1000` 主动归一化

##### 处理

1. **派发**：每块派一个 subagent，**完整 prompt 由渲染脚本生成**（见 [subagent-dispatch#派发配方](../subagent-dispatch/SKILL.md#派发配方)），派发时按「派发引用 prompt」只给引用路径
  - 渲染命令：`python scripts/render_subagent_prompt.py task-translate --video <工作目录> [--chunk <k> | --all] [--prior-file <前文摘要>]`（先验知识自动注入 humanizer 注入版 + 术语表；前文摘要用 `--prior-file` 追加）
  - **输入**：`r01_results/chunk_<k>.txt` + 前后块 CONTEXT 衔接（`--ctx 10`，每侧 10 cue，覆盖前块末尾 1–2 句；语义段是步骤 3/4/6 统一分块单位，见 conventions）——**数据文件引用**（渲染脚本注入 `## 本块数据`）
  - **先验知识注入**（渲染脚本自动注入 `## 先验知识`）：
    - **humanizer 注入版**：`humanizer-inject.md`（~50 行），**勿注入 humanizer-zh 354 行全量版**（仅主会话/审核深读）——禁止只写"去口语化/去翻译腔"笼统要求（subagent 看不到主会话加载的规则）
    - **前文摘要注入（可选）**：需跨块长距离语义照应时，先对前文做摘要（派 `task-summary` → `reflow/summary.md`），用 `--prior-file` 追加注入本块（见 [task-summary](task-summary.md)）
  - **产物**：`reflow/r02_results/chunk_<k>.txt`，各块独立文件（整段中文，格式/折行见 [PRODUCT_FORMATS](../../../docs/PRODUCT_FORMATS.md) 与任务文件）——**中间不拼全文**
2. **注意事项**：
  - **不交给 subagent 运行全局校验**（`check-r03` 块级模式验全部块，见步骤 5 校验段，主会话统一跑）
  - **翻译纪律与去翻译腔**：见 `task-translate.md`（翻译纪律 + humanizer 注入版 `humanizer-inject.md`）
  - **r02 定稿即自然译文**：r03 忠实铁律只许「切」不许「译」，翻译腔若拖到 r04 后只能回 r02 返工（阶段二½ 审核时主会话对照检查）

##### 校验

1. **术语全量核对**：`python scripts/srt_reflow_check_terms.py <01> <02_terms.md> reflow/r02_results/ --chunks reflow/chunks/`——逐条遍历 02_terms.md，01 定位原文出现块 → 该块 r02 译文须含确认译名（变体容错/长术语覆盖逻辑见脚本 docstring）
  - 输出：✅ 命中（默认折叠计数，`--verbose` 展开）/ ⚠️ 译文未见确认译名（带 r02 块文件行号 + 上下文 + 01 原句 + 02_terms 行号；Agent 复核：意译 / 漏译 / 漂移 / 命令·参数·专名保留原文）/ ℹ️ 01 未命中（带 02_terms 行号；查 ASR 修正列或措辞变体）
  - 退出码 1 = 有未命中项，**Agent 复核后才可放行**；漂移**回写** `reflow/r02_results/` 对应块（各块独立文件）
2. **跨步骤兜底**：步骤 5 check-r03 ④ ZH 忠实（拦截译文改写）→ 阶段二½ 人工对照检查


#### 步骤 5：分句 + 语义对应（两条平行路径，二选一）

> 两路径产物契约一致（`r03_results/chunk_<k>.txt`，消费端 check-r03 / 回填无感），差异在断句方式与 token 消耗。**步骤 5-1（老，现状）在前**、**步骤 5-2（新，省 token）在后**——两路径各自独立「归一化 → 处理 → 校验」三段；5-2 的归一化/校验与 5-1 相同，**只引用前文**（见步骤 5-1 对应段），处理独立展开。

##### 步骤 5-1：LLM 语义分句（老，现状，精细）

> 语义对应/句内再切更精细，token 消耗大（~35k/块，token 优化实测）。

###### 归一化

1. **预分句 + ZH 机械化断句（脚本，方案 4——断句基线机械化）**：`python scripts/srt_reflow_presplit.py reflow/r01_results/ reflow/r02_results/ -o reflow/`
  - EN 按句末标点 `.?!`（`r01_results/`，衔接归位后）预分句标号 `E1..En` → `reflow/r03_normalized_1/chunk_<k>.txt`
  - ZH 按句号 `。！？`（`r02_results/` 译文原稿，脚本读取不受行宽限制）预分句标号 `Z1..Zm` + **句内按标点切候选段 + 贪心拼合 [15,22]（硬 ≤26）** → `reflow/r03_normalized_2/chunk_<k>.txt`（**r03 模板骨架**：每 Z 句一组 `## S?_Z<n>`，ZH 整句原文 + 子句段预填、关系预填 1:1/1:n、EN 待填——分句 agent 填空后即 r03_results）
  - **不形成中英对照**（EN/ZH 各自编号；`S?_Z<n>` 默认按序提示对应 `E<n>`，启发式须核对）；**忠实铁律由结构保证**（段只在标点处切、不增删改——段拼接 == Z 原文 == r02）；**长短/宽度/断句类型机械化**，agent 不再自行判长短
  - **多语言通用**：切分标点（`--punct-levels` 有序层级，默认逗号族>顿号>破折号，超宽才降级）、句长区间（`--soft-min/--soft-max/--hard-max/--min-unit`）全参数化，默认 CJK；宽度复用 `srt_reflow_common.text_width`（Unicode 块通用）
  - 一次性全目录跑完（r02 折行副本不再需要——预分句输出已逐句折行，脚本直读 r02_results 原稿）

###### 处理

1. **派发**：每块派一个 subagent，**完整 prompt 由渲染脚本生成**（见 [subagent-dispatch#派发配方](../subagent-dispatch/SKILL.md#派发配方)），派发时按「派发引用 prompt」只给引用路径
  - 渲染命令：`python scripts/render_subagent_prompt.py task-split --video <工作目录> [--chunk <k> | --all] [--prior-file <块边界情况>]`（先验知识自动注入术语表；每块边界情况/空隙归属等主会话复核结论用 `--prior-file` 追加）
  - **输入（材料配对——分句语义对应是需全貌的跨切面决策）**：每块输入 = `r03_normalized_1/chunk_<k>.txt`（EN E 号预分句）+ `r03_normalized_2/chunk_<k>.txt`（ZH r03 模板骨架，见「归一化」）对照 + 前后块 CONTEXT（**数据文件引用**，渲染脚本注入 `## 本块数据`）
  - **分句/语义对应规则**：整句骨架（预分句 E 号确认）/ 模板填空（S 号·EN·关系·子单元 EN）/ 1:1·1:n·n:1 对应 / 忠实转写铁律 / 拆合标注 / 游离停顿词——见 `task-split.md`；r03 产物结构（`## S<n>` / EN·ZH·关系 / 子单元）见 [PRODUCT_FORMATS#r03_plan.md](../../../docs/PRODUCT_FORMATS.md)
  - **产物**：`r03_results/chunk_<k>.txt`（**S 号块内从 1 连续编号**，见 task-split 规则 6）→ **`r03_results/` 即回填输入**（步骤 6 目录直读，脚本自动全局重编号，**无需拼接**）；`r03_plan.md` 仅审核/审计时 `join-r03` 按需生成
  - **漏句留空**：处理不了的 Z 句（无法对应/超宽段切不动）在产物写 `> ⚠️ 未匹配 Z<n>：<文本>` 标记，**不静默丢弃**（check-r03 ④ ZH 忠实会抓缺句，配合留空标记精确定位）
2. **注意事项**：每块内保持整句/单元的语义完整性（不跨块拆句；空隙为硬边界，整句不跨空隙块）

###### 校验

**本步是回填前的写时预检，不可跳过**：`check-r03` 通过才进步骤 6（回填）——把"步骤 6 跑完才发现"提前到分句阶段拦截。

1. **r03 统一校验**：`python scripts/srt_reflow.py check-r03 reflow/r03_results/ <01> reflow/r02_results/ --chunks reflow/chunks/ [--cjk-speed 5] [--no-frag] [--no-mismatch] [--full-warnings]`——逐块六查（锚定缩到块内 cue 区间、ZH 忠实缩到块内 r02；主会话统一跑，勿交 subagent——与 subagent-dispatch 纪律母版 #9「不运行全局校验」同指一次运行）；**本校验即分句 subagent「不手算、不重抄」的执行兜底**——task-split 规则 2/4/7 只要求凭目测切分、直接写盘，行宽 ③ / 拼接互斥 ② / ZH 忠实 ④ 全在此统一裁决
  - ① **整句锚定唯一性**（缩到块内 cue 区间）
  - ② **拆句子单元互斥拼接 == 整句（EN）**
  - ③ **译文单元行宽 ≤26**（软 22 / 硬 26）
  - ④ **ZH 忠实性（两层）**：r03 整句 ZH 与 r02 定稿字符多集一致（净增删字即违规，允许口语词重排）+ 拆句子单元 ZH 拼接 == 整句 ZH（拦截译文改写，含整句/子单元两层）
  - ⑤ **碎片预检（预警，不阻断）**：1:n 整句按阅读速度粗估子单元时长，<1s 的提示 Agent 在 r03 合并/调整切分点（长句不碎）
  - ⑥ **中英失配预估（预警，不阻断）**：1:n 整句按单元级 cue 锚定 + 共享 cue 切分预估各单元实际时长，文本量大的中文单元只拿到很短英文 cue（倒装/中英时长差、读不完）时提示 Agent 调整切分点或依赖回填阅读插值
  - ⑦ **括号/引号配对（预警，不阻断）**：单元内开闭括号数量不等 = 括号被拆在单元中间；引号不成对 = 引号归属漂移（单元开头多出/丢失 `"`）——提示合并单元或调整标点归属
  - ⑧ **格式标记残留（跨块句硬违规 / 占位预警）**：r03 扫描 `【承接句】`/`【延伸句】` 残留 → **硬违规打回**（跨块句标记应在衔接归位/翻译/预分句时消除，回填会把标记原样写进交付 SRT——uVOFckoMdIU chunk_002 S94 事故）；`[待审核: …]` 占位残留 → **存疑预警**（提示回 r02 定稿或人工确认，防止占位流进交付）
  - **处置（批量告警闭环，锁死 ≤3 轮）**：
    1. **一次校验 → 全部错误一次给**：check-r03 全块跑 → 收集**全部**硬违规（①②③④⑧）错误清单（自带 `文件:行号 + 行上下文`）
    2. **一次 surgical-fix**：全部错误清单**一次派发** `task-fix`（B 档批量，见 subagent-dispatch「定点修正」）——不逐条派发
    3. **一次复验**：task-fix 后重跑 check-r03；残留增量 → 第二轮 B 档只派**增量残留清单**（逐轮收敛）；连续多轮仍失败 → 升级 C 档整块重派
    4. **严禁全量重写**：禁止整块打回全文重写（token 反超现状，见 token 优化方案「五」）
    5. 存疑预警（⑤⑥⑦ + ⑧ 占位）：Agent 智能判断——⑤⑥ 独立开关 `--no-frag` / `--no-mismatch`（预警过多、效果不佳时可单独关一项降噪）；**默认折叠**（统计 + 前 5 条样例，其余省略），分句阶段需全量看预警时加 `--full-warnings`

##### 步骤 5-2：脚本断句（新，省 token，先试）——LLM 只做句子匹配，断句/填回全机械

> 分句阶段的 LLM 思考链 + 写盘 token **归零**；产物 = 复用模板子句段（机械断句）+ 按序近似中英对应，语义对齐/游离词/超宽段等由 **漏句留空标记**（`> ⚠️`）+ 人工审核兜底。适合先跑一版粗分句看节奏，审核不满意再走 5-1（老路径）。

###### 归一化

（同步骤 5-1 归一化，见上——`r03_normalized_1/` + `r03_normalized_2/` 已生成则直接复用，不重复跑）

###### 处理

1. **句子匹配（每块派一个 subagent）**：`python scripts/render_subagent_prompt.py task-match --video <工作目录> [--chunk <k> | --all]`（派发引用 prompt，见 [subagent-dispatch#派发配方](../subagent-dispatch/SKILL.md#派发配方)）
  - **输入**：`r03_normalized_1/chunk_<k>.txt`（EN E 号预分句）+ `r03_normalized_2/chunk_<k>.txt`（ZH Z 句模板骨架）对照（**数据文件引用**，渲染脚本注入 `## 本块数据`）
  - LLM **只输出匹配文件** `reflow/r03_matches/chunk_<k>.txt`（每行 `Z组 = E组`，如 `Z5+Z6+Z7+Z8 = E5`；**覆盖全部 Z/E 号各恰好一次**）——**不抄文本、不断句、不写 r03**（规则见 `task-match.md`；`r03_matches` 格式见 [PRODUCT_FORMATS#r03_matches](../../../docs/PRODUCT_FORMATS.md)）
  - **覆盖完整性是第一要务**：漏任何 Z/E 句都会在 r03 产物留空标记（脚本断句允许不完整，缺处人工核对或升级 5-1）
2. **机械断句填回（脚本，一次性全目录）**：`python scripts/srt_reflow_build_r03.py reflow/r03_matches/ reflow/r03_normalized_1/ reflow/r03_normalized_2/ -o reflow/r03_results/`
  - 子单元 = **复用模板骨架子句段**（presplit 机械断句结果，忠实/宽度由结构保证）；EN 整句 = 匹配 E 组按号拼接；子单元 EN = 按 ZH 子单元宽度比例机械切分（**互斥拼接 == 整句**，check-r03 ② 可过）
  - **漏句留空**：匹配未覆盖的 Z/E 句，产物写 `> ⚠️ 脚本断句·未匹配 Z<n>: <文本>`（**不静默消失**）；S 号块内连续、关系由子单元数定（1:1/1:n）

###### 校验

（同步骤 5-1 校验，见上——check-r03 对两路径产物统一裁决；5-2 由 build-r03 机械生成、互斥/行宽/忠实天然满足，产物 `> ⚠️ 脚本断句·未匹配` 标记 = 漏句，在此显形，需人工核对或升级 5-1）


#### 步骤 6：回填

##### 处理

**时间边界规则（reflow 特有）**：允许预测点（100ms 取整、不入原边界集）——与 translate（边界 ⊆ 原集合）不同；阅读插值触发的整句会引入必要预测点（倒装语义必须）。

1. **运行回填脚本（脚本任务，唯一动作）**：`python scripts/srt_reflow.py reflow reflow/r03_results/ <01> -o reflow/r04_draft.srt [--anchored reflow/r03_anchored.jsonl] [--snap-ms 300] [--cjk-speed 5]`
  - 输入：r03 传 **`r03_results/` 目录**（或 r03_plan.md，兼容）；目录模式按块序解析 + **S 号全局重编号**，无需先拼全文（LLM 不读全量、不撞窗口）
  - 处理方式（**脚本内一次性完成，主代理零读取**）：整句锚定 + 单元级时间分配 + 阅读插值——
    - **整句锚定**：脚本以 r03 整句文本在 01 全文唯一性搜索 → 锚定时间范围 `[start, end]`
    - **单元级 cue 锚定**：组内各单元文本在整句区间内顺序搜索，直接取自身 cue 区间；首末单元裁剪到整句边界；分割点**就近吸附真实 cue 边界**（非"空隙优先"吸附空隙后沿）
    - **共享 cue 中间断句**：真实 cue 内部需估算切分时按两侧字符比例（受控例外，人工抽查）
    - **字数比例降级兜底**：文本未命中时按字数比例 + 就近吸附；仍无边界则 **100ms 取整预测点**（不入原边界集）
    - **阅读感知插值（倒装/中英时长差）**：单元 cue 锚定后若任一单元「时长 <1s（长句碎片）」或「显著失配（< 阅读所需×0.7 且失配 ≥300ms）」——触发该整句按中文阅读速度（`--cjk-speed 5`）在整句区间内重分配并就近吸附真实 cue 边界（无则 100ms 预测点）；**不机械匹配英文 cue**（倒装语序下英文 cue 长短与中文阅读量不匹配）
    - **锚定明细**：同步落盘 `r03_anchored.jsonl`（JSONL，每行一整句）——逐整句锚定状态（unique / non-unique / failed）、分配方式（`alloc`: cue/reading/ratio）、每单元 cue 命中情况（hit + 起止 cue 号）
  - 产物：`r04_draft.srt`（预览，止步 `_work/`）
2. **agent 复核（脚本运行后，按需，不读全量）**：主代理**不参与时间分配**（脚本已全自动完成，无需读 r03_results/ 或 01 全文）；只按需审查——
  - `r03_anchored.jsonl`：**按行 grep** 关注锚定状态（non-unique / failed）、分配方式（alloc）、单元命中（hit=false）——整读约 27k token，见 conventions「大 JSONL 按行 grep」
  - `r04_alerts.md` 告警处置 + `check-duration` 长句碎片复核（见下方「校验」段）

##### 校验

1. **告警**：输出 `r04_alerts.md`——
  - 时长分布（极短 <300ms / 超长 >15s 或 >2×中位时长，双向告警）
  - 🔪 长句碎片（单条字幕时长须 ≥1s；同一整句拆出的 <1s 单元 =「长句碎片」，**回报 Agent 裁决**：合并 / 调整 r03 切分点 / 接受）
  - ⏱️ 独立短句（<1s 语义自足，如「好吗。」）可接受、仅复核
  - 📖 阅读插值（触发整句清单）
  - 单元内 gap > 5s、剪辑跳转 > 10s、预测点清单、行宽 > 22
2. **动作规则**：
  - 碎片 cue 合并容纳完整单元
  - 行宽 > 26 必切（软 22 预警；"标点+有 cue"处，无 cue 则预测点）
  - 时长超限不单独触发
  - [Music] 等非语音 cue 跳过
  - n:1 合句超长找"语义分割 + 有 cue"处切
3. **预览止步 `_work/`**，未经确认禁止写入 `_output/`；**回填严格脚本化**：只做断句 + 时间运算，禁止任何二次翻译/改写（译文在 r02 定稿后不改）；断句暴露译文问题 → 回 r02/r03 改，不在回填阶段擅自改写
4. **校验**：`srt_check_segments.py <输出> --orig <01>`（不启用 cue-exact，cue 数已变）——时间不重叠、语义完整、区间不逆
5. **长句碎片复核（必跑）**：`python scripts/srt_reflow.py check-duration reflow/r04_draft.srt reflow/r03_results/`——逐条长句碎片（<1s 拆句单元）**回报 Agent 裁决**（合并 / 调整 r03 切分点 / 接受）；插值已修复（≥1s）的碎片不在此列


#### 步骤 7：组装输出

##### 归一化——预留

1. 无——`r04_draft.srt` + `r03_results/` 已就绪，直接组装

##### 处理

1. **组装**：`python scripts/srt_reflow.py attach-en reflow/r04_draft.srt reflow/r03_results/ -o reflow/r04_bilingual.srt`（r03 目录或文件均可）
  - 中文行 = 对应译文单元；英文行 = r03 的**英文片段**（拆句子单元取各自互斥片段，**不得复用整句原文**）

##### 校验（行宽 + 输出门禁）

1. **行宽校验**：`srt_check_width.py <输出> --order en-zh`（残留超限仅预警）
2. **输出门禁**：**仅阶段二½ 用户确认后**输出到 `_output/<文件名>.reflow.srt`——`_output/` 是正式交付目录，未确认前禁止写入
3. **双语观感差** → 默认改 `zh-only`

---

### 阶段二½：人工审核循环

按 [redstone-review](../redstone-review/SKILL.md) 执行（循环机制 + 输出门禁）。**审核对象：回填方案 + 最终 SRT**（r03 = `r03_results/` 目录直读，或 `join-r03` 生成的 `r03_plan.md` 完整稿 + `r04_draft.srt`），重点核对语义对应是否判对（拆/合关系、切分位置）。**审核中发现 AI 味 / 翻译腔 → 回 r02 改整句、r03 同步**（受忠实铁律约束，不得在 r04 单侧改写），红石术语译名不受影响。

### 阶段三：数据源效果总结

按 [redstone-finalize](../redstone-finalize/SKILL.md) 原样执行（coverage_log 流水 + source_experience 经验提炼）。
