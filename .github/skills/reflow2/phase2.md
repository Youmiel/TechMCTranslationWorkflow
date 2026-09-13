# reflow2 阶段二执行细节（源头固化 + 继承回填）

> 本文件 = `reflow2` 阶段二（时间轴源头固化）的**完整执行指令**（步骤 1-7，各步按「归一化 → 处理 → 校验」三段组织）。**仅进入阶段二时读取**——阶段〇/一由 [SKILL.md](SKILL.md) 指挥；阶段产物链 / 中断恢复路由 / 输出门禁见 [SKILL.md](SKILL.md#中间产物与断点恢复)。

> **派发边界**：补标点 / 翻译 / 句子匹配**一律派 subagent**（任务 = `task-punctuate` / `task-translate` / `task-match` 的 **reflow2 版**，渲染时 `--skill reflow2`），无需报告策略——见 [subagent-dispatch#派发边界](../subagent-dispatch/SKILL.md#派发边界哪些派-subagent--哪些主会话)。
> **执行型纪律与模型**：纪律母版「一、执行型定位」内联执行型纪律；派发入口 / 运行模型名不在 skill 硬编码——见 [EDITOR_COMPAT#各编辑器派发 subagent 命令表](../../../docs/EDITOR_COMPAT.md)（模型名读 `configs/subagent_model.yaml`）。
>
> **需请求 Wiki 时**（翻译中遇未收录术语/机制不明/数值核对）：先 `refresh_cache.py --check-page "<页面名>"` 判定、过期则 `fetch_wiki.py --refresh "<页面名>"` 主动刷新后重读；需阅页面派 `wiki-researcher`（任务文件 `wiki-tools/task-wiki-query.md`）——见 [wiki-tools](../wiki-tools/SKILL.md)（权威）。

> **行文结构**：各步骤按「1. 归一化 → 2. 处理 → 3. 校验」三段标题组织（无归一化环节标注「无」）；步骤 1/2 为前置步骤。

---

## 阶段二：时间轴源头固化 + 继承回填

### 步骤 1：空隙探测 + 硬性断句

##### 归一化

1. 无——直接使用 `01_subtitle_asr_fixed.srt`

##### 处理

1. **空隙探测**：`python scripts/srt_reflow_gap_scan.py <01> -o reflow2/r00_gaps.md`——空隙点清单（长停顿 >5s / 剪辑跳转 >10s）即分块组边界依据；**已有 r00_gaps.md 则复用**；探测结果人工确认后作为 `--gaps` 分块空隙点集
2. **硬性断句**：`python scripts/srt_reflow_breaks.py <01> -o reflow2/r01_breaks.md`——断句点清单（含 Agent 复核字段），供补标点先验知识注入

##### 校验

1. **Agent 复核断句点清单**（回填 r01_breaks.md）：每空隙点判定性质（剪辑跳转→断死 / 语义停顿→可松断）、断句方式、游离停顿词归属

### 步骤 2：确定块大小 + 分块

分块机制见 [redstone-conventions#长视频分块](../redstone-conventions/SKILL.md#长视频分块全流程通用机制)。块数为 1 时即单块骨架。

##### 归一化

1. 无——直接使用 `01_subtitle_asr_fixed.srt`

##### 处理

1. **定容量**：`python scripts/context_estimate.py <01>`（默认读 `configs/context_window.json`；输出 `--owned` 建议值）
   - **实践建议**（机制不变）：`--owned` ≤200 cue 封顶（同 reflow-redstone 步骤 2 补丁）
2. **分块**：`python scripts/text_chunk.py <01.srt> --type srt --gaps --owned <每块cue数> --ctx 10 --out reflow2/chunks/`
   - 块 = 「空隙组-片」；空隙点强制切块（语义硬边界），组内按 `--owned` 拆片

##### 校验

1. 无——分块正确性由后续补标点/校验兜底

### 步骤 3：合并 cue + 补充标点

##### 归一化

1. **chunks 块文本归一化（脚本一次性全目录）**：`python scripts/srt_reflow_normalize.py reflow2/chunks/ -o reflow2/r01_normalized/`
   - 每块 `## BEFORE`/`## OWNED`/`## AFTER` 分区内 cue 文本**预先合并**为连续文本（剔除纯标记 cue），折行 ≤1000 字符/行
   - 产物：`reflow2/r01_normalized/chunk_<k>.txt`（**仅作补标点输入，非校验基准**）

##### 处理

1. **补标点（逐块派 subagent）**：渲染命令 `python scripts/render_subagent_prompt.py task-punctuate --skill reflow2 --video <工作目录> [--chunk <k> | --all]`
   - 派发引用 prompt（见 [subagent-dispatch#派发引用-prompt](../subagent-dispatch/SKILL.md#派发引用-prompt)）
   - 产物：`reflow2/r01_results/chunk_<k>.txt`：
     - 整段英文
     - 仅加标点不改措辞
     - 空隙强制断句
     - 跨块句补全标记 `【承接句】` / `【延伸句】`

##### 校验

**任务**：主会话统一跑，所有块完成后一次执行；问题走定点修复（B 档 `task-fix`，见 [subagent-dispatch#定点修正](../subagent-dispatch/SKILL.md#定点修正surgical-fix校验打回先小规模修不整块重派)）。

1. **硬性校验**（空隙点句末标点）：`python scripts/srt_reflow_check_breaks.py <01> reflow2/r01_results/ --chunks reflow2/chunks/ --gaps reflow2/r00_gaps.md`
2. **措辞校验**（词序列与 01 一致）：`python scripts/srt_reflow_check_words.py <01> reflow2/r01_results/ --chunks reflow2/chunks/`
3. **补标点质量校验**：`python scripts/srt_reflow_check_sentence_len.py reflow2/r01_results/`（硬：单句逗号 >10 / 单句 >600 / 句均 >350；软：≥8 逗号且 ≥250 字符）
4. **衔接归位**：跨块句重复（块 k `【延伸句】` ≡ 块 k+1 `【承接句】`）——只在一侧留无标记完整句，另一侧不留文本；单边标记兜底（回填 01 cue 拼接原文留完整句删标记）

> 步骤 3 校验是源头固化（步骤 4）的前置——E 句固化依赖 r01 与 01 措辞一致，措辞错误会造成 E 锚定失败。

### 步骤 4：源头固化（切 E 句 + 固化时间）

> 本步骤是 reflow2 核心（对应 reflow 的分句阶段，但**零 agent 分句**、零 r03 重型结构）。E 句 = 只读真值锚，下游继承。

##### 归一化

1. 无——直接使用 `reflow2/chunks/`（cue 结构 + 时间戳）+ `reflow2/r01_results/`（衔接归位后补标点整段）+ `01`

##### 处理

1. **源头固化（脚本，一次性全目录）**：`python scripts/srt_reflow2_etimeline.py reflow2/chunks/ reflow2/r01_results/ --srt <01> -o reflow2/en_timeline/`
   - 每块 r01 按 `.?!` 切 E 句（复用 `split_en`：缩写保护/省略号不切/跨块句标记剥离）
   - 每 E 句在块内 OWNED cue 区间锚定（与消费端 `io.build_full` 同构：norm 去空格、无缝拼接），相邻 E 句共享 cue 按字符占比切分
   - 产物：`reflow2/en_timeline/chunk_<k>.txt`（每行 `E<n>\t<start> --> <end>\t<c<cues>>\t<文本>`）——**纯脚本内部产物**（机器消费）

##### 校验

1. **锚定失败检测**：脚本退出码 1 = 有 E 句 MISS（补标点措辞与 01 不一致 / 标记残留）——定点修复 r01 后重跑
2. **抽查**：E 句固化时间应与原 cue 边界吻合（源头贴原轴，无预测点）

### 步骤 5：整段翻译 + 术语核对

##### 归一化

1. 翻译前将英文输入折行 ≤1000 字符/行（`auto_wrap_file` 就地折行，若 subagent 输出超长）

##### 处理

1. **翻译（逐块派 subagent）**：渲染命令 `python scripts/render_subagent_prompt.py task-translate --skill reflow2 --video <工作目录> [--chunk <k> | --all] [--prior-file <前文摘要>]`
   - 输入：`reflow2/r01_results/chunk_<k>.txt`（整段英文）——**翻译不吃时间**（输入无时间戳，E 固化走独立支线）
   - 先验知识自动注入 humanizer 注入版 + 术语表；前文摘要用 `--prior-file`
   - 产物：`reflow2/r02_results/chunk_<k>.txt`（整段中文，r02 定稿即自然译文）

##### 校验

1. **术语全量核对**：`python scripts/srt_check_terms.py <01> <02_terms.md> reflow2/r02_results/ --chunks reflow2/chunks/`（退出码 1 = 有未命中，复核后才放行；漂移回写）

### 步骤 6：切 Z 句 + 语义对齐

##### 归一化

1. **切 Z 句（脚本，一次性全目录）**：`python scripts/srt_reflow2_zsent.py reflow2/r02_results/ -o reflow2/zh_sentences/`
   - 每块 r02 按 `。！？…` 切 Z 句（复用 `split_zh`：括号配平保护/折行合并保留中英数字空格）
   - 产物：`reflow2/zh_sentences/chunk_<k>.txt`（每行 `Z<n> <整句文本>`）——Z 每次从 r02 重算（删句改句后重切重对齐）

##### 处理

1. **语义对齐（逐块派 subagent，纯号）**：渲染命令 `python scripts/render_subagent_prompt.py task-match --skill reflow2 --video <工作目录> [--chunk <k> | --all]`
   - 输入：`reflow2/en_timeline/chunk_<k>.txt`（E 句 + 固化时间）+ `reflow2/zh_sentences/chunk_<k>.txt`（Z 句列表）对照
   - LLM 只输出对齐文件 `reflow2/align/chunk_<k>.txt`（每行 `Z组 = E组`，如 `Z5+Z6 = E5`；覆盖全部 Z/E 各恰好一次）——不抄文本、不断句、不写时间
   - **覆盖完整性第一要务**：漏任何 Z/E 句 → 回填留空（问题清单），需补派

##### 校验

1. **对齐完整性（脚本）**：回填脚本（步骤 7）会报告未对齐的 Z/E——发现漏句 → 定点补派 task-match（B 档，重派缺失块）或人工补行

### 步骤 7：继承回填（生成 r04）

##### 归一化

1. 无——`zh_sentences/` + `align/` + `en_timeline/` + `01` 已就绪

##### 处理

1. **继承 + 回填（脚本，唯一动作）**：`python scripts/srt_reflow2_backfill.py reflow2/zh_sentences/ reflow2/align/ reflow2/en_timeline/ -o reflow2/r04_draft.srt --alert reflow2/r04_alerts.md`
   - 处理方式（**脚本内一次性完成，主代理零读取、不参与时间分配**）：
     - **继承**：每 Z 组对应 E 组，时间 = E 组覆盖范围 [首 E.start, 末 E.end]（E 固化时间已含共享 cue 切分，继承天然零重叠）
     - **拆子段**：Z 句超宽（>硬 26，视觉宽度）→ 按中文标点拆候选段 + 按阅读速度比例在 E 组区间内细分（复用 `allocate._allocate_by_weight`：吸附真实 cue 边界 ≤300ms，无则 100ms 取整预测点）——阅读舒适优先
     - **双语**：同步生成 `r04_bilingual.srt`（en-zh：英文行 = E 句/片段，子段 EN 按宽度比例机械切、互斥拼接 == 整句 EN）
   - 产物：`r04_draft.srt`（预览，止步 `_work/`）+ `r04_bilingual.srt` + `r04_alerts.md`
2. **agent 复核（按需）**：`r04_alerts.md` 告警处置（长句碎片 🔪 / 独立短句 ⏱️ / 预测点 🎯）——主代理不读全量

##### 校验

1. **告警处置**：`r04_alerts.md`
   - 碎片 cue → 合并容纳完整单元
   - 行宽 >26 → 必切
   - [Music] 等非语音 cue → 跳过
   - 断句暴露译文问题 → 回 r02 改（重切 Z / 重对齐 / 重继承）
2. **时间轴校验**：`python scripts/srt_check_segments.py reflow2/r04_draft.srt --orig <01>`（时间不重叠、区间不逆；时间边界贴原 cue + 允许必要预测点）
3. **行宽校验**：`python scripts/srt_check_width.py reflow2/r04_bilingual.srt --order en-zh`（残留超限仅预警）
4. **预览止步 `_work/`**，未经确认禁止写入 `_output/`；**回填严格脚本化**：只做继承 + 时间运算 + 拆段，禁止任何二次翻译/改写
