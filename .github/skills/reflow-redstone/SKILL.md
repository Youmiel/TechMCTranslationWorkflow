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

### 中间产物与断点恢复（按产物路由）

**全流程各阶段（子 skill）的输入与产物**：

1. **阶段〇/一 领域预判与术语补齐**（`redstone-preprocess`）——输入 `_input/` 原始字幕 → 产物 `<工作目录>/01_subtitle_asr_fixed.srt`、`<工作目录>/02_terms.md`
2. **阶段二 语义回填**（本工作流，产物在 `<工作目录>/reflow/`）
   - 输入：`01` + `02`
   - **`context_estimate.py` 只定 `--owned`（每块 cue 数）；执行一律 subagent**（块数由空隙组 × 组内分片决定，见 conventions「长视频分块」）。产物统一块级，按序：
     - 步骤 1 前置 → `r00_gaps.md`、`r01_breaks.md`；分块骨架 → `chunks/`（从 01 `--gaps` 分块：空隙点强制切块，块数下限 = 空隙点数+1）
     - 步骤 1 补标点 → `r01_results/chunk_<k>.txt`（每块独立）
     - 步骤 2/3 翻译 + 术语抽查 → `r02_results/chunk_<k>.txt`（每块独立）
     - 步骤 4 分句 → `r03_results/chunk_<k>.txt`（S 号块内从 1 连续编号）——**回填输入 = 目录直读**（步骤 5 `parse_r03_dir` 按块序解析 + 全局重编号，零拼接）；`r03_plan.md` 仅审核/审计时 `join-r03` 按需生成
     - 步骤 5/6 回填 + 组装 → `r04_draft.srt`（预览，止步 `_work/`）、`r03_anchored.jsonl`（锚定明细，JSONL 每行一整句：锚定状态 + 单元 cue 命中）

> **产物格式/分隔符/标记约定（单一权威）**：各产物结构（r00–r04、r03_anchored.jsonl）见 [PRODUCT_FORMATS](../../../docs/PRODUCT_FORMATS.md)——处理前先查对应节，勿现查代码猜格式；块间分隔一律空行、标记文本仅限脚本生成的 `【强制断句】`。
3. **阶段二½ 人工审核**（`redstone-review`）——输入 `r03` + `r04` → 用户确认（无新落盘）
4. **阶段三 数据源总结**（`redstone-finalize`）——`.github/experience/` 追加

**中断恢复路由**：检查 `_work/<视频名>/` 最完整产物，**从产出该产物的阶段/步骤开头继续**（假设该阶段异常中断、产物可能不完整）：

1. 无任何产物 → 从头开始（阶段〇）
2. 仅 `01_subtitle_asr_fixed.srt` → preprocess §1.1 开头
3. 有 `02_terms.md` → preprocess §1.3 开头（§1.4 入库照做）
4. 有 `reflow/chunks/`（01 分块骨架）→ 步骤 1 第 6 步（从逐块补标点续）
5. 有 `reflow/r01_results/`（逐块中间产物）→ 步骤 1 校验（从补标点校验续）
6. 有 `reflow/r02_results/`（逐块中间产物）→ 步骤 2 第 1 步（从逐块翻译续）
7. 有 `reflow/r03_results/`（逐块中间产物）→ 步骤 4 第 1 步（从分句续；回填直读 r03_results/，无需拼接）
8. 有 `r03_plan.md`（仅审核/审计产物，非回填输入）→ 不设独立恢复点，回填以 r03_results/ 为准
9. 有 `r04_draft.srt` → 步骤 5 开头（重新回填）

> 各阶段结束**立即落盘**（conventions「断点恢复」）；中间产物是工作底稿，**禁止自动删除**（AGENTS.md #6）。

## 依赖（扩展 Skill 地图）

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

### 特有规则（空隙与阈值约定，gap 判定统一参数）

