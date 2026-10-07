# reflow2 阶段三执行细节（源头固化 + 继承回填）

> 本文件 = `reflow2` 阶段三（时间轴源头固化）的**完整执行指令**（按角色名组织，每个角色按“归一化 → 处理 → 校验”三段组织）。**仅进入阶段三时读取**——阶段〇–阶段二由 [SKILL.md](SKILL.md) 指挥；阶段产物链 / 中断恢复路由 / 输出门禁见 [SKILL.md](SKILL.md#中间产物与断点恢复)。

> **派发边界**：补标点 / 翻译 / 句子匹配**一律派 subagent**（任务 = `task-punctuate` / `task-translate` / `task-match` 的 **reflow2 版**，渲染时 `--skill reflow2`），无需报告策略——见 [subagent-dispatch#派发边界](../subagent-dispatch/SKILL.md#派发边界)。
> **执行型纪律与模型**：纪律母版「一、执行型定位」内联执行型纪律；派发入口 / 运行模型名不在 skill 硬编码——见 [EDITOR_COMPAT#各编辑器派发 subagent 命令表](../../../docs/EDITOR_COMPAT.md)（模型名读 `configs/subagent_model.yaml`）。
>
> **需请求 Wiki 时**（翻译中遇未收录术语/机制不明/数值核对）：先 `refresh_cache.py --check-page "<页面名>"` 判定、过期则 `fetch_wiki.py --refresh "<页面名>"` 主动刷新后重读；需阅页面派 `wiki-researcher`（任务文件 `wiki-tools/task-wiki-query.md`）——见 [wiki-tools](../wiki-tools/SKILL.md)（权威）。

> **行文结构**：各角色按“1. 归一化 → 2. 处理 → 3. 校验”三段标题组织（无归一化环节标注“无”）；空隙探测与分块为前置角色。

---

## 阶段三：时间轴源头固化 + 继承回填

### 空隙探测

##### 归一化

1. 无——直接使用 `01_subtitle_asr_fixed.srt`

##### 处理

1. **空隙探测**：`python scripts/srt_reflow_gap_scan.py <01> -o reflow2/r00_gaps.md`——产出 `r00_gaps.md`（人读：长停顿 >5s / 剪辑跳转 >10s / **疑似源切分缺陷**分节）+ `r00_gaps_active.tsv`（**生效空隙点集 = 单一事实源**）；**已有 tsv 则复用**
2. **硬性断句**：`python scripts/srt_reflow_breaks.py <01> -o reflow2/r01_breaks.md`——断句点清单（含 Agent 复核字段），供补标点先验知识注入

##### 校验

1. **裁决疑似源切分缺陷**：脚本已自动标记（判据：前 cue 末尾无句末标点 **且** 后 cue 首字母小写）——确认是源字幕把同一句切成两条 cue 时，把 `r00_gaps_active.tsv` 该行 `status` 由 `suspect` 改为 **`excluded`**（正式排除：不分块 / 不断句 / 校验跳过；重跑不覆盖）。**脚本只报告不改行为**，默认仍生效
2. **Agent 复核断句点清单**（回填 r01_breaks.md）：每空隙点判定性质（剪辑跳转→断死 / 语义停顿→可松断）、断句方式、游离停顿词归属

### 分块

分块机制见 [redstone-conventions#长视频分块](../redstone-conventions/SKILL.md#长视频分块)。块数为 1 时即单块骨架。

##### 归一化

1. 无——直接使用 `01_subtitle_asr_fixed.srt`

##### 处理

1. **定容量**：`python scripts/context_estimate.py <01>`（默认读 `configs/context_window.json`；输出 `--owned` 建议值）
   - **实践建议**（机制不变）：`--owned` ≤300 cue 封顶（同 reflow-redstone 分块补丁；若单块 >200 cue 遇执行型模型输出超限中断，该视频降回 ≤200）
2. **分块**：`python scripts/text_chunk.py <01.srt> --type srt --gaps-file reflow2/r00_gaps_active.tsv --owned <每块cue数> --ctx 10 --out reflow2/chunks/`
   - 块 = “空隙组-片”；空隙点强制切块（语义硬边界），组内按 `--owned` 拆片
   - `--gaps-file` 读生效集（`excluded` 项自动跳过）——排除源切分缺陷空隙无需再去掉开关

##### 校验

1. 无——分块正确性由后续补标点/校验兜底

### 补标点

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

**任务**：主会话统一跑，所有块完成后一次执行；问题走定点修复（B 档 `task-fix`，见 [subagent-dispatch#定点修正](../subagent-dispatch/SKILL.md#定点修正校验打回先小规模修不整块重派)）。

1. **硬性校验**（空隙点句末标点）：`python scripts/srt_reflow_check_breaks.py <01> reflow2/r01_results/ --chunks reflow2/chunks/ --gaps reflow2/r00_gaps_active.tsv`
   - 读 tsv 生效集（`excluded` 跳过）；命中疑似源缺陷且未排除时会提示“改 tsv 为 excluded”而非要求强制断句
2. **措辞校验**（词序列与 01 一致）：`python scripts/srt_reflow_check_words.py <01> reflow2/r01_results/ --chunks reflow2/chunks/`
3. **补标点质量校验**：`python scripts/srt_reflow_check_sentence_len.py reflow2/r01_results/`（硬：单句逗号 >10 / 单句 >600 / 句均 >350；软：≥8 逗号且 ≥250 字符）
4. **衔接归位**（脚本，文档设计落地）：`python scripts/srt_reflow2_stitch.py reflow2/r01_results/`——
   块 k 末句 ≡ 块 k+1 首句（补标点按规则 4 在两侧各补全的**同一句**）→ **只在一侧留无标记完整句，另一侧不留文本**：
   - **保留前块**（句子归属它开始的地方，剥标记、留完整句）；**后块整句删除**（含标记）
   - **单边标记兜底**：仅一侧有标记 / 两侧内容不等 → 只删标记、保留句子（etimeline 会剥标记），告警交人工确认
   - 归位后 `check_words` 走**跨块互补**判定放行（前块多出的词 == 邻块缺失的词）——两者均属正常，非措辞错误
   - 为何必须：跨块句若原样进翻译 → **同一句被翻两遍**（两块各一次）→ 中文重复、E 句时间重复

> **为何跨块句是常态**：块边界由 `--owned` cue 数等分，**常落在句子中间**——ASR 字幕 93% 的 cue 末尾无句末标点、cue 间又常无缝 → **无句末可吸附**（调 `--owned` 无解：实测 150–270 全范围无规避值）。故归位是关键机制而非兜底。

> 补标点 校验是源头固化 的前置——E 句固化依赖 r01 与 01 措辞一致，措辞错误会造成 E 锚定失败。

### 一致性复核

> 目的：抓**块内自相矛盾的机制断言**（极性对立 / 方向对立 / 归类冲突 / 数值对立）——原始字幕的断言一旦自相矛盾，翻译照直译会把矛盾原样带进交付稿，而全链其余校验只比对**措辞与时间**、无从发现。
> **只看文本内部一致性，不做事实核查**：不查资料、不判断哪句符合游戏机制，疑点交人工裁决。

##### 归一化

1. 无——直接使用 `reflow2/en_timeline/`（E 句 + 固化时间）

##### 处理

1. **块内对立扫描（逐块派 subagent）**：渲染命令 `python scripts/render_subagent_prompt.py task-consistency --skill reflow2 --video <工作目录> [--chunk <k> | --all]`
   - 输入：`reflow2/en_timeline/chunk_<k>.txt`（E 句文本列表）
   - 产物：`reflow2/consistency/chunk_<k>.txt`（疑点 TSV 行 / `无矛盾`）
   - **必须在翻译之前**：矛盾在英文侧已存在，越晚改越贵——改 E 侧后需重跑下游（补标点 → 重切 Z → 重对齐 → 重继承）

##### 校验

1. **形态与句号引用**：`python scripts/srt_reflow2_check_consistency.py reflow2/consistency/ [--expand]`
   - 查块覆盖与 `en_timeline` 一致、4 字段 TSV、`无矛盾` 与疑点行互斥、引用 E 号存在且文本有效（**不判断矛盾是否判对**——内容真伪脚本无法验）
2. **疑点不放行自动修**：产物只是**疑点清单**，脚本不自动改、subagent 不提议改法——结算进阶段五 人工裁决（改哪句 / 是否改由用户定）

### 源头固化

> 本步骤是 reflow2 核心（对应 reflow 的分句阶段，但**零 agent 分句**、零 r03 重型结构）。E 句 = 只读真值锚，下游继承。

##### 归一化

1. 无——直接使用 `reflow2/chunks/`（cue 结构 + 时间戳）+ `reflow2/r01_results/`（衔接归位后补标点整段）+ `01`

##### 处理

1. **源头固化（脚本，一次性全目录）**：`python scripts/srt_reflow2_etimeline.py reflow2/chunks/ reflow2/r01_results/ --srt <01> -o reflow2/en_timeline/`
   - 每块 r01 按句末标点（`terminator` 角色）切 E 句（复用 `split_en`：缩写保护/省略号不切/跨块句标记剥离）
   - 每 E 句在块内 OWNED cue 区间锚定（与消费端 `io.build_full` 同构：norm 去空格、无缝拼接），相邻 E 句共享 cue 按字符占比切分
   - 产物：`reflow2/en_timeline/chunk_<k>.txt`（每行 `E<n>\t<start> --> <end>\t<c<cues>>\t<文本>`）——**纯脚本内部产物**（机器消费）

##### 校验

1. **锚定失败检测**：脚本退出码 1 = 有 E 句 MISS（补标点措辞与 01 不一致 / 标记残留）——定点修复 r01 后重跑
2. **抽查**：E 句固化时间应与原 cue 边界吻合（源头贴原轴，无预测点）

### 翻译

##### 归一化

1. 翻译前将英文输入折行 ≤1000 字符/行（`auto_wrap_file` 就地折行，若 subagent 输出超长）

##### 处理

1. **翻译（逐块派 subagent）**：渲染命令 `python scripts/render_subagent_prompt.py task-translate --skill reflow2 --video <工作目录> [--chunk <k> | --all] [--prior-file <前文摘要>]`
   - 输入：`reflow2/r01_results/chunk_<k>.txt`（整段英文）——**必须是衔接归位（补标点 的校验项 #4）后的版本**（否则块边界句会被翻两遍）——**翻译不吃时间**（输入无时间戳，E 固化走独立支线）
   - 先验知识自动注入 humanizer 注入版 + 术语表；前文摘要用 `--prior-file`
   - 产物：`reflow2/r02_results/chunk_<k>.txt`（整段中文，r02 定稿即自然译文）

##### 校验

1. **术语全量核对**：`python scripts/srt_check_terms.py <01> <02_terms.md> reflow2/r02_results/ --chunks reflow2/chunks/`（退出码 1 = 有未命中，复核后才放行；漂移回写）

### 切 Z 句与对齐

##### 归一化

1. **切 Z 句（脚本，一次性全目录）**：`python scripts/srt_reflow2_zsent.py reflow2/r02_results/ -o reflow2/zh_sentences/`
   - 每块 r02 按句末标点（同一通用角色表；中文侧即 `。！？…`）切 Z 句（复用 `split_zh`：括号配平保护/折行合并保留中英数字空格）
   - 产物：`reflow2/zh_sentences/chunk_<k>.txt`（每行 `Z<n> <整句文本>`）——Z 每次从 r02 重算（删句改句后重切重对齐）

##### 处理

1. **语义对齐（逐块派 subagent，纯号）**：渲染命令 `python scripts/render_subagent_prompt.py task-match --skill reflow2 --video <工作目录> [--chunk <k> | --all]`
   - 输入：`reflow2/en_timeline/chunk_<k>.txt`（E 句 + 固化时间）+ `reflow2/zh_sentences/chunk_<k>.txt`（Z 句列表）对照
   - LLM 只输出对齐文件 `reflow2/align/chunk_<k>.txt`（每行 `Z组 = E组`，如 `Z5+Z6 = E5`；覆盖全部 Z/E 各恰好一次）——不抄文本、不断句、不写时间
   - **覆盖完整性第一要务**：漏任何 Z/E 句 → 回填留空（问题清单），需补派

##### 校验

1. **对齐完整性（脚本）**：回填脚本会报告未对齐的 Z/E——发现漏句 → 定点补派 task-match（B 档，重派缺失块）或人工补行

### 继承回填

##### 归一化

1. 无——`zh_sentences/` + `align/` + `en_timeline/` + `01` 已就绪

##### 处理

1. **导出断句润色清单（脚本，仅导出模式、不写产物）**：`python scripts/srt_reflow2_backfill.py reflow2/zh_sentences/ reflow2/align/ reflow2/en_timeline/ --emit-polish reflow2/split_polish/_request/`
   - 每个**拆段组**（中文超宽、已有断点）导出为 `_request/chunk_<k>.md` 的一项：组标识（`Z<n>` / `Z<n>+Z<m>`）+ 中文各段（决定片数）+ 英文整句
   - **不注入脚本切分结果**——避免引导 subagent 沿脚本切点微调；单片组不进清单
   - 仅导出模式**不需要 `-o`**、不写任何 r04 产物；清单可在任意时点重生成（与 `align/` 同批）
2. **断句润色（逐块派 subagent）**：渲染命令 `python scripts/render_subagent_prompt.py task-split-polish --skill reflow2 --video <工作目录> [--chunk <k> | --all]`
   - 派发引用 prompt（见 [subagent-dispatch#派发引用-prompt](../subagent-dispatch/SKILL.md#派发引用-prompt)）
   - 产物：`reflow2/split_polish/chunk_<k>.txt`：每行 `<组标识> <片1> || <片2> || …`
     - **只移断点、不改文本**（拼接必须逐字符等于英文整句）
     - 片数 == 该组中文段数
     - 依据：脚本按中文段宽比例切出的断点仍可能落在**句法单元内部**（限定词/名词、介词/宾语、助动词/主动词、短语动词被劈开）——这类判断需语义/句法识别
3. **继承 + 回填（脚本，唯一写入动作）**：`python scripts/srt_reflow2_backfill.py reflow2/zh_sentences/ reflow2/align/ reflow2/en_timeline/ -o reflow2/r04_draft.srt --alert reflow2/r04_alerts.md --polish-input reflow2/split_polish/`
   - `--polish-input` 可省（回退到脚本切分，与未引入本环节时逐字节一致）
   - 处理方式（**脚本内一次性完成，主代理零读取、不参与时间分配**）：
     - **跨块句兜底合并**（拆段前）：兜底处理**未走补标点 衔接归位**的历史产物（两侧都补全 → EN 重复）或
       ASR 残式边界（互补两半）。判据 ① **重复**：两侧 EN 归一化后相等 → EN 取后块完整句；
       ② **悬空延续**：前块末句 EN 以悬空成分收尾（介词/冠词/连词/及物动词，与 task-punctuate 规则 7 同源词表）
       且后块首句为碎片 → 前句去尾标点拼后句。
       - ZH 互补拼接（两侧相同则去重；**前句中文已闭合句号时告警**提醒可能需润色 / 回 r02 调整）
       - 告警类型 `🔗 跨块句合并`（见 `r04_alerts.md`）
       - **走新流程（归位 → 翻译）时本步不会触发**——块边界句已在源头归位，一侧已无文本
     - **继承**：每 Z 组对应 E 组，时间 = E 组覆盖范围 [首 E.start, 末 E.end]（E 固化时间已含共享 cue 切分，继承天然零重叠）
     - **拆子段**：Z 句超宽（>硬 27，视觉宽度）→ 按**标点功能角色表**（`srt_reflow_core.punct`）拆候选段 + 按阅读速度比例在 E 组区间内细分（复用 `allocate._allocate_by_weight`：吸附真实 cue 边界 ≤300ms，无则 100ms 取整预测点）——阅读舒适优先
       - **拼合 = 代价最小化**（断点强度 + 段宽偏离 [15,22] + 碎片罚）：`strong`（`；：—`）> `clause`（`，`）> `list`（`、`）；括号内断点为**软代价**（优先保持括注完整，超宽时允许断开）
         - 顿号（`、`）代价取 **18.0**（“最后手段”）——优先保住并列成分完整，但超硬限时仍可断（完全禁止会使并列项长句切不动、直接超硬限）
         - 拼合不用“贪心填满硬上限”：贪心会吞掉强断点（`…回答一下：第一，` + `怎么搭…？`，断点落在逗号而非冒号）；分号 = `strong` 强优先（可被宽度否决）、不硬断
     - **双语**：同步生成 `r04_bilingual.srt`（zh-en：中文行在前，英文行 = E 句/片段，子段 EN **按中文段宽比例切**、互斥拼接 == 整句 EN）
       - 候选含**全部词边界**；标点处 / 从句连词前 / 一般连接词前给奖励；枚举与括号内部**候选排除**；功能词（介词/冠词/助动词/并列连词）后的悬空切点**回拉**（把功能词挪到后段）
       - 启发式保护默认开，`--no-enum-keep` / `--no-bracket-keep` / `--dangling-pullback` / `--punct-cut-bonus` 等可调
       - **断句润色结果优先**：`--polish-input` 给出且校验通过时用其结果，否则回退脚本切分（逐组）
   - 产物：`r04_draft.srt`（预览，止步 `_work/`）+ `r04_bilingual.srt` + `r04_alerts.md`
4. **agent 复核（按需）**：`r04_alerts.md` 告警处置（长句碎片 🔪 / 独立短句 ⏱️ / 预测点 🎯）——主代理不读全量

##### 校验

1. **告警处置**：`r04_alerts.md`
   - 碎片 cue → 合并容纳完整单元
   - 行宽 >27 → 必切
   - [Music] 等非语音 cue → 跳过
   - 断句暴露译文问题 → 回 r02 改（重切 Z / 重对齐 / 重继承）
   - `🈳 断句润色回退` → 该组按脚本切分输出（片数/拼接校验未过），可重派该块
2. **时间轴校验**：`python scripts/srt_check_segments.py reflow2/r04_draft.srt --orig <01>`（时间不重叠、区间不逆；时间边界贴原 cue + 允许必要预测点）
3. **行宽校验**：`python scripts/srt_check_width.py reflow2/r04_bilingual.srt --order zh-en`（残留超限仅预警）
4. **预览止步 `_work/`**，未经确认禁止写入 `_output/`；**回填严格脚本化**：只做继承 + 时间运算 + 拆段，禁止任何二次翻译/改写
