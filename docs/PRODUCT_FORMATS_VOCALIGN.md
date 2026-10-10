# 产物格式规范 — vocalign（语音对齐骨架驱动）

> 通用约定（编码 / 折行 / 符号分工 / 变更同步清单）见 [`PRODUCT_FORMATS.md`](PRODUCT_FORMATS.md)。
> 共享产物（`00` / `01` / `02` / `term` / `wiki`）见同文件的共享产物章节。
> 设计依据见 `Project_Plan/2026-10-08_vocalign独立前置设计.md`。

## 本工作流产物速查

| 产物 | 生成者 | 消费 / 校验 |
|---|---|---|
| `vocalign/segments.srt` | `vocalign_collect.py` | 人工核标点质量 |
| `vocalign/segments.suspect.md` | `vocalign_collect.py` | **转写可疑段**（重复幻觉 / 循环 / 语速异常）——只报不改，交 agent 或人工处置 |
| `vocalign/words.json` | `vocalign_collect.py` | `vocalign_skeleton.py` |
| `vocalign/skeleton.json` | `vocalign_skeleton.py` | `vocalign_text.py` / `vocalign_candidates.py` |
| `vocalign/skeleton.txt` · `boundaries.txt` · `stitches.txt` | 同上 | **人工抽查**（骨架质量）/ **人工调参**（判据明细）/ **复核碎片归位** |
| `vocalign/long_lines.srt` | `vocalign_skeleton.py` | `text_chunk.py`（初版载体，供分块） |
| `vocalign/e0/long_lines.md` | `vocalign_text.py apply` | 术语扫描与翻译的输入 |
| `vocalign/e0/long_lines.srt` | 同上 | `glossary_load_plan` / `glossary_lookup` / `text_chunk` / `vocalign_backfill.py` |
| `vocalign/e0/en_timeline/` | 同上 | 对齐子 agent（`task-match`） |
| `vocalign/e0/_request/` · `reply/` · `_items.json` · `report.md` | `vocalign_text.py` / 定稿子 agent | `check` / `apply` |
| `vocalign/e0/_changes.tsv` | `vocalign_text.py apply` | **改动审计**（人工复核：S 号 / 改动类型 / 骨架原文 / 定稿） |
| `vocalign/chunks/` | `text_chunk.py` | 翻译派发（块边界在长句边界） |
| `vocalign/consistency/chunk_<k>.txt` | 复核子 agent | `srt_reflow2_check_consistency.py --id-prefix S`、人工裁决 |
| `vocalign/r01_normalized/` | `srt_reflow_normalize.py` | 翻译子 agent |
| `vocalign/r02_results/` | 翻译子 agent | `srt_reflow2_zsent.py` / `vocalign_backfill.py` |
| `vocalign/zh_sentences/` | `srt_reflow2_zsent.py` | 对齐子 agent |
| `vocalign/align/` | 对齐子 agent | `vocalign_backfill.py`（`Z<n> = S<m>`） |
| `vocalign/candidates/*` | `vocalign_candidates.py` / 候选点子 agent | `vocalign_backfill.py --candidates` |
| `r04_draft.srt` / `r04_bilingual.srt` / `r04_alerts.md` | `vocalign_backfill.py` | 人工审核 |
| `<名>.filled.srt` | `srt_fill_gaps.py` | 交付稿（空隙填充后；原稿保留供对照） |
| `vocalign/_fix_splits.draft.md` | `vocalign_backfill.py` | 人工裁决（超宽片定点修复草稿） |
| `vocalign/collect_report.txt` | `vocalign_collect.py` | 耗时 / 规模诊断 |
| `vocalign/segments_patched.srt` / `patch_report.md` | `vocalign_collect.py`（`--patch-pad`） | 可疑点重识别拼接稿 / 逐窗口对照 |

## `words.json`：词级时轴