- **长停顿阈值 5s**：三处引用同一值——① 步骤 2 极长间隔分语义段；② 步骤 5 单元内部空隙告警；③ 游离停顿词归属（大空隙 > 5s 前最后 cue **时间层归前句句尾**——r01 复核时文本归前句、r03 分句时仍独立成单元覆盖自身 cue，两层不冲突，见 task-split 规则 5）
- **剪辑跳转阈值 10s**：相邻单元边界间隔 > 10s 视为剪辑跳转点，输出清单人工确认
- **超长单元阈值 15s 或 > 2×中位时长**（时长分布报告双向告警）
- **单句时长 ≥ 1s（长句碎片）**：单条字幕时长通常不能短于一秒；同一整句拆出的 <1s 单元 =「长句碎片」，脚本检测（`r04_alerts.md` 的 🔪 与 `check-duration`）**回报 Agent 裁决**（合并 / 调整 r03 切分点 / 接受）；独立短句（语义自足，如「好吗。」）可接受、仅复核
- **中文阅读速度 5 字/秒（阅读插值）**：倒装语序 / 中英时长差异大时**不能仅匹配英文 cue**——`reflow --cjk-speed 5` 按中文阅读所需时长比例在整句区间内重分配（切分点就近吸附真实 cue 边界，无则 100ms 预测点）；触发条件 = 长句碎片（<1s）或显著失配（< 阅读所需×0.7 且失配 ≥300ms）
- **时间边界规则**：允许预测点（100ms 取整、不入原边界集）——与 translate（边界 ⊆ 原集合）不同；阅读插值触发的整句会引入必要预测点（倒装语义必须，见步骤 5）
- **回填严格脚本化**：只做断句 + 时间运算，禁止任何二次翻译/改写（译文在 r02 定稿后不改）；断句暴露译文问题 → 回 r02/r03 改，不在回填阶段擅自改写
- **输出门禁**：`_output/` 只收阶段二½ 用户确认后的正式稿（见 `redstone-review`）

## 固定工作流指令

本工作流四个阶段 + 一个人工审核循环。

---

### 阶段〇 / 阶段一：领域预判 + 术语补齐（复用）

按 [redstone-preprocess](../redstone-preprocess/SKILL.md) 原样执行（阶段〇 预判 / §1.1 扫描 → `01_subtitle_asr_fixed.srt` / §1.2 补齐 / §1.3 确认 → `02_terms.md` / §1.4 入库）。`--cue-exact` 校验保留（保护原轴骨架）。**阶段门禁：`01`/`02` 交用户确认后才进入阶段二，不得擅自跨阶段**（阶段间确认是本工作流的流程控制）。

---

### 阶段二：语义回填（新核心流程）

> 语义工作（合并补标点 / 翻译 / 分句对应 / 回填判断）由 Agent 承担；确定性时间运算由 `scripts/srt_reflow*.py` 承担（见各步骤）。

