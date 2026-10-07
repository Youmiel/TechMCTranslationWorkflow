# reflow2 产物格式（PRODUCT_FORMATS_REFLOW2）

> reflow2（时间轴源头固化；三种工作流中最晚建立）阶段三 专有产物的格式 / 结构 / 标记约定。
> 共享部分不在本文件重复：
> - 阶段〇、一、二产物 `01` / `02`、块骨架格式 → [PRODUCT_FORMATS](PRODUCT_FORMATS.md)
> - `r01_normalized/` [格式](PRODUCT_FORMATS_REFLOW.md#r01_normalizedchunk_ktxt)、`r01_results/` [格式](PRODUCT_FORMATS_REFLOW.md#r01_resultschunk_ktxt)、`r02_results/` [格式](PRODUCT_FORMATS_REFLOW.md#r02_resultschunk_ktxt) → [PRODUCT_FORMATS_REFLOW](PRODUCT_FORMATS_REFLOW.md)（reflow2 仅目录为 `reflow2/`，另加 `srt_reflow2_stitch.py` 跨块句衔接归位）
>
> 本文件只列 reflow2 **专有产物**（源头固化链：`en_timeline` → `consistency` → `zh_sentences` → `align` → 继承回填 r04）。产物统一块级，目录 `<工作目录>/reflow2/`。

## 产物速查

| 产物 | 生成者 | 消费/校验脚本 |
|------|--------|----------------|
| `en_timeline/chunk_<k>.txt` | 脚本 `srt_reflow2_etimeline.py`（E 句 + 固化时间，只读真值锚） | 脚本 `srt_reflow2_backfill.py`（继承时间）、task-match LLM（句子匹配输入） |
| `consistency/chunk_<k>.txt` | Agent（机制断言自洽性复核 subagent，`reflow2/task-consistency`） | 脚本 `srt_reflow2_check_consistency.py`（形态 + 句号引用）、人工审核 |
| `r01_results/`（衔接归位后） | 补标点 subagent → 脚本 `srt_reflow2_stitch.py`（跨块句衔接归位：只在一侧留完整句） | 脚本 `srt_reflow2_etimeline.py`（E 句固化）、翻译 subagent |
| `zh_sentences/chunk_<k>.txt` | 脚本 `srt_reflow2_zsent.py`（Z 句文本列表） | task-match LLM（句子匹配输入）、脚本 `srt_reflow2_backfill.py` |
| `align/chunk_<k>.txt` | Agent（句子匹配 subagent，`reflow2/task-match`） | 脚本 `srt_reflow2_backfill.py`（继承时间） |
| `split_polish/chunk_<k>.txt` | Agent（断句润色 subagent，`reflow2/task-split-polish`） | 脚本 `srt_reflow2_backfill.py --polish-input`（校验 + 逐组回退） |
| `r04_draft.srt` / `r04_bilingual.srt` / `r04_alerts.md` | 脚本 `srt_reflow2_backfill.py` | `srt_check_segments.py`、`srt_check_width.py --order zh-en` |

> 块级产物（`en_timeline` / `consistency` / `zh_sentences` / `align` / `r01_results`）的**块数 = 空隙组数 × 组内片数**。
> 表内 `r01_results/` 的**格式**复用 reflow 文件同名节（见页首链接）——reflow2 只是多一道 `srt_reflow2_stitch.py` 衔接归位。

## `reflow2/en_timeline/chunk_<k>.txt`

- 命名：`<工作目录>/reflow2/en_timeline/chunk_<k>.txt`
- 生成：`python scripts/srt_reflow2_etimeline.py reflow2/chunks/ reflow2/r01_results/ --srt <01> -o reflow2/en_timeline/`——每块 r01（衔接归位后）按句末标点（角色表 `terminator`）切 E 句（复用 presplit `split_en`），每 E 句在块内 OWNED cue 区间锚定（与消费端 `io.build_full` 同构：norm 去空格、无缝拼接；相邻 E 句共享 cue 按字符占比切分）
- 格式：**每行一个 E 句**，`E<n>\t<start> --> <end>\t<c<cues>>\t<文本>`。
  - `E<n>\tMISS\t-\t<文本>` = 锚定失败（回填继承缺该句）
  - `E<n>\t-\t-\t<文本>\t剥离标记后为空` = 内嵌标记剥离后无文本跳过
  - `(global)` 尾注 = 块内未命中走全局兜底（跨块补全句）
- 定位：**纯脚本内部产物**（机器消费）——E 句 = 只读真值锚，下游通过对齐继承时间，**永不重编号**；不面向人工复核格式（人读需结合 align 理解对应）
- 消费：task-match LLM（句子匹配输入，E 文本在 tab 末段）、`srt_reflow2_backfill.py`（继承时间）

## `reflow2/consistency/chunk_<k>.txt`

- 命名：`<工作目录>/reflow2/consistency/chunk_<k>.txt`
- 生成：Agent（机制断言自洽性复核 subagent，`reflow2/task-consistency`；各块独立文件）——LLM 只做**块内**机制断言对立扫描
- 格式：首行固定注释行 `# 机制断言自洽性复核（块内对立扫描）`；其余为**疑点行或 `无矛盾`**（二者互斥、必居其一）：
  - 疑点行 = 4 字段 tab 分隔：`<E<n>>`（断言 A 句号）/ `<E<m>>`（断言 B 句号；单句内部矛盾时与 A 相同）/ `<对立主题>`（≤20 字）/ `<冲突说明>`（≤60 字，引原文锚词）
  - `无矛盾` = 单独一行、不含制表符
- 约束：
  - **只查块内**——不跨块比较、不读本块数据以外的文件
  - **不是事实核查**——只判断两句断言能否同时成立，不判断哪句符合游戏机制、不查资料、不提议改法
  - **例外情形不报**——一句给通用规则、另一句描述该规则的特例 / 附加机制 / 附加条件时，两者可同真
  - 句号一律照抄 `en_timeline` 已有号（不重编号、不写时间戳 / cue 号）；`MISS` / 空文本句不参与复核
  - 产物只是**疑点清单**：脚本不自动改、subagent 不提议改法，裁决归人工审核
- 消费：脚本 `srt_reflow2_check_consistency.py`（形态 + 句号引用合法性）、人工审核（阶段五）

## `reflow2/zh_sentences/chunk_<k>.txt`

- 命名：`<工作目录>/reflow2/zh_sentences/chunk_<k>.txt`
- 生成：`python scripts/srt_reflow2_zsent.py reflow2/r02_results/ -o reflow2/zh_sentences/`——每块 r02 按句末标点（同一通用角色表；中文侧即 `。！？…`）切 Z 句（复用 presplit `split_zh`：括号配平保护/折行合并保留中英数字空格/剥跨块句标记前缀）
- 格式：**整句级 Z 列表**——每行 `Z<n> <整句文本>`；首行 `# Z 整句列表...` 注释
- 定位：Z 句 = 中文整句单元（每次从 r02 重算，删句/改句后重切重对齐、不依赖记忆编号）；无脚手架（不做 r03 模板骨架）
- 消费：task-match LLM（句子匹配输入）、`srt_reflow2_backfill.py`（继承时间）

## `reflow2/align/chunk_<k>.txt`

- 命名：`<工作目录>/reflow2/align/chunk_<k>.txt`
- 生成：Agent（句子匹配 subagent，`reflow2/task-match`；各块独立文件）——LLM 只做 Z↔E 语义对应
- 格式：**同 reflow 匹配文件**（每行 `Z5+Z6+Z7+Z8 = E5`，只含号对应、不抄文本；`#` 注释行可选）——见 [`r03_matches`](PRODUCT_FORMATS_REFLOW.md#r03_matcheschunk_ktxt)
- 约束：**覆盖完整性**——全部 Z 号（`Z1..Zm`）与全部 E 号（`E1..En`）各出现恰好一次；漏句 → 回填问题清单留空，需补派
- 消费：脚本 `srt_reflow2_backfill.py`（继承 E 固化时间）

## `reflow2/split_polish/chunk_<k>.txt`

- 命名：`<工作目录>/reflow2/split_polish/chunk_<k>.txt`；输入清单 `reflow2/split_polish/_request/chunk_<k>.md`
- 生成：Agent（断句润色 subagent，`reflow2/task-split-polish`）——**只复核断点位置**，不写文本
- 格式：**每行一组**，`<组标识> <片1> || <片2> || …`
  - 组标识 = `Z<n>` / `Z<n>+Z<m>`（与 `align/` 同形）；`align/` 中多 Z 对应一个 E 的组即多 Z 标识
  - 片分隔符 = ` || `；片数 == 该组中文段数
- 约束：
  - **只移断点、不改文本**：拼接（去空白）必须逐字符等于该组英文整句
  - 采段组（中文宽度 > 软限）才存在；单片组不进清单
  - 缺失 / 校验未过 → 该组**逐组回退** `punct.split_secondary` 结果，不阻断流程（记 `r04_alerts.md` 的 `🈳`）
  - **无同源校验**（与 `align/` 同类的风险）——`align/` 变更后必须重跑 `--emit-polish` 重导出清单
- 消费：脚本 `srt_reflow2_backfill.py --polish-input`（校验后替代 `split_secondary`；时间轴不受影响）

## `reflow2/split_polish/_request/chunk_<k>.md`

- 命名：`<工作目录>/reflow2/split_polish/_request/chunk_<k>.md`
- 生成：`python scripts/srt_reflow2_backfill.py reflow2/zh_sentences/ reflow2/align/ reflow2/en_timeline/ --emit-polish reflow2/split_polish/_request/`（**仅导出模式**——不写任何 r04 产物，可随时重生成）
- 格式：每个待复核组一节 `## <组标识>` + 中文分段列表（决定片数）+ 英文整句（``` 代码块）
- 约束：**不注入脚本切分结果**——避免引导 subagent 沿脚本切点微调、失去独立判断
- 定位：**临时派发材料**（非产物）；清单与 `split_polish/` 一并重生成

## `reflow2/r04_draft.srt` / `r04_bilingual.srt` / `r04_alerts.md`

- 命名：`<工作目录>/reflow2/r04_draft.srt`（预览单语中文）、`r04_bilingual.srt`（双语 zh-en，中文行在前）、`r04_alerts.md`（告警）
- 生成：`python scripts/srt_reflow2_backfill.py reflow2/zh_sentences/ reflow2/align/ reflow2/en_timeline/ -o reflow2/r04_draft.srt --alert reflow2/r04_alerts.md`（双语默认与 r04 同目录 `r04_bilingual.srt`）
  - 断句润色（可选）：先 `--emit-polish` 导出清单、派发 `task-split-polish`，再 `-o … --polish-input reflow2/split_polish/`
- 格式：
  - `r04_draft.srt`：标准 SRT 单语中文（显示单元 = Z 整句或拆段）；时间 = E 组覆盖范围（源头固化，天然零重叠）
  - `r04_bilingual.srt`：标准 SRT 双语 `zh-en`（中文行 = 对应译文，英文行 = E 句/片段；拆段子单元 EN **按中文段宽比例切**、互斥拼接 == 整句 EN；候选含全部词边界、标点/连词前给奖励、枚举与括号内候选排除、功能词悬空回拉——启发式保护，默认开）
  - `r04_alerts.md`：`# r04_alerts（新 reflow2）` + 总显示单元/跨块句合并/超宽拆段/长句碎片统计 + `## 告警清单`——🔗 跨块句合并（拼中文句界已闭合时附“回 r02 调整”提示）/ 🔪 长句碎片（<1s）/ ⏱️ 独立短句（<1s 语义自足可接受）/ 🎯 预测点（拆段含 100ms 取整）/ 🔀 时间重叠顺延 / ⛔ 倒挂
- 约束：**继承回填严格脚本化**（只做继承 + 时间运算 + 拆段 + **跨块句衔接归位**，禁二次翻译）；时间边界贴原 cue（E 固化），仅拆子段在无真实 cue 边界可吸附处允许 100ms 预测点
  - 跨块句衔接归位：合并被块边界劈成两半的同一句（判据：两侧 EN 归一化后相等 / 前句末尾悬空成分 + 后句碎片）——ZH 互补拼接、EN 去重、时间与真实 cue 边界取并集；块边界常落句中且**无句末可吸附**（ASR 93% cue 末尾无标点），故本机制是常态路径