```json
{
 "meta": {
  "audio": "xxx.mp3", "model": "large-v3", "device": "cuda", "compute_type": "float16",
  "language": "en", "segments": 154, "n_words": 2558, "n_unaligned": 64,
  "timing_s": {"load_and_extract": 2.4, "align": 6.9}
 },
 "words": [
  {"start": 0.74, "end": 1.142, "text": "Repeaters", "score": 0.804},
  {"start": null, "end": null, "text": "15.", "score": null}
 ]
}
```

**字段约定**

- `text`：**词尾带标点**（`comparators,` / `output.`）——标点与时间同源，是本工作流的核心输入
- `start` / `end`：**秒**（float，毫秒精度保留 3 位）。**`null` = 未对齐词占位**
- ⚠️ **`null` 不是脏数据**：whisperX 约 2.6% 词对齐失败（几乎全是数字：`15.` / `3` / `8, 8` / `20`）。
  采集端**必须保留**它们，骨架构建器按前后锚点插值补齐。
  **删除占位会让词序列出现空洞，前后词直接相邻，跨空洞间隙被误判为停顿边界**
  （伪边界示例 `values of | and`，原文 "values of 1 and 2"）
- `score`：对齐置信度 0–1（未对齐词为 `null`）

## `skeleton.json`：骨架结构

```json
{
 "source": {"words": "words.json", "srt": ""},
 "params": {"baseline_ms": 40.0, "sent_ms": 500.0, "clause_ms": 250.0, "clause_upgrade_ms": 0.0},
 "align": {"interp": 64, "synth": 0, "hole_total": 64, "aligned": 2494, "text_source": "words"},
 "n_words": 2558, "n_sentences": 149, "n_sentences_raw": 164, "n_stitched": 15,
 "stitches": [{"end": 176.46, "left": "…the delay by", "right": "eight game ticks…"}],
 "n_clauses": 263,
 "boundary_sources": {"sent/punct": 111, "clause/punct": 73, "sent/pause": 37, "clause/pause": 41},
 "clause_words": {"n": 263, "p25": 5.0, "p50": 9.0, "p90": 17.0, "max": 27},
 "sentence_clauses": {"n": 149, "p50": 2.0, "max": 6},
 "low_conf_bounds": [{"i": 42, "after": "works", "before": "so", "gap_ms": 423.0, "conf": "low"}],
 "sentences": [
  {"start": 0.74, "end": 8.257, "nclauses": 3, "nwords": 25,
   "text": "…", "clauses": [{"start": 0.74, "end": 1.926, "nwords": 3, "text": "Repeaters and comparators,"}]}
 ]
}
```

**字段约定**

- 三层：`sentences[]`（长句）/ `clauses[]`（子句）/ 词（在 `words.json`）
- 时间单位 = **秒**；`boundary_sources` 的键 = `<level>/<why>`，`why` ∈ `punct` / `pause` / `punct+longpause`
- `n_sentences_raw` → `n_sentences` 的差 = **碎片归位**合并数（`n_stitched`，明细见 `stitches.txt`）
- `low_conf_bounds`：无标点加短停顿（250–500ms）的边界，**真伪混杂**（如 `works | so` 为真、
  `a | game` 为伪），须人工或 LLM 裁决；脚本**只标注不降级**

## `stitches.txt`：碎片归位明细

whisper 是**段级**输出（按静音窗口切段），段边界**不保证与句界一致**——落在句中时骨架会把它当句界，长句被切碎。
归位判据同 reflow2 的**源切分缺陷**：**前句末尾无句末标点** 且 **后句首字母小写**（英文句首必大写，故为强证据；两条件同时成立才合并）。

```
# 碎片归位明细（前句末尾无句末标点 + 后句首字母小写 → 合并）
# 长句 164 → 150（合并 14 处）

1. 00:01:56,460
   left：…Each time you click, it increases the delay by
   right：eight game ticks.…
```

`--no-stitch` 关闭归位（合并误伤时用）；关闭后长句数回到 `n_sentences_raw`。

## `segments.suspect.md`：转写可疑段

whisper 在前文上下文（`condition_on_previous_text=True`）中偶发**重复幻觉**：重复文本占用时间，段时长被压缩，强制对齐错位，骨架在该处产生伪边界。本报告只**探测并上报**，不自动删改。

