# vocalign 阶段三执行细节（工作流核心）

> 本文件 = 阶段三的**完整执行指令**（按角色名组织）。**仅进入阶段三时读取**——阶段路由 / 产物链 / 中断恢复见 [SKILL.md](SKILL.md#中间产物与断点恢复)。

> **派发边界**：翻译 / 对齐 / 候选点**一律派 subagent**（任务 = `task-translate` / `task-match` / `task-candidates`，渲染时 `--skill vocalign`），无需报告策略——见 [subagent-dispatch#派发边界](../subagent-dispatch/SKILL.md#派发边界)。
> **执行型纪律与模型**：纪律母版「一、执行型定位」内联执行型纪律；派发入口 / 运行模型名不在 skill 硬编码——见 [EDITOR_COMPAT#各编辑器派发 subagent 命令表](../../../docs/EDITOR_COMPAT.md)（模型名读 `configs/subagent_model.yaml`）。

---

## 阶段三：工作流核心

### 分块：正式分块

##### 归一化

1. 无——直接使用 `vocalign/e0/long_lines.srt`（**定稿载体**）

##### 处理

1. **分块**：`python scripts\text_chunk.py "<W>\vocalign\e0\long_lines.srt" --type srt --owned <N> --ctx 10 --out "<W>\vocalign\chunks"`
   - `--owned` 取值同“阶段〇 分块：清单分批”（用 `context_estimate.py` 定）
   - **必须重跑覆盖**清单分批用的块——否则块内文本是**未定稿**的，翻译与术语识别会读到旧文本

##### 校验

1. **抽查块内文本 = 定稿文本**（应含定稿修正词与并入的注释）
2. 块数应与清单分批一致（同一 `--owned` 下，长句边界不变）

### 一致性复核

> 目的：抓**块内自相矛盾的机制断言**（极性对立 / 方向对立 / 归类冲突 / 数值对立）——原始转写的断言一旦自相矛盾，翻译照直译会把矛盾原样带进交付稿，而全链其余校验只比对**措辞与时间**、无从发现。
> **只看文本内部一致性，不做事实核查**：不查资料、不判断哪句符合游戏机制，疑点交人工裁决。

1. **块内对立扫描（逐块派 subagent）**：渲染命令 `python scripts\render_subagent_prompt.py task-consistency --skill vocalign --video "<W>" [--chunk <k> | --all]`
   - 派发引用 prompt（见 [subagent-dispatch#派发引用-prompt](../subagent-dispatch/SKILL.md#派发引用-prompt)）
   - 输入：`vocalign/e0/en_timeline/chunk_<k>.txt`（S 句文本列表）
   - 产物：`vocalign/consistency/chunk_<k>.txt`（疑点 TSV 行 / `无矛盾`）
   - **必须在翻译之前**：矛盾在英文侧已存在，越晚改越贵——改英文侧后需回文本定稿重跑下游
2. **形态与句号引用校验**（主会话统一跑，所有块完成后一次执行）：`python scripts/srt_reflow2_check_consistency.py "<W>\vocalign\consistency" --etimeline "<W>\vocalign\e0\en_timeline" --id-prefix S [--expand]`
   - 查块覆盖与 `en_timeline` 一致、4 字段 TSV、`无矛盾` 与疑点行互斥、引用 S 号存在且文本有效（**不判断矛盾是否判对**——内容真伪脚本无法验）
3. **疑点不放行自动修**：产物只是**疑点清单**，脚本不自动改、subagent 不提议改法——结算进阶段五 人工裁决（改哪句 / 是否改由用户定）

### 翻译

##### 归一化

1. **块文本归一化（脚本一次性全目录）**：`python scripts/srt_reflow_normalize.py "<W>\vocalign\chunks" -o "<W>\vocalign\r01_normalized"`
   - 每块 `## BEFORE`/`## OWNED`/`## AFTER` 分区内 cue 文本**预先合并**为连续文本，折行 ≤1000 字符/行
   - **无补标点环节**——标点已在阶段〇定稿完成；本步只做合并

##### 处理

1. **翻译（逐块派 subagent）**：渲染命令 `python scripts\render_subagent_prompt.py task-translate --skill vocalign --video "<W>" [--chunk <k> | --all]`
   - 派发引用 prompt（见 [subagent-dispatch#派发引用-prompt](../subagent-dispatch/SKILL.md#派发引用-prompt)）
   - 输入：`vocalign/r01_normalized/chunk_<k>.txt`（整段英文，**不吃时间**——时轴独立于翻译）
   - 先验知识自动注入 humanizer 注入版 + 术语表
   - 产物：`vocalign/r02_results/chunk_<k>.txt`（整段中文，定稿即自然译文，无二次创作）
   - **非口播注释**（定稿头部注明的括号内容）按其规则保留括号并从简

##### 校验

**任务**：主会话统一跑，所有块完成后一次执行；问题走定点修复（B 档 `task-fix`）。

1. **术语全量核对**：`python scripts/srt_check_terms.py "<W>\vocalign\e0\long_lines.srt" "<W>\02_terms.md" "<W>\vocalign\r02_results" --chunks "<W>\vocalign\chunks"`
   - 第一参用 **E0 定稿载体**（其 cue 号恒等于 S 号，与 `chunks/` 同源）——vocalign 无 `01`，本载体即英文原文的对照物
   - 退出码 1 = 有未命中（⚠️/ℹ️），复核后才放行；漂移回写
2. **块覆盖**：`r02_results/` 与 `chunks/` 块号一一对应（缺块会导致回填留空）

### 对齐

1. **切 Z 句（脚本一次性全目录）**：`python scripts/srt_reflow2_zsent.py "<W>\vocalign\r02_results" -o "<W>\vocalign\zh_sentences"`
   - 按句末标点切 Z 句（括号配平保护 / 折行合并保留中英数字空格）
   - 产物：`zh_sentences/chunk_<k>.txt`（每行 `Z<n> <整句文本>`）——Z 每次从 r02 重算
2. **语义对齐（逐块派 subagent）**：渲染命令 `python scripts\render_subagent_prompt.py task-match --skill vocalign --video "<W>" [--chunk <k> | --all]`
   - 派发引用 prompt（见 [subagent-dispatch#派发引用-prompt](../subagent-dispatch/SKILL.md#派发引用-prompt)）
   - 输入：`vocalign/e0/en_timeline/chunk_<k>.txt`（S 长句 + 语音实测时间）+ `vocalign/zh_sentences/chunk_<k>.txt`（Z 句列表）对照
   - LLM 只输出对齐文件 `vocalign/align/chunk_<k>.txt`（每行 `Z组 = S组`）——不抄文本、不断句、不写时间
   - **覆盖完整性第一要务**：Z 与 S 号各出现恰好一次；漏任何一句 → 回填留空
3. **完整性验收**：回填脚本会报告未对齐的 Z / S——发现漏句 → 定点补派 `task-match`（B 档，重派缺失块）或人工补行
4. **抽检语义对应**：中英语序会交叉，不可按序一一对应（`task-match` 规则 5）

> **为何自产对齐**：定稿长句自带**语音实测时间**，故不再需要 reflow2 的 `en_timeline`（cue 锚定产物）——vocalign 自产 `Z<n> = S<m>`，块号体系因此独立（不与 reflow2 耦合）。
> **S 号为全局编号**（reflow2 的 E 号为块内局部）——跨块消费无需按块分装。

### 候选点

##### 归一化

1. 无——直接使用 `vocalign`（骨架 + 定稿文本 + 分块）

##### 处理

1. **导出清单（脚本）**：
   ```powershell
   python scripts\vocalign_candidates.py emit --skeleton "<W>\vocalign" --words "<W>\vocalign" `
       --e0 "<W>\vocalign\e0" --chunks "<W>\vocalign\chunks" --srt "<W>\vocalign\e0\long_lines.srt"
   ```
   - **必须传 `--e0`**：清单显示**定稿文本**（否则仲裁修正不进清单，` | ` 位置与实际文本错位）
   - 产出 `candidates/_request/chunk_<k>.md`（长句 + 净停顿标注；**不给**脚本自己的切分结果，避免引导微调而非重判）
2. **标注（逐块派 subagent）**：渲染命令 `python scripts\render_subagent_prompt.py task-candidates --skill vocalign --video "<W>" [--chunk <k> | --all]`
   - 派发引用 prompt（见 [subagent-dispatch#派发引用-prompt](../subagent-dispatch/SKILL.md#派发引用-prompt)）
   - 产物：`candidates/reply/chunk_<k>.txt`（`S<n>` + 原句，在语义边界插 ` | `）
   - 分隔符固定 ` | `（前后各一空格）；**禁用 `/`**（Minecraft 命令大量使用）；**候选宁多勿少**（候选集非最终切点）；已有标点处不必标注
3. **作答校验（脚本）**：`python scripts\vocalign_candidates.py check --skeleton "<W>\vocalign" --words "<W>\vocalign" --e0 "<W>\vocalign\e0"`
4. **词号归一（脚本）**：`python scripts\vocalign_candidates.py norm --skeleton "<W>\vocalign" --words "<W>\vocalign" --e0 "<W>\vocalign\e0"`
   - 产出 `candidates/chunk_<k>.tsv`（S 号 / **全局词号** / 句内词号）

##### 校验

1. **作答校验**：`check` 退出码 0；失败行记为空候选（回填回退纯语音权重，不静默）
2. **人工复核** `candidates/_check_report.md` 的失败明细
3. **词号抽查**：tsv 的全局词号应指向切点左侧词的正确位置

> **为何需要 LLM 候选点**：骨架（标点 + 净停顿）对“子句内部仍需切分”的长句**零候选**——无标点且无 ≥250ms 停顿处只能靠语义判断。
> **⚠️ 定稿可能增删词**（仲裁替换词数不同、注释并入新增词）：
> - 词号锚定用 **difflib 相似度对齐**（**不按顺序映射**）
> - 落在定稿新增词上的切点**无原词锚 → 丢弃**（宁少勿错）
> **候选点环节替代 reflow2 的断句润色**：reflow2 需 LLM 在脚本切点间**移动**断点（脚本切点可能落在句法单元内部）；vocalign 的候选集本身就是 LLM 给的语义边界，脚本只在候选中挑——语义判断前移到了本环节。

### 回填

##### 归一化

1. 无——`words.json` + `r02_results/` + `align/` + `e0/` + `chunks/` + `candidates/` 已就绪

##### 处理

1. **回填组装（脚本，唯一写入 r04 的动作）**：
   ```powershell
   python scripts\vocalign_backfill.py --words "<W>\vocalign\words.json" `
       --r02 "<W>\vocalign\r02_results" --align "<W>\vocalign\align" `
       --e0 "<W>\vocalign\e0" --chunks "<W>\vocalign\chunks" `
       --candidates "<W>\vocalign\candidates" -o "<W>\vocalign" --expand
   ```
   - **处理方式（脚本内一次性完成，主代理零读取、不参与时间分配）**：
     - **中文分段**：按句末标点切 Z 句，超硬限（27）的用断点强度代价 DP 拆子段——**只拆不合**（不跨句合并）
     - **英文切分**：全词边界候选 + **惩罚阶梯**选点（标点与长停顿 0，短停顿 20，候选点 60，无证据 200），片宽贴合中文段宽占比
     - **时间**：片取**语音实测词边界**；**S 组聚簇**（多个 Z 共享一 S 组时合并处理，防时间重叠）；相邻组词范围**单调钳制**（容差会让相邻组各多取同一个词）
     - **段时长兜底**：不足 1s 时**借相邻空隙**延长（先后借再前借，不改切点）
     - **注释保真**：定稿并入的非口播注释文本随长句进入英文片
   - 产物：`r04_draft.srt` / `r04_bilingual.srt` / `r04_alerts.md`

##### 校验

1. **回填校验**：退出码 0 = 无片数 / 拼接 / 时间倒挂错误（退出码 1 时看 `r04_alerts.md` 的“校验失败”节）
2. **切点验收（看 `r04_alerts.md` 的切点来源统计）**：
   - `none`（无证据切点）应尽量少——它们正是候选点环节的目标消除对象
   - 与候选点环节未启用时对比：**无证据切点数下降**、标点结尾率不下降、切在词中率恒为 0
   - ⚠️ **不可用“停顿证据率”作验收判据**：候选点的价值正在**无语音证据处**，该率必然下降
3. **人工审核（阶段五）**：`align/` 的语义对应 + `r04_bilingual.srt` 阅读节奏 + `r04_alerts.md` 的无证据切点

> **为何不需要“跨块句”机制**：块边界必然落在骨架长句边界（`cue ≡ S`），故不存在被切开的句子——对照 reflow2 需“衔接归位”正因其块按 cue 数等分、常落在句中。
