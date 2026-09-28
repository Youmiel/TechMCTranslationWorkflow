# reflow2 产物格式（PRODUCT_FORMATS_REFLOW2）

> reflow2（时间轴源头固化；三种工作流中最晚建立）阶段二专有产物的格式 / 结构 / 标记约定。
> 共享部分不在本文件重复：
> - 阶段〇/一产物 `01` / `02`、块骨架格式 → [PRODUCT_FORMATS](PRODUCT_FORMATS.md)
> - `r01_normalized/` [格式](PRODUCT_FORMATS_REFLOW.md#r01_normalizedchunk_ktxt归一化输入)、`r01_results/` [格式](PRODUCT_FORMATS_REFLOW.md#r01_resultschunk_ktxt补标点块)、`r02_results/` [格式](PRODUCT_FORMATS_REFLOW.md#r02_resultschunk_ktxt翻译块) → [PRODUCT_FORMATS_REFLOW](PRODUCT_FORMATS_REFLOW.md)（reflow2 仅目录为 `reflow2/`，另加 `srt_reflow2_stitch.py` 跨块句衔接归位）
>
> 本文件只列 reflow2 **专有产物**（源头固化链：`en_timeline` → `zh_sentences` → `align` → 继承回填 r04）。产物统一块级，目录 `<工作目录>/reflow2/`。

## 产物速查

| 产物 | 生成者 | 消费/校验脚本 |
|------|--------|----------------|
| `en_timeline/chunk_<k>.txt` | 脚本 `srt_reflow2_etimeline.py`（E 句 + 固化时间，只读真值锚） | 脚本 `srt_reflow2_backfill.py`（继承时间）、task-match LLM（句子匹配输入） |
| `r01_results/`（衔接归位后） | 补标点 subagent → 脚本 `srt_reflow2_stitch.py`（跨块句衔接归位：只在一侧留完整句） | 脚本 `srt_reflow2_etimeline.py`（E 句固化）、翻译 subagent |
| `zh_sentences/chunk_<k>.txt` | 脚本 `srt_reflow2_zsent.py`（Z 句文本列表） | task-match LLM（句子匹配输入）、脚本 `srt_reflow2_backfill.py` |
| `align/chunk_<k>.txt` | Agent（句子匹配 subagent，`reflow2/task-match`） | 脚本 `srt_reflow2_backfill.py`（继承时间） |
| `r04_draft.srt` / `r04_bilingual.srt` / `r04_alerts.md` | 脚本 `srt_reflow2_backfill.py` | `srt_check_segments.py`、`srt_check_width.py --order zh-en` |

> 块级产物（`en_timeline` / `zh_sentences` / `align` / `r01_results`）的**块数 = 空隙组数 × 组内片数**。
> 表内 `r01_results/` 的**格式**复用 reflow 文件同名节（见页首链接）——reflow2 只是多一道 `srt_reflow2_stitch.py` 衔接归位。

## `reflow2/en_timeline/chunk_<k>.txt`（E 句 + 固化时间，只读真值锚）

- 命名：`<工作目录>/reflow2/en_timeline/chunk_<k>.txt`
- 生成：`python scripts/srt_reflow2_etimeline.py reflow2/chunks/ reflow2/r01_results/ --srt <01> -o reflow2/en_timeline/`——每块 r01（衔接归位后）按 `.?!` 切 E 句（复用 presplit `split_en`），每 E 句在块内 OWNED cue 区间锚定（与消费端 `io.build_full` 同构：norm 去空格、无缝拼接；相邻 E 句共享 cue 按字符占比切分）
- 格式：**每行一个 E 句**，`E<n>\t<start> --> <end>\t<c<cues>>\t<文本>`。
  - `E<n>\tMISS\t-\t<文本>` = 锚定失败（回填继承缺该句）
  - `E<n>\t-\t-\t<文本>\t剥离标记后为空` = 内嵌标记剥离后无文本跳过
  - `(global)` 尾注 = 块内未命中走全局兜底（跨块补全句）
- 定位：**纯脚本内部产物**（机器消费）——E 句 = 只读真值锚，下游通过对齐继承时间，**永不重编号**；不面向人工复核格式（人读需结合 align 理解对应）
- 消费：task-match LLM（句子匹配输入，E 文本在 tab 末段）、`srt_reflow2_backfill.py`（继承时间）

## `reflow2/zh_sentences/chunk_<k>.txt`（Z 句文本列表）

- 命名：`<工作目录>/reflow2/zh_sentences/chunk_<k>.txt`
- 生成：`python scripts/srt_reflow2_zsent.py reflow2/r02_results/ -o reflow2/zh_sentences/`——每块 r02 按 `。！？…` 切 Z 句（复用 presplit `split_zh`：括号配平保护/折行合并保留中英数字空格/剥跨块句标记前缀）
- 格式：**整句级 Z 列表**——每行 `Z<n> <整句文本>`；首行 `# Z 整句列表...` 注释
- 定位：Z 句 = 中文整句单元（每次从 r02 重算，删句/改句后重切重对齐、不依赖记忆编号）；无脚手架（不做 r03 模板骨架）
- 消费：task-match LLM（句子匹配输入）、`srt_reflow2_backfill.py`（继承时间）

## `reflow2/align/chunk_<k>.txt`（对齐文件，纯号）

- 命名：`<工作目录>/reflow2/align/chunk_<k>.txt`
- 生成：Agent（句子匹配 subagent，`reflow2/task-match`；各块独立文件）——LLM 只做 Z↔E 语义对应
- 格式：**同 reflow 匹配文件**（每行 `Z5+Z6+Z7+Z8 = E5`，只含号对应、不抄文本；`#` 注释行可选）——见 [`r03_matches`](PRODUCT_FORMATS_REFLOW.md#r03_matcheschunk_ktxt分句输入匹配文件脚本断句路径)
- 约束：**覆盖完整性**——全部 Z 号（`Z1..Zm`）与全部 E 号（`E1..En`）各出现恰好一次；漏句 → 回填问题清单留空，需补派
- 消费：脚本 `srt_reflow2_backfill.py`（继承 E 固化时间）

## `reflow2/r04_draft.srt` / `r04_bilingual.srt` / `r04_alerts.md`

- 命名：`<工作目录>/reflow2/r04_draft.srt`（预览单语中文）、`r04_bilingual.srt`（双语 zh-en，中文行在前）、`r04_alerts.md`（告警）
- 生成：`python scripts/srt_reflow2_backfill.py reflow2/zh_sentences/ reflow2/align/ reflow2/en_timeline/ -o reflow2/r04_draft.srt --alert reflow2/r04_alerts.md`（双语默认与 r04 同目录 `r04_bilingual.srt`）
- 格式：
  - `r04_draft.srt`：标准 SRT 单语中文（显示单元 = Z 整句或拆段）；时间 = E 组覆盖范围（源头固化，天然零重叠）
  - `r04_bilingual.srt`：标准 SRT 双语 `zh-en`（中文行 = 对应译文，英文行 = E 句/片段；拆段子单元 EN 按宽度比例机械切、互斥拼接 == 整句 EN）
  - `r04_alerts.md`：`# r04_alerts（新 reflow2）` + 总显示单元/跨块句合并/超宽拆段/长句碎片统计 + `## 告警清单`——🔗 跨块句合并（拼中文句界已闭合时附「回 r02 调整」提示）/ 🔪 长句碎片（<1s）/ ⏱️ 独立短句（<1s 语义自足可接受）/ 🎯 预测点（拆段含 100ms 取整）/ 🔀 时间重叠顺延 / ⛔ 倒挂
- 约束：**继承回填严格脚本化**（只做继承 + 时间运算 + 拆段 + **跨块句衔接归位**，禁二次翻译）；时间边界贴原 cue（E 固化），仅拆子段在无真实 cue 边界可吸附处允许 100ms 预测点
  - 跨块句衔接归位：合并被块边界劈成两半的同一句（判据：两侧 EN 归一化后相等 / 前句末尾悬空成分 + 后句碎片）——ZH 互补拼接、EN 去重、时间与真实 cue 边界取并集；块边界常落句中且**无句末可吸附**（ASR 93% cue 末尾无标点），故本机制是常态路径