```
# 转写可疑段（幻觉探测，**只报不改**）

- 段 28（00:01:56,480 → 00:01:57,200，108 字符/秒）：段首重复前段末 3 词；语速过快 108 字符/秒
  - 文本：two game ticks. Each time you click, it increases the delay by two game ticks.

## 循环区间（内容可能已丢失）

- 段 113–116：`the number of slots you want to use to` ×4
```

**探测项**（阈值见 `vocalign_collect.py` 顶部常量）

- 段首重复紧前段末 ≥6 词（重复幻觉的经典形态）
- 跨段 n-gram 循环：同 8-gram 连续重复 ≥3 次（跑飞；**必须跨段检**——每段各含 2 次时单段内达不到阈值）
- 字速率异常：<8 或 >28 字符/秒（正常语速 ~15；超上限 = 时长被压缩）

**处置**（agent / 人工决策，脚本不自动改）

- **重复型**：删去重复片段（内容无损失）
- **循环型**：该区间真实内容**已被循环挤掉**，删重复无法恢复 → 取该时间区间**重跑识别**
- **语速异常型**：多为上述两者的伴随症状；单独出现时核对音频
- 处置后**必须重跑对齐与骨架**（时间变则切分变）
- ⚠️ **不得凭本报告判丢句**——它判的是跑飞；有无内容缺失需对照油管**原始字幕**核验

## `boundaries.txt`：判据明细

供调参用。

```
# 词间边界判据明细（净停顿 = 原始间隙 − baseline 40ms）
# i	level	why	conf	gap_ms	net_ms	after | before
42	clause	pause	low	423.0	383.0	works | so
```

`conf`：`high` = 标点直出 / `med` = 长停顿补出（≥540ms）/ `low` = 短停顿补出 / `-` = 非边界。

## `candidates/*`：语义候选点

骨架（标点与净停顿）对子句内部仍需切分的长句无候选（无标点、无 ≥250ms 停顿）
，这类位置只能靠 LLM 语义判断。产物为清单、作答、归一化。

**派发粒度 = 合译组**（行首 `S10+S11`）：组 = 一个 `Z` 行里的 S 集合（`align/` 的 `Z10 = S10+S11`），
回填也按组聚簇切分。逐 S 派发会让 agent 看不到完整语义单元，且**跨 S 交界处的切点无人负责**
（实测极端情形：`S47` 行仅剩 `input power.` 两词，而那处需要的切点正横跨 S46/S47）。

### `candidates/_request/chunk_<k>.md`：派发清单

```markdown
# chunk_001

> 在语义单元边界插入 ` | `（前后各一空格）。已有标点处**不必**标注。
> 候选**宁多勿少**；不得增删改任何词、不得写 `/` 与时间戳。
> `[至少切 N 处]` = 该句中文译文分成了 N 段，英文就至少要在其中切 N 处；**多切不罚**。
> 行首写 `S10+S11` 的 = 这两句译成了同一段中文（合译），**在整行范围内标**。
> 长句 86 / 词 1533

S1  [至少切 1 处] Repeaters and comparators, while being some of the oldest redstone components in the game, are often overlooked…
S10+S11  [至少切 1 处] The side with the torch stub that's not in the track is the output. This is where the repeater will provide power.
```

- 行首 `S<n>` 或 `S<n>+S<m>`（单 S 与 `skeleton.json` 长句编号一致；组与 `align/` 同形）+ **两个空格**
- **不给**停顿位置（脚本本就有语音证据，标出来只会把 agent 引向已覆盖处）与脚本自己的切分结果

### `[至少切 N 处]`：中文切点需求

为何需要：清单**只有英文**，agent 无从判断该长句要切多细；而回填只能按候选切——候选不足时整片吞下，最终字幕中文短、英文一行挤满（实测中文 9 宽而英文片 40.6 宽）。