> **派发边界**：本阶段补标点/翻译/分句**一律派 subagent**（每任务按骨架块数派发），无需报告策略——见 [subagent-dispatch#派发边界](../subagent-dispatch/SKILL.md#派发边界哪些派-subagent--哪些主会话)。**派发载体 = `reflow-worker` 自定义 agent**（见 [subagent-dispatch#派发载体](../subagent-dispatch/SKILL.md#派发载体自定义-agent)）。

#### 步骤 1：合并全文 + 补充标点（语义；硬性断句脚本驱动）

> 补标点任务文件 = `reflow-redstone/task-punctuate`；`--owned` 定容量见步骤 1b；分块机制见 [redstone-conventions#长视频分块](../redstone-conventions/SKILL.md#长视频分块全流程通用机制) + [PRODUCT_FORMATS#通用文本分块](../../../docs/PRODUCT_FORMATS.md)。

##### 1a 前置（共用）

1. **空隙探测（先验证 gap 准确性）**：`python scripts/srt_reflow_gap_scan.py <01> -o reflow/r00_gaps.md`——空隙点清单（长停顿 >5s / 剪辑跳转 >10s）即分块组边界依据；**已有 r00_gaps.md 则复用，勿重复探测**；探测结果人工确认后作为 `--gaps` 分块的空隙点集
2. **硬性断句输入**：`python scripts/srt_reflow_breaks.py <01> -o reflow/r01_breaks.md`——断句点清单（含 Agent 复核字段）+ 注入【强制断句】标记的补标点输入文本
3. **Agent 复核断句点清单**（回填 r01_breaks.md）：每空隙点判定**性质**（剪辑跳转→断死 / 语义停顿→可松断）、**断句方式**（独立成句 / 分段 / 归前句句尾）、**游离停顿词归属**

##### 1b 定 N + 分块

4. **定容量（`context_estimate.py`）**：`python scripts/context_estimate.py <01>`（参数默认读 `configs/context_window.json`、CLI 可覆盖）——**预测阈值，使用放大倍数参数**（amplification≈5 断句放大）：**单块输入上限 = min(窗口×split_ratio, max_output×output_ratio÷amplification)**；材料 ≤ 单块输入上限 → 不分片；超 → 按 `--owned` 分片（反推见第 5 点）。执行一律 subagent
5. **分块（一律跑，产物契约统一）**：`python scripts/text_chunk.py <01.srt> --type srt --gaps --owned <每块cue数> --ctx <衔接cue数> --out reflow/chunks/`——chunks/ 恒存在
   - **空隙点强制切块（语义硬边界，与容量无关）**：`--gaps` 把 01 按空隙点切成「空隙组」（防跨空隙误译），**每个空隙组至少一块**——块数下限 = 空隙点数+1；仅 01 无空隙点才 1 块
   - **组内按 `--owned` 分片（容量控制）**：空隙组 cue 数 > `--owned` 时组内再拆多片；容量足够（`--owned` ≥ 最大空隙组 cue 数）→ 每组恰一块
   - **块 = 「空隙组-片」**：块标识「块G-片P」；`--owned` 按分句最重反推（见 conventions §4：单块材料 ≈ 阈值 token÷4；**反推公式 `--owned ≈ (单块输入上限÷4)×1.5÷每cue平均字符`**），拿不准用保守兜底默认 **50**
   - `--ctx 10`（每侧衔接 cue 数，约覆盖前块末尾 1–2 句）

##### 1c 派发补标点 subagent

6. **补标点（逐块）**：每块派一个 subagent——prompt 按 [subagent-dispatch#派发配方](../subagent-dispatch/SKILL.md#派发配方) 组装（任务文件 = `reflow-redstone/task-punctuate`），输入 = `reflow/chunks/chunk_<k>.txt`（**数据文件引用**），结果写 `reflow/r01_results/chunk_<k>.txt`（整段文字，格式/折行见 [PRODUCT_FORMATS](../../../docs/PRODUCT_FORMATS.md) 与任务文件）——**中间不拼全文**；每块独立处理，**不交给 subagent 运行全局校验**（校验见 1d，主会话统一跑；subagent 自查只限本块格式完整 + 片边界跨块句补全标记 `【承接句】`/`【延伸句】`）
7. 中间产物 `reflow/r01_results/`（各块独立文件；块首/块尾跨块句已按 [task-punctuate#规则 4](task-punctuate.md) 补全并标记——相邻块对同一跨块句都补全，待 1d 衔接归位）

##### 1d 校验 + 归位（主会话统一跑，所有块 subagent 全部完成后一次执行）

8. **硬性校验**：`python scripts/srt_reflow_check_breaks.py <01> reflow/r01_results/ --chunks reflow/chunks/ --gaps reflow/r00_gaps.md`——逐空隙点查句末标点 `.?!`（复用 r00_gaps 已验证空隙点；块数为 1 时即单块骨架；脚本先剥离跨块句标记 `【承接句】`/`【延伸句】` 再判，避免标记补全文本干扰空隙断句）；违规默认打回第 6 步重跑（**重跑前先 mv 清理已存在结果**，见 [subagent-dispatch#派发前主 Agent 准备](../subagent-dispatch/SKILL.md#派发前主-agent-准备)）；语义停顿可作受控例外放行，须 r03 不跨空隙成单元——勿交 subagent 逐块跑（避免重复全量校对）
9. **措辞校验 + 跨块句衔接**：`python scripts/srt_reflow_check_words.py <01> reflow/r01_results/ --chunks reflow/chunks/`——逐块词序列与对应 01 cue 段一致（脚本剥离 `【承接句】`/`【延伸句】` 标记后比对；含跨块句标记的块缺词 → ⚠️ 提示、归位时确认，**不计打回**；无标记块缺词/多词 → 打回）；**跨块句衔接校验**：相邻块 `【延伸句】` ⇔ `【承接句】` 标记互补、两半文本拼接 = 完整句（脚本/人工抽查）——同上，主会话统一跑
10. **衔接归位（校验通过后、进入步骤 2 前）**：相邻块跨块句重复（块 k `【延伸句】` ≡ 块 k+1 `【承接句】`）——脚本取各块**头尾句**（按标点分句取首/末句；整段归一化 1000 字符/行后取首末句亦可），交 agent 综合吸收：**只在一侧留无标记完整句，另一侧直接不留该句文本**（删去）；归位后每块句子完整、无跨块重复，供步骤 2 整段翻译；**归位后不再跑块级措辞校验**（跨块句已移/删，全局词守恒由 r04 审核兜底）

#### 步骤 2：翻译（整段输出、不分割、不编号；仅极长间隔处分段）

> 翻译任务文件 = `reflow-redstone/task-translate`（同一套 01 分块骨架）。先验知识注入（随 `## 先验知识`）：
> - **humanizer 注入版**：`humanizer-inject.md`（~50 行），**勿注入 humanizer-zh 354 行全量版**（仅主会话/审核深读）——见第 4 点去翻译腔内联，禁止只写"去口语化/去翻译腔"笼统要求（subagent 看不到主会话加载的规则）
> - **前文摘要注入（可选）**：需跨块长距离语义照应时，先对前文做摘要（派 `task-summary` → `reflow/summary.md`），随先验知识注入本块（见 [task-summary](task-summary.md)）

1. **派发**：每块派一个 subagent（每块输入 = `reflow/r01_results/chunk_<k>.txt` + 前后块 CONTEXT 衔接，`--ctx 10` 保证块间衔接连贯——**数据文件引用**），结果写 `reflow/r02_results/chunk_<k>.txt`（整段中文，格式/折行见 [PRODUCT_FORMATS](../../../docs/PRODUCT_FORMATS.md) 与任务文件）——**中间不拼全文**；**不交给 subagent 运行全局校验**（`check-r03` 块级模式验全部块，见步骤 4 第 8 步，主会话统一跑）
2. 中间产物 `reflow/r02_results/`（各块独立文件）
3. **翻译纪律与去翻译腔**：见 `task-translate.md`（翻译纪律 + humanizer 注入版 `humanizer-inject.md`）。**r02 定稿即自然译文**——r03 忠实铁律只许「切」不许「译」，翻译腔若拖到 r04 后只能回 r02 返工（阶段二½ 审核时主会话对照检查）
4. **语义段**：语义段是步骤 1/4/5 统一分块单位（见 conventions）；翻译时 CONTEXT 注入前块末尾 1–2 句衔接（`--ctx 10`，每侧 10 cue）

#### 步骤 3：术语抽查（防漂移）

用 `02_terms.md` 全量核对译文术语（<50 条成本可忽略）；漂移回写 `reflow/r02_results/` 对应块（各块独立文件）。

#### 步骤 4：分句 + 语义对应（翻译后）

> 分句任务文件 = `reflow-redstone/task-split`（同一套 01 分块骨架）。分句语义对应是**需全貌的跨切面决策**：
> - 每块输入 = `r01_results/chunk_<k>.txt` + `r02_results/chunk_<k>.txt` 对照 + 前后块 CONTEXT（**数据文件引用**）
> - 结果写 `r03_results/chunk_<k>.txt`（**S 号块内从 1 连续编号**，见 task-split 规则 6）→ **`r03_results/` 即回填输入**（步骤 5 目录直读，脚本自动全局重编号，**无需拼接**）；`r03_plan.md` 仅审核/审计时 `join-r03` 按需生成
> - 每块内保持整句/单元的语义完整性（不跨块拆句；空隙为硬边界，整句不跨空隙块）

分句/语义对应规则（原文分句 / 译文判长短切分 / 1:1·1:n·n:1 对应 / 忠实转写铁律 / 拆合标注 / 游离停顿词）见 `task-split.md`；r03 产物结构（`## S<n>` / EN·ZH·关系 / 子单元）见 [PRODUCT_FORMATS#r03_plan.md](../../../docs/PRODUCT_FORMATS.md)。
**r03 统一校验（写时即合规预检，必跑，通过才进步骤 5；与 subagent-dispatch 纪律母版 #9「不运行全局校验」同指一次运行，由主会话在所有块 subagent 全部完成后统一跑，勿交 subagent）**：`python scripts/srt_reflow.py check-r03 reflow/r03_results/ <01> reflow/r02_results/ --chunks reflow/chunks/ [--cjk-speed 5] [--no-frag] [--no-mismatch]`——逐块六查（锚定缩到块内 cue 区间、ZH 忠实缩到块内 r02）：
- ① **整句锚定唯一性**（缩到块内 cue 区间）
- ② **拆句子单元互斥拼接 == 整句（EN）**
- ③ **译文单元行宽 ≤26**（软 22 / 硬 26）
- ④ **ZH 忠实性（两层）**：r03 整句 ZH 与 r02 定稿字符多集一致（净增删字即违规，允许口语词重排）+ 拆句子单元 ZH 拼接 == 整句 ZH（拦截译文改写，含整句/子单元两层）
- ⑤ **碎片预检（预警，不阻断）**：1:n 整句按阅读速度粗估子单元时长，<1s 的提示 Agent 在 r03 合并/调整切分点（长句不碎）
- ⑥ **中英失配预估（预警，不阻断）**：1:n 整句按单元级 cue 锚定 + 共享 cue 切分预估各单元实际时长，文本量大的中文单元只拿到很短英文 cue（倒装/中英时长差、读不完）时提示 Agent 调整切分点或依赖回填阅读插值
- ⑦ **括号/引号配对（预警，不阻断）**：单元内开闭括号数量不等 = 括号被拆在单元中间；引号不成对 = 引号归属漂移（单元开头多出/丢失 `"`）——提示合并单元或调整标点归属
- 处置：硬违规（①②③④）打回改写后重跑；存疑预警（⑤⑥⑦）供 Agent 智能判断——⑤⑥ 独立开关 `--no-frag` / `--no-mismatch`（预警过多、效果不佳时可单独关一项降噪）
- 目的：把"步骤 5 跑完才发现"变成"写时即合规"（事后返工主因，见反馈）

#### 步骤 5：回填（合并 / 切分 / 预测 / 阅读插值；脚本化）

`python scripts/srt_reflow.py reflow reflow/r03_results/ <01> -o reflow/r04_draft.srt [--anchored reflow/r03_anchored.jsonl] [--snap-ms 300] [--cjk-speed 5]`——r03 传 **`r03_results/` 目录**（或 r03_plan.md，兼容）；目录模式按块序解析 + **S 号全局重编号**，无需先拼全文（LLM 不读全量、不撞窗口）

- **锚定明细**：同步落盘 `r03_anchored.jsonl`（JSONL，每行一整句）——
  - 逐整句锚定状态（unique / non-unique / failed）
  - 分配方式（`alloc`: cue/reading/ratio）
  - 每单元 cue 命中情况（hit + 起止 cue 号）
  - 可逐行审查：哪些句非唯一/失败、哪些单元走了字数兜底（hit=false）、哪些走了阅读插值（alloc=reading）

- **整句锚定**：脚本以 r03 整句文本在 01 全文唯一性搜索 → 锚定时间范围 `[start, end]`
- **单元级 cue 锚定**：组内各单元文本在整句区间内顺序搜索，直接取自身 cue 区间；首末单元裁剪到整句边界；分割点**就近吸附真实 cue 边界**（非"空隙优先"吸附空隙后沿）
- **共享 cue 中间断句**：真实 cue 内部需估算切分时按两侧字符比例（受控例外，人工抽查）
- **字数比例降级兜底**：文本未命中时按字数比例 + 就近吸附；仍无边界则 **100ms 取整预测点**（不入原边界集）
- **阅读感知插值（倒装/中英时长差）**：单元 cue 锚定后若任一单元「时长 <1s（长句碎片）」或「显著失配（< 阅读所需×0.7 且失配 ≥300ms）」——触发该整句按中文阅读速度（`--cjk-speed 5`）在整句区间内重分配并就近吸附真实 cue 边界（无则 100ms 预测点）；**不机械匹配英文 cue**（倒装语序下英文 cue 长短与中文阅读量不匹配）
- **告警**：输出 `r04_alerts.md`——
  - 时长分布（极短 <300ms / 超长 >15s 或 >2×中位）
  - 🔪 长句碎片（同一整句拆出的 <1s 单元，**回报 Agent 裁决**）
  - ⏱️ 独立短句（<1s 语义自足，仅复核）
  - 📖 阅读插值（触发整句清单）
  - 单元内 gap > 5s、剪辑跳转 > 10s、预测点清单、行宽 > 22
- **动作规则**：
  - 碎片 cue 合并容纳完整单元
  - 行宽 > 26 必切（软 22 预警；"标点+有 cue"处，无 cue 则预测点）
  - 时长超限不单独触发
  - [Music] 等非语音 cue 跳过
  - n:1 合句超长找"语义分割 + 有 cue"处切
- **预览止步 `_work/`**，未经确认禁止写入 `_output/`；严格脚本化禁二次翻译
- 校验：`srt_check_segments.py <输出> --orig <01>`（不启用 cue-exact，cue 数已变）——时间不重叠、语义完整、区间不逆
- **长句碎片复核（必跑）**：`python scripts/srt_reflow.py check-duration reflow/r04_draft.srt reflow/r03_results/`——逐条长句碎片（<1s 拆句单元）**回报 Agent 裁决**（合并 / 调整 r03 切分点 / 接受）；插值已修复（≥1s）的碎片不在此列

#### 步骤 6：组装输出（双语）

`python scripts/srt_reflow.py attach-en reflow/r04_draft.srt reflow/r03_results/ -o reflow/r04_bilingual.srt`（r03 目录或文件均可）

- 中文行 = 对应译文单元；英文行 = r03 的**英文片段**（拆句子单元取各自互斥片段，**不得复用整句原文**）
- 行宽校验 `srt_check_width.py <输出> --order en-zh`（残留超限仅预警）
- **仅阶段二½ 用户确认后**输出到 `_output/<文件名>.reflow.srt`——`_output/` 是正式交付目录，未确认前禁止写入
- 双语观感差 → 默认改 `zh-only`

---

### 阶段二½：人工审核循环（复用）

按 [redstone-review](../redstone-review/SKILL.md) 执行（循环机制 + 输出门禁）。**审核对象：回填方案 + 最终 SRT**（r03 = `r03_results/` 目录直读，或 `join-r03` 生成的 `r03_plan.md` 完整稿 + `r04_draft.srt`），重点核对语义对应是否判对（拆/合关系、切分位置）。**审核中发现 AI 味 / 翻译腔 → 回 r02 改整句、r03 同步**（受忠实铁律约束，不得在 r04 单侧改写），红石术语译名不受影响。

### 阶段三：数据源效果总结（复用）

按 [redstone-finalize](../redstone-finalize/SKILL.md) 原样执行（coverage_log 流水 + source_experience 经验提炼）。
