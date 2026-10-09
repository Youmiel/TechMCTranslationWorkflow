# 产物格式规范 — vocalign（语音对齐骨架驱动）

> 通用约定（编码 / 折行 / 符号分工 / 变更同步清单）见 [`PRODUCT_FORMATS.md`](PRODUCT_FORMATS.md)。
> 共享产物（`00` / `01` / `02` / `term` / `wiki`）见同文件的共享产物章节。
> 设计依据见 `Project_Plan/2026-10-08_vocalign独立前置设计.md`。

## 本工作流产物速查

| 产物 | 生成者 | 消费 / 校验 |
|---|---|---|
| `vocalign/segments.srt` | `vocalign_collect.py` | 人工核标点质量 |
| `vocalign/words.json` | `vocalign_collect.py` | `vocalign_skeleton.py` |
| `vocalign/skeleton.json` | `vocalign_skeleton.py` | `vocalign_text.py` / `vocalign_candidates.py` |
| `vocalign/skeleton.txt` · `boundaries.txt` | 同上 | **人工抽查**（骨架质量）/ **人工调参**（判据明细） |
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
| `vocalign/collect_report.txt` | `vocalign_collect.py` | 耗时 / 规模诊断 |

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
 "n_words": 2558, "n_sentences": 149, "n_clauses": 263,
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
- `low_conf_bounds`：无标点加短停顿（250–500ms）的边界，**真伪混杂**（如 `works | so` 为真、
  `a | game` 为伪），须人工或 LLM 裁决；脚本**只标注不降级**

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

### `candidates/_request/chunk_<k>.md`：派发清单

```markdown
# chunk_001

> 在语义单元边界插入 ` | `（前后各一空格）。已有标点处**不必**标注。
> 候选**宁多勿少**；不得增删改任何词、不得写 `/` 与时间戳。
> `⋯<ms>⋯` = 该词边界处实测净停顿（仅 ≥250ms 标注；仅供参考，**不是判据**）。
> 长句 86 / 词 1533

S1  Repeaters and comparators, while being some of the oldest redstone components in the game, ⋯463ms⋯ are often overlooked…
```

- 行首 `S<n>`（与 `skeleton.json` 长句编号一致）+ **两个空格**
- `⋯<ms>⋯` = **净停顿**（仅 ≥250ms；`why=interp-skip` 的插值边界不标）
- **不给**脚本自己的切分结果（避免引导“微调”而非“重判”）

### `candidates/reply/chunk_<k>.txt`：子 agent 作答

```
S29  what do you think happens | when I input a pulse that's shorter than the delay the repeater has?
S30  So let's change that, shall we?
```

| 项 | 规定 |
|---|---|
| 行首 | `S<n>` + 空白；**每句一行**（不得断成多行） |
| 分隔符 | ` \| `（前后各一空格，断在**词间**） |
| 数量 | **宁多勿少**（候选集，不是最终切点） |
| 禁止 | `/`（MC 命令撞车）、增删改词、调序、时间戳、注释 |
| 无需切分 | **原样回抄**（合法作答，非漏答） |

### `candidates/chunk_<k>.tsv`：机器消费

```
# chunk_001	长句 86 / 有候选 71 / 候选点 101
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

`r04_alerts.md` 含：块数 / 中文段数 / **切点来源统计**（punct / sent-pause / clause-pause / candidate / none）
/ 无证据切点清单 / 段时长不足清单 / 逐块告警 / 校验失败项。