- **算法**：`r02_results` 同块中文 → 按句末标点切 Z 句 → 中文段数 N = `ceil(中文宽 / HARD_MAX)`；提示值 = **N**
- **粒度 = 合译组**（与清单行一致）：`Z10 = S10+S11` 的两个长句合译成一段中文 → 切点需求是**整组**的，标在组那一行
- **多切不罚**：有裕量时回填按宽度占比挑更贴合的候选；少切才失衡
- 不传 `--r02` / `--align` 则清单不标（仅英文环境的降级）

> ⚠️ **措辞一律用动作**（“切 N 处”）而不用结果量（“N 片”）——后者会诱导 agent 去**数**自己的产出（数错反而更差）。同理不写占比、百分比等需它换算的数字。
> ⚠️ **提示值刻意比真实需求多要一处**（真实需求 = N−1 个切点）：片数对得上而**边界错配**的情形仍需额外候选位；多切不罚、少切则失衡。
> ⚠️ 本标记只能掲开**切点不足**导致的失衡（如中文 3 段而英文只切 2 片）；**切点数相同而边界错配**时（中英逗号位置本就不同）它报不出——那类靠回填的 `r04_alerts.md` **超宽英文片**告警 + `--fix-splits` 定点修复。

### `candidates/reply/chunk_<k>.txt`：子 agent 作答

```
S29  what do you think happens | when I input a pulse that's shorter than the delay the repeater has?
S30  So let's change that, shall we?
S10+S11  The side with the torch stub that's not in the track is the output. | This is where the repeater will provide power.
```

| 项 | 规定 |
|---|---|
| 行首 | **照抄清单行首**：`S<n>` 或 `S<n>+S<m>` + 空白；**每行一行**（不得断成多行、不得把组拆开） |
| 分隔符 | ` \| `（前后各一空格，断在**词间**） |
| 数量 | **宁多勿少**（候选集，不是最终切点） |
| 禁止 | `/`（MC 命令撞车）、增删改词、调序、时间戳、注释 |
| 无需切分 | **原样回抄**（合法作答，非漏答） |

### `candidates/chunk_<k>.tsv`：机器消费

```
# chunk_001	组 86 / 有候选 71 / 候选点 101
S29	510,517	5,12
```

- 第 2 列 = **全局词号**（= 切点**左侧词**在 `words.json` 的 `words[]` 下标，0-based；语义“在该词之后切”）
- 第 3 列 = 句内词号（定稿文本的，与作答一致；便于人工核对）
- **跨块合并消费**（块号只是派发单位，候选点全局有效）
- ⚠️ **定稿可能增删词** → 第 3 列（定稿词号）到第 2 列（原词号）经 **difflib 相似度对齐**；
  落在定稿**新增词**上的切点无原词锚 → **丢弃**

### `candidates/_check_report.md`：校验报告

逐块 `行 / 通过 / 失败 / 候选点` + 失败明细。判据 4 条：S 号存在（不重复 / 不缺失 / 不越界）、
不含 `/`、去分隔符与空白后逐字符等于原句、分隔符落在**词边界**（展开的 token 序列须等于原句 token 序列）。
**失败行不静默采信**（该 S 号记为空候选 → 回填回退纯语音权重）。

## `e0/*`：前置定稿产物

把音频转写的长句收敛为定稿文本（供术语扫描与翻译消费）。设计见
`Project_Plan/2026-10-08_vocalign独立前置设计.md`。

### `e0/_request/chunk_<k>.md`：定稿待办清单

```markdown
## 一、文本仲裁（两套 ASR 不一致处；选一个或另写）
A1  S3
  01      : …everyone, my name is **[Emdy]**
  whisper : …Hello everyone, my name's **[MD]**
  → 作答：`A# = whisper` / `A# = 01` / `A# = <你的文本>`

## 二、可疑停顿补标点（有停顿但词尾无标点；补上应有标点或判为无）
B1  S21  （该句第 12/24 词后）
  …change the delay between the input and ⟨此处无标点，310ms 停顿⟩ output by right clicking…
  （**不确定就判 `无`**；此处只是有停顿，不等于该断）

## 三、非口播注释确认（字幕含无语音对应内容，确认保留并入长句）
C1  S91  注释：`by block, ocelot or cat`（7.1 词/秒，whisper 该时段仅 7 词）
```

- `A#` 来自两套 ASR 的词级差异（形态归一后）；`B#` 来自 `boundaries.txt` 的净停顿；
  `C#` 来自语速判据（词数除以时长超过口播上限，且该时段实测词数明显更少）
- 清单只给人看；apply 用 `_items.json` 的锚点（不解析清单文本）

### `e0/reply/chunk_<k>.txt`：定稿作答

每行 `<key> = <值>`：

```
A1 = 01
B1 = 无
C1 = 保留
A7 = the command it ran
```

| 类 | 值域 |
|---|---|
| `A#` | `whisper` / `01` / **自定文本** |
| `B#` | `,` `.` `?` `!` `;` `:` / `无` |
| `C#` | `保留` / `删` |

### `e0/_items.json`：机器可读锚点

```json
{"A1": {"key":"A1","kind":"arb","s":3,"i1":32,"i2":33,"main":"MD","surf":"Emdy","ctx_main":"…","ctx_01":"…"},
 "B1": {"kind":"punct","s":21,"g":412,"after":"input","before":"output","net":310},
 "C1": {"kind":"note","s":91,"note":"by block, ocelot or cat","head":"A chest that is blocked from opening"}}
```

- `i1/i2` = **skeleton 侧原词号**（半开区间；apply 按此替换）；`g` = 切点左侧词的全局词号；
  `head` = 注释插入点的锚定词序列（apply 用**词序列匹配**定位，不用时间；
  长句边界与 cue 边界不同）

### `e0/long_lines.srt`：定稿 SRT 载体

```
1
00:00:00,740 --> 00:00:08,257
Repeaters and comparators, while being some of the oldest redstone components in the game, …
```

- **cue 号恒等于 S 号** → 依赖 cue 号的现有脚本（`glossary_lookup` / `glossary_load_plan` /
  `text_chunk`）可直接消费，无需改动
- **时间 = 长句语音实测值**（来自 `skeleton.json`）；文本**不折行**（折行会让 `text_chunk`
  插 ` | ` 连接符，引入噪声）
- ⚠️ 本载体绕开的是自动字幕作为**文本源**，不是 SRT 这个容器：内容与时间
  全部来自音频实测（转写加强制对齐），只借用 SRT 字段结构
- `text_chunk.py --type srt` 吃它，块边界必然落在骨架长句边界

### `e0/en_timeline/chunk_<k>.txt`：S 长句与时间

```
S1	00:00:00,740 --> 00:00:08,257	S1	Repeaters and comparators, while being some of the oldest redstone components…
```

- 格式与 reflow2 的 `en_timeline/` 同构（`S<n>\t<时间>\t<范围>\t<文本>`）→ `task-match` 模板与派发链可直接复用
- **按块分装**（供逐块对照），但 **S 号是全局编号**（reflow2 的 E 号为块内局部）
- 块划分由 `--chunks` 的 **OWNED cue 范围**给出（cue 号恒等于 S 号）

### `e0/long_lines.md`：定稿文本

```markdown
# 定稿长句（149 句）
# 含非口播注释 1 处（括号内容无语音对应，属讲解稿补注）：(by block, ocelot or cat)

S1  Repeaters and comparators, while being some of the oldest redstone components in the game, are often overlooked…
```

- **书写层忠实转写原样**，加 LLM 仲裁修正与注释并入（**不是**比对层的归一化形态）
- 头部注明非口播注释，提示翻译环节这些括号内容无语音对应

### `e0/_changes.tsv`：改动审计

```
# S号	改动类型	骨架原文	定稿
3	punct+replace	Hello everyone, my name's MD and welcome back…	Hello everyone, my name's Emdy and welcome back…
```

- 逐条列出定稿相对骨架原文的改动（S 号 / 改动类型 / 原文 / 定稿），供**人工复核**
- 对比 reflow2 的措辞校验：本工作流**允许**改词（仲裁是核心功能）→ 不做硬校验，改为**逐条可核**

## `align/chunk_<k>.txt`：Z 与 S 语义对应

```
Z5+Z6+Z7+Z8 = S5
Z2 = S2
```

- 由 `task-match`（`--skill vocalign`）产出；输入 = `e0/en_timeline/` 加 `zh_sentences/`
- 以 reflow2 的 `align/` 为原型，但 S 为**全局编号**
- 回填消费：`vocalign_backfill.py --align <dir> --e0 <dir>`（S 时间从 `e0/long_lines.srt` 取）

## `consistency/chunk_<k>.txt`：机制断言疑点清单

```
# 机制断言自洽性复核（块内对立扫描）
S12\tS40\t红石导体与红石线\t前者称导体能传电，后者称不能
```

- 由复核子 agent（`task-consistency`，`--skill vocalign`）产出；输入 = `e0/en_timeline/`
- 4 字段 TSV：句号 A / 句号 B / 对立主题（≤20 字）/ 冲突说明（≤60 字）
- 无矛盾 → 第二行单独写 `无矛盾`（与疑点行**互斥**）
- 校验：`srt_reflow2_check_consistency.py <dir> --etimeline <e0/en_timeline> --id-prefix S`
- **只做文本内部一致性比对**，不判断哪句符合游戏机制——疑点由阶段五人工裁决

## `r04_*`：交付稿

格式与 reflow2 一致（见 [`PRODUCT_FORMATS_REFLOW2.md`](PRODUCT_FORMATS_REFLOW2.md) 的 r04 节），
差异仅在**时间来源**：

- 每段的 `start` / `end` = 对应英文片的**语音实测词边界**（段时长不足 1s 时借相邻空隙延长，不改切点）
- 对应关系 = **自产 `align/`**（`Z<n> = S<m>`）；中英语序会交叉，不可按序一一对应
- 英文切点 = 全词边界候选加惩罚阶梯（标点与长停顿 0，短停顿 20，候选点 60，无证据 200）
- 假空隙降级：无标点、靠停顿当证据的边界，若**附近有对齐可疑词**（`words.json` 的 `score` < 0.3）
  → 判为假空隙（惩罚同“无证据”），因为该空隙来自音素对齐失败而非真停顿

`r04_alerts.md` 含：块数 / 中文段数 / **切点来源统计**（punct / fix / sent-pause / clause-pause /
candidate / lowconf / none）/ 无证据切点清单 / **假空隙位置清单** / 定点修复未命中清单 /
**超宽片清单**（甲/乙分节）/ 段时长不足清单 / 逐块告警 / 校验失败项。

### `lowconf`：假空隙位置

whisperX 的音素对齐会在个别词上失败（实测几乎全是数字词，`words.json` 记 `n_unaligned`）→ 该词
`start` 被推后、相邻词的 `score` 极低，中间多出一段**无处安放的空隙**。

```
788  uses          235.117 → 235.418   +140ms   score 0.872
790  signal        235.719 → 235.920   +60ms    score 0.407
791  comparison,   237.020 → 237.201   +1100ms  score 0.595   ← 空隙实在这里
792  container     237.221 → 237.422   +20ms    score 0.108   ← 对齐失败
```

若不剔除，回填会把它当**零惩罚强切点**（与标点同级）→ 空隙落在段与段之间 →
播放时前条消失、后条未出现，空白 1.1s（超出 `srt_fill_gaps.py` 的 1s 阈值）。

- 判据：无词尾标点、净停顿 ≥ 500ms，且边界前后各 2 词内有 `score` < 0.3
- 实测标定：全片 4 处“无标点且 gap ≥ 1s”中命中 3 处；第 4 处窗口内最低 `score` 0.539（真停顿）不命中
- 剔除后 DP 会改选**有证据**的位置（实测 4 处零惩罚切点 → 3 处候选点 + 1 处标点，**无一退到 `none`**）
- 只降级**判定**、不动任何时间戳（仍守“时间取语音实测”）

**超宽英文片**（英宽 > 硬限 **且** 英/中宽比 ≥ 2（正常片约 1.5））——成因两类，**处置不同**：

- **甲 切点错位**：该 S 组中文已分 ≥2 段（英文片位足够），只是 DP 把切点放偏 → 可 `--fix-splits` **定点修复**
- **乙 片数不足**：该 S 组中文**只 1 段** → 回填直接令英文 1 片（**不跑切分 DP**）
  → 定点修复与补候选点**均无效**，须回中文译文侧补句内标点使其分 2 段

**超宽中文段**（中宽 > 硬限）= **中文侧**问题（分段未拆到限内）→ 回中文译文侧收窄措辞或补句内标点

两类成因的判定与切片选点，见回填自动产的 `_fix_splits.draft.md`（下节）。

> ⚠️ 为何不单用“英宽 > 硬限”：硬限是**中文**（1.0/字符）的尺，英文按视觉宽（0.4/字符）
> 本就比中文大（正常片英/中 ≈ 1.3）——单判会报出四成片为“超宽”（全是误报）。

### `_fix_splits.tsv`：定点修复切点

回填报出**超宽英文片**后，重跑整个候选点环节（派 subagent）代价高；而问题往往只是个别处——
人工/agent 只针对那处写一行修复，重跑回填即可。

```
# S号	切点两侧词（左 | 右）
S69	useful | to
```

- **锚 = S 号 + 相邻两词**（不用词号：词号随 E0 增删词漂移，不稳）
- **定位** = 在**该 S 时间范围内**的词序列中找该相邻词对（去标点、不区分大小写）；
  命中不唯一或未命中 → 记入 `r04_alerts.md` 的“定点修复未命中”节（**不静默**）
- **效力** = 零惩罚切点（与标点同级）→ DP 必定采用；回填报告单列 `fix` 计数与采用数
- 用法：`python scripts/vocalign_backfill.py ... --fix-splits <work>/vocalign/_fix_splits.tsv`

> ⚠️ 该机制只能**在已有词序列内选切点**——若英文词序列本身缺词（转写幻觉所致），
> 应先按 `segments.suspect.md` 处置重跑采集，定点修复治不了缺词。

### `_fix_splits.draft.md`：定点修复待裁决草稿

回填**每次自动产**（仅当报出超宽英文片时）；**不参与回填**，是给人裁决用的信息整理。
每处超宽片一节：片号 / S 组（合译组写 `S94+S95`）/ 片宽与倍率 / 中英文本 / **成因判定** /
（甲类）该片内**每个**切点的候选表。

甲类候选表由**模拟重跑该 S 组**得出——把该切点当零惩罚切点加进去，报告切后各片宽度：

| 切点（本片内） | 证据 | 抄进 tsv 的行 | 本片 英/中 | 组内最大 英/中 |
|---|---|---|---|---|
| comparator | into | candidate | `S41	comparator \| into` | 1.00 | 1.86 |

- 按**组内最大比例**升序（最小化最坏情况：只压本片会把问题转给同组别片）
- 推荐行标注是否**全部片达标**；“仍不达标”= 该片内切点已**穷举**，须回候选点环节补候选或接受
- 单元格内那行与 `_fix_splits.tsv` 同形（制表符分隔）——直接整行复制即可

## `segments_patched.srt` / `patch_report.md`：可疑点重识别拼接稿

`vocalign_collect.py` 在 `--patch-pad N`（**默认 ±20s**，0 = 关闭）下自动执行：转写，探测可疑段，
对每个可疑点取 ±N 秒**单独重识别**，再与全片稿**拼接**。

**为何能消幻觉**：whisper 的 `condition_on_previous_text` 把前文带进解码 → 偶发重复幻觉。
切片重识别时**块内保留前文**（保住标点）、**块间重置**（截断污染累积）——实测既消幻觉又保住标点。

```
全片稿（含幻觉）
  57.60→58.00  This is the red track.                                  ← 幻觉（0.4s / 55 字符每秒）
  58.00→59.60  This is where the repeater will provide power.

拼接稿（替换区 [53.0, 66.6] 被重识别内容接管）
  55.82→62.54  the track is the output. This is where the repeater will provide power. …
```

### 替换区边界与拼接

- **边界取可疑点两侧最近的句末标点**（距离在 3–16s 内）——落在句界才不会把一句话劈成两半
- **边界优先级**：两版都有段边界的（`paired`）＞ 仅全片版（`strong`）＞ 仅重识别版（`alt`）＞ 固定 ±8s（`fallback`）
- **接缝去重**：两版段边界不可能完全重合（时间戳偏差 p90 0.42s），于是接缝两侧各取一个同时段的段，
  同一句会出现两遍。处置：定向（仅在窗口边界 ±2s 内）删去**后段的重复开头**，并逐条入报告
- **自检**：时间倒挂 / 接缝重复 / 兜底边界 / 跨界段丢弃 均入报告（**不静默**）

### 差异清单与裁决门禁

`patch_report.md` 的**差异清单**只列两版文本不同处（比对前已归一：分词与数字写法，
`right-clicking` = `right clicking`、`two` = `2`）——**未列出的内容两版一致**，不必读全文。

| 窗口 | 可疑点 | 差异 | 状态 | 摘要 |
|---|---|---|---|---|
| 1 | 00:00:58 | 3（+1 接缝） | 保留补丁 | 删“This is the red track.”；改“the repeat”→“repeater” |
| 5 | 00:10:54 | 0（+2 接缝） | 保留补丁 | （仅接缝副作用） |

- 差异按 **`删 / 增 / 改` 三态**给出（“补丁版相对全片版”的改动）——三态比“哪版有”好读：
  同一处的删与增已配成一条 `改“旧”→“新”`
- 标 `〔接缝〕` 者为替换区两端附近的差异，多为拼接副作用（去重 / 两版边界不重合），**非内容改动**
- 每窗口附**折叠**的两版全文对照（`<details>`），需深查时再展开

### `patch_decisions.tsv`：裁决表

门的落地物：把要**回退为全片版**的窗口写进去（未列默认 `keep`），带 `--patch-decisions` 重跑，
窗口转写有缓存（`patch_windows/`）→ **秒级重拼**。

```
# <窗口号>	<keep|revert>
6	revert
```

### 验收与局限

- **报告逐窗口给出“全片版原内容 / 重识别内容”对照** —— 必须人工核对
- ⚠️ **非万灵药**：窗口内是**全新解码**，可能在非可疑处引入新错
  （实测：`Copper bulbs` 被改成 `Lava bulbs`，后者非游戏内方块）
- ⚠️ **会改 S 编号**（实测 151 变 153，差异从首个替换区所在长句开始），下游需重跑；
  对照全片切片（151 变 136）漂移小得多
- 实测（PRR2，772.6s）：可疑段由 8 降到 1、耗时 22s、时间倒挂 0 处

## `<名>.filled.srt`：空隙填充后的交付稿

相邻段间隙 < 1s 时把前段 `end` 延到后段 `start`（首尾相接），消除播放时“前条消失、后条未出现”的闪烁。工具 = `scripts/srt_fill_gaps.py`。

```
原稿  c1  00:00:00,740 --> 00:00:04,418        ← 与 c2 间隙 503ms
      c2  00:00:04,921 --> 00:00:08,257

填充  c1  00:00:00,740 --> 00:00:04,921
      c2  00:00:04,921 --> 00:00:08,982
```

- **只改 `-->` 之后的结束时刻**，起始时刻与编号 / 文本原样保留
- 间隙 ≥ 阈值（默认 1000ms）保留：那是真实停顿或剪辑跳转，覆盖会吃掉静默语义
- 首段不填（无前段）、末段不填（无后段）；中英双语稿时间戳同行共享，无需分别处理
- **不覆盖原稿**（默认产 `<名>.filled.srt`）；`--in-place` 可原地覆盖

> ⚠️ 本步**主动偏离语音实测时间**（多出的是静默段）——是 vocalign“时间取语音实测”的**唯一例外**，
> 故独立成脚本、与 r04 分开产出（观感后处理可事后重跑或跳过）。
> ⚠️ 它**不修**时间重叠；遇重叠仅告警（属上游回填问题）。
