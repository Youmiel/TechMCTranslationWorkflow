---
name: redstone-preprocess
description: 红石字幕翻译前置——字幕机械修复（阶段〇）+ 加载集判定与准备（阶段一）+ 术语扫描与知识补齐（阶段二），产出干净时间轴（00）、ASR 修正字幕（01）与确认术语表（02）。
---

# 红石字幕翻译前置（redstone-preprocess）

> 定位：翻译前的**字幕机械修复 + 领域预判 + 术语补齐**（阶段〇 / 阶段一 / 阶段二），产出干净时间轴、ASR 修正字幕与确认术语表，供翻译阶段使用。

## 输入 / 输出

| 产物 | 时机 | 内容 | 恢复价值 |
|------|------|------|----------|
| `<工作目录>/00_subtitle_snapped.srt` | 阶段〇（脚本，机械修复） | 结构清理（重叠/倒序顺延）+ 时间轴吸附后的字幕（**文本逐条未改**、cue 数不变） | 避免重复机械修复；**全工作流时间轴新基准** |
| `<工作目录>/01_subtitle_asr_fixed.srt` | 第一次遍历后（subagent 分块派发 + 合并） | ASR 修正 + 游离单词归位的英文字幕（**时间码照抄 00**、不增删 cue） | 避免重复 ASR 解码 |
| `<工作目录>/02_terms.md` | 术语确认后 | 确认后的术语映射表（时间戳/原文/译名/来源/ASR 修正） | 翻译唯一译名依据，跳过整个阶段二 |

> 产物结构/格式/标记约定（单一权威）见 [PRODUCT_FORMATS](../../../docs/PRODUCT_FORMATS.md)；处理前先查对应节，勿现查代码猜格式。

## 依赖

`use-glossary` · `term-scan` · `term-registration` · `subagent-dispatch` · `csv-rules` · `wiki-tools` · `segment-subtitles` · `redstone-conventions` · `maintain-knowledge`

## 注意事项

- **环境**：见 [redstone-conventions#环境](../redstone-conventions/SKILL.md#环境)
- **CSV**：按 [csv-rules](../csv-rules/SKILL.md)（`utf-8-sig` 读 / `utf-8` 写、`csv` 模块解析、脚本勿 `python -c` 内联）
- **ASR**：YouTube 自动生成字幕可能不可靠，先解码再翻译。
  - 解码查全局 asr_fixes，未命中查本视频局部
  - 登记分层：通用→全局表，专属→局部

## 阶段〇：字幕机械修复

> **为什么在最前**：输入（YouTube 自动字幕）带两类与内容无关的缺陷——**结构**（重叠/倒序 cue）与**时间轴**（按显示节奏生成、边界落在词与词之间）。两者都不需要领域知识，越早修，下游（空隙探测 / 分块 / 补标点 / 锚定）越不会吃进坏边界。
>
> **与术语扫描的分界（必须遵守）**：本阶段**绝不动文本**——ASR 误识别修正需要门禁加载的词汇表 / `asr_fixes` 作先验（见 [阶段一](#阶段一加载集判定与准备) 第 6 步），属语义判断，留 [阶段二](#阶段二术语扫描与知识补齐) 的术语扫描。

1. **跑机械修复**：`python scripts/srt_mech_fix.py <原始ASR.srt> -o 00_subtitle_snapped.srt [--audio <音频> | --video <视频>]`
   - **结构清理**：重叠/倒序 cue 顺延（只调 `start`，`end` 更可信）；异常时长仅告警不自动改（改时长会破坏语义边界）
   - **时间轴吸附**（有音频才做）：边界吸附到语音能量谷，**起终点分向**以保留 cue 间隙——间隙是 reflow 空隙探测的唯一输入
   - **音频自动探测**：`--audio` → `--video` 同名音频 → 容器音轨 → 输入目录内音频文件；**无音频则跳过该步**，其余照常（保持“纯文本可跑”）
2. **读不变量自检**（脚本已写入报告首节，未过时脚本退出码 1、**不产出产物**）：cue 数不变、文本逐条不变、每条 `start < end`、无重叠无倒序、**吸附后 cue 间隙守恒**
3. **产物**：`<工作目录>/00_subtitle_snapped.srt`（脚本不指定 `-o` 时仅出报告）
4. **后续基准**：第一次遍历的分块与合并输入、`01` 的 `--cue-exact` 对照物**均改用 `00`**（见 [阶段二](#阶段二术语扫描与知识补齐)）

> 报告默认落 `<工作目录>/speech_align/mech_fix_report.md`（不依赖 cwd）。

## 阶段一：加载集判定与准备

1. **刷新本地知识**：`python scripts/refresh_cache.py`（统一入口：Mojang/TechMC 自动刷新，**Wiki 只告警不自动抓取**——Wiki 过期页由查证/查询时主动刷新（`--check-page` 判定 → `fetch_wiki.py --refresh`），见 [wiki-tools](../wiki-tools/SKILL.md)；或按需 `glossary_split.py --check`、`glossary_fetch_mojang.py`）
2. **定加载集（常驻 + 命中数候选 + 用户门禁）**：跑 `python scripts/glossary_load_plan.py <字幕.srt>`（用 `00_subtitle_snapped.srt`）；实际常驻表用 `--list-resident` 查
   - 脚本自动：**常驻集无条件加载** + 用字幕扫全部非 L1.5 表 → **命中词条数 ≥3 的表列为候选**（附命中数、命中样例、未达阈值全貌）
   - **必须把报告报用户门禁确认**，由用户剔除非必要表；裁定后跑 `--record "<剔除的表>"`（候选全保留则 `--record`）
   - 门禁**自动写日志** `glossary_gate_log.md`（探测范围 → 用户决策，供调阈值）
   - **不读 `glossary_categories.yaml` 判类别**（其 keywords 覆盖面与字幕实际用语脱节）；报告见 [use-glossary#加载集判定](../use-glossary/SKILL.md#加载集判定)
   - **不得静默跳过门禁**
3. **L1.5 按需查询**：`.cache/mojang/redstone.csv`（归 L1，已入常驻集）；`.cache/mojang/blocks.csv`、`items.csv`、`entities.csv`、`misc.csv`（归 L1.5，**不注入 ASR 通道**——含 `water`/`thing` 类通用词会稀释注意力并诱发误纠）→ **L1 未命中时按需 grep 查询**，不整体加载
4. **加载知识地图**：读 `indexes/knowledge/` + `indexes/repos/_manifest.md`（机制知识卡 `knowledge/02_mechanic/`、外部仓库经索引定位）
5. 读 `docs/SOURCE_COVERAGE.md`（各数据源擅长/不擅长）
6. 读全局 `.github/experience/asr_fixes.md` + 本视频局部 `_work/<视频名>/asr_fixes.md`（准备 ASR 解码）

## 阶段二：术语扫描与知识补齐

### 2.1 术语扫描

> 机制见 [term-scan](../term-scan/SKILL.md)（权威：子任务拆法 + 任务文件导航；术语识别块输出格式在 `task-term-recognition.md`）、[use-glossary#术语源优先级](../use-glossary/SKILL.md#术语源优先级)；长视频分块见 [redstone-conventions#长视频分块](../redstone-conventions/SKILL.md#长视频分块)（通用机制）。
> **派发边界**：第一次遍历（英文预整理）与术语识别**一律派 subagent**（每块一个，块数由骨架决定），无需报告策略——见 [subagent-dispatch#派发边界](../subagent-dispatch/SKILL.md#派发边界)。
>
> 主会话只做：
> 1. 定 N（`context_estimate.py`）
> 2. 分块（`text_chunk.py`）
> 3. **扫 ASR 触发清单**（`asr_trigger.py scan`，纯脚本、无状态）
> 4. 渲染 prompt（`render_preprocess_prompt.py`）
> 5. 派发
> 6. 合并
> 7. 校验（含 `asr_check_trigger.py` 清单覆盖率）
> 8. 汇总

1. **加载术语表（两个通道不同，勿混）**：
   - **ASR 纠错通道**（阶段一第 2 步产出）：显式清单 = **常驻集 + 门禁后保留的候选**，
     经 `render_preprocess_prompt.py --glossary <csv...>` 注入（见下方第一次遍历）；
     只注 **L1 + L2**，**L1.5 不注**（含通用词，稀释注意力且诱发误纠）
   - **术语扫描通道**（阶段二第 3 步 `glossary_lookup.py scan`）：**L1 始终全量**（无参数可限），
     **L2 按 `--categories <文件名>` 显式指定** = 门禁后保留的 L2 表（附常驻 `general`）
   - **门禁只影响注入面，不改变扫描通道的 L1 全量行为**——L1 表短且库小，全量无害；
     L2 宽表才是需要门禁筛的对象
2. **第一次遍历（英文预整理，分块派 subagent）**，产出 `01_subtitle_asr_fixed.srt`：
   - **定 N + 分块（派发必经第一步，勿整条读字幕）**：
     1. `python scripts/context_estimate.py <00_subtitle_snapped.srt> --no-amplification` 定 `--owned`
     2. `python scripts/text_chunk.py <00_subtitle_snapped.srt> --type srt --owned <N> --ctx <M> --out _en_chunks/`
   - **扫 ASR 触发清单（分块后、渲染前，必跑）**：
     `python scripts/asr_trigger.py scan <00_subtitle_snapped.srt> --video <工作目录>`
     → 产出 `asr_trigger/triggers.tsv`（变体 → 完整正确词形 + 层级，纯脚本、无状态、零算法风险）
     - 把“发现怪词”从**注意力驱动**改为**清单驱动**——实测该环节是主瓶颈（缺失项中 69.8% 属“长文本里没注意到”）
     - **必须带绑定**（`变体 → 正确词形`）；注入裸词条会退化（实测会丢词）
     - 无此产物时渲染脚本**直接报错**（不得缺省——“缺清单”会被读作“免检”）
     - 分层：M 多词（误报 3%）/ S 单字非停用词（高价值）；X（单字停用词）默认不列（误报 96%）
   - **派发**：
     1. 渲染：`python scripts/render_preprocess_prompt.py task-en-preprocess --video <工作目录> --all --glossary <L1/L2 csv...>`（渲染脚本自动注入 ASR 触发清单（按块 OWNED 过滤）+ asr_fixes 全局+局部 + 领域术语集；见 [subagent-dispatch#派发配方](../subagent-dispatch/SKILL.md#派发配方)）
     2. 逐块派 subagent：任务文件 = `term-scan/task-en-preprocess`，结果写 `_work/<视频名>/_en_results/chunk_<k>.srt` + `chunk_<k>.asr.tsv`（ASR 修正清单）
   - **合并**：`python scripts/srt_join_parts.py _en_results/ --out 01_subtitle_asr_fixed.srt --chunks _en_chunks/`（各块 SRT 片段按块序拼接 + 全局段号重排；cue 数 = OWNED cue 数强制校验）
   - **立即校验时间轴**：`python scripts/srt_check_segments.py 01_subtitle_asr_fixed.srt --orig 00_subtitle_snapped.srt --cue-exact`
     - 01 只改文本、**时间码逐条照抄 00**、不增删 cue
     - 时间轴错位立即回本步修正（否则一路传最终稿）；默认只给问题数，`--expand` 看明细，缺失 cue 定位用 `--missing-ctx 1`
   - **校验清单覆盖率（闸门）**：`python scripts/asr_check_trigger.py --video <工作目录>`
     - 清单每项必须有决策（修正 `[ASR]` 或放行 `[放行]`）；**未处理项退出码 1 = 打回**
     - 单块修复后只查该块：`--chunk <k>`（默认展开详情）；`--expand` 展开明细
     - 来源口径不符（如仍写 `[ASR 推测]`）与“改后未登记”为**提示级**，不拦
   - **字幕缺失定位（--missing-ctx）**：cue 数不一致（字幕缺失/多余）时脚本默认只报缺失/多余总数；追加 `--missing-ctx 1` 输出每条缺失 cue 的标号+时间+文本+上下句（agent 直接定位、无需自写定位脚本；默认关闭，防输出过多挤爆上下文）
   - **ASR 推测登记**：汇总各块 `.asr.tsv`（触发清单 `[ASR]`/`[放行]` / 映射命中 `[ASR]` / 联想 `[ASR 推测]` / 未定 `[待审核]`）。
  - 跨视频通用 → 全局表
  - 视频专属 → 局部 `asr_fixes.md`
   - **跨行合并成整句 / 合并时间戳是阶段三的重活，此处不做**（translate 走两遍式断句；reflow 走回填的空隙探测 + 补标点）
3. **机械查找**：`python scripts/glossary_lookup.py scan <01> --categories <门禁后的 L2 表名> --levels L1,L2 --out scan_terms.txt`，命中项无论像不像术语一律按登记译名处理（L1 始终全量；L1.5 默认不扫）
4. **术语识别（派 subagent）**：
   1. **定 N**：`python scripts/context_estimate.py <01> --no-amplification`（**预测阈值，不使用放大倍数参数**）
   2. **分块**：`python scripts/text_chunk.py <01> --type srt --owned <N> --ctx <M> --out _term_chunks/`
   3. **渲染派发 prompt**：`python scripts/render_preprocess_prompt.py task-term-recognition --video <工作目录> --all --scan <scan_terms.txt>`（自动注入 scan 命中项按块过滤 + 陷阱词清单 + 领域术语集 + ASR 修正映射）
   4. **逐块派 subagent**：任务文件 = `term-scan/task-term-recognition`，结果写 `_work/<视频名>/_term_results/chunk_<k>.txt`（执行一律 subagent，见 「redstone-conventions#长视频分块」）
5. **主会话汇总**：按 `term_en` 合并去重；`[ASR 推测]`/`[推断]`/`[待审核]` 行保留**首次时间戳**（格式 `HH:MM:SS`，取字幕时间码精确值）；L3 未命中进 [集中补齐](#22-集中补齐)
6. **未加载表漏刷回记**：译/扫/查词时命中**未加载表**里的词且确实需要 → 报用户补充加载，并记入 `glossary_gate_log.md` 备注（供调阈值，见 [use-glossary#运行中反哺加载集修正](../use-glossary/SKILL.md#运行中反哺加载集修正)）

> subagent 任务规则见 `term-scan/task-en-preprocess`（第一次遍历）与 `term-scan/task-term-recognition`（术语识别）（现成任务文件；prompt 由 `scripts/render_preprocess_prompt.py` 渲染，派发配方见 [subagent-dispatch#派发配方](../subagent-dispatch/SKILL.md#派发配方)）。

### 2.2 集中补齐

> 翻译前一次性完成所有网络请求，查证 agent 分批派发。
>
> 机制（缓存判定 / fidelity / 降级链 / **过期判定与主动刷新** / 请求纪律 / 缓存写入）见 [wiki-tools](../wiki-tools/SKILL.md)（权威）；数据源选择参考 `docs/SOURCE_COVERAGE.md`。
> - **查证由 `term-researcher`（研究型 agent）分批派发**——命中缓存后**必先判定过期，过期则主动刷新再读**（`refresh_cache.py --check-page` → `fetch_wiki.py --refresh`）
> - 主会话只做：汇总待查列表、分块、逐块派发（任务文件即 prompt，双引用）、读各块结果、合并、更新映射
> - **主会话不读 wiki 页面全文**（页面只进查证 agent 一次性上下文，返回每词一行压缩总结——token 纪律，见 [subagent-dispatch#主会话读写最小化](../subagent-dispatch/SKILL.md#主会话读写最小化)）
> - **事后（阶段三及以上）临时需请求 Wiki**（机制细节/数值核对/版本行为）：同样先查缓存 → 过期判定 → 主动刷新；需阅页面的查询派 `wiki-researcher`（任务文件 `wiki-tools/task-wiki-query.md`，产物 `wiki_pending_<i>.md` → `wiki_resolve_<i>.md`）

1. **主会话写待查列表**（[术语扫描](#21-术语扫描) 第 5 步合并去重后）：`_work/<视频名>/term_pending.md`，每行 `term_en | 首次时间戳 | 已给候选/依据`（L3 未命中 + 决策行）
2. **分块（条数多必分，防研究 agent 推理截断）**：待查列表按 **30 条/块** 拆成 `term_pending_<i>.md`（块内保持原行格式；`term_pending.md` 保留全量作审计）。块数 = ⌈条数÷30⌉
3. **逐块派发（任务文件即 prompt，双引用）**：每块派一个 subagent（agentName = `term-researcher`，研究型 agent），派发引用给两个路径：
   - 任务文件 `.github/skills/term-scan/task-term-resolve.md`（= 完整 prompt，含查证链 / 抓取纪律 / 输出契约）
   - 该块待查列表 `_work/<视频名>/term_pending_<i>.md`
   - subagent 先读两者再执行；**不追加执行型纪律母版**（研究型纪律由 agent 系统提示词承载，见 [subagent-dispatch#派发边界](../subagent-dispatch/SKILL.md#派发边界)）
   - **串行派发**——上一块 `term_resolve_<i>.md` 写盘后再派下一块（断点恢复粒度 = 块）
4. **读查证结果 + 合并**：各块查证 agent 写盘 `term_resolve_<i>.md`（每行 `term_en|候选译名|数据源|依据|[标记]`）+ 返回压缩总结（每词一行）；主会话合并各块 → 汇总（供 [术语确认](#23-术语确认)），据此更新内存术语映射表（`[待审核]` 进确认环节）
5. **断点/审计**：`term_resolve_<i>.md` 即查证产物契约（数据源命中统计是阶段六 coverage_log 依据，见 `redstone-finalize`）

### 2.3 术语确认

输出术语清单供用户确认，**ASR 误识别单独一栏**集中批注。**决策行（`[ASR 推测]`/`[推断]`/`[待审核]`）必须附字幕时间戳**；普通行同样填写；判定为通用标准译名的词在来源列标 `[通用词]`（确认后不入库，见 [术语入库](#24-术语入库)）

```
| 时间戳 | 原文 | 译名 | 来源 | ASR 修正 |
|---|---|---|---|---|
| 00:12:34 | Comparator | 比较器 | knowledge/ | — |
| 00:07:12 | sorder | 分类器 | [ASR 推测] | sorter |
| 00:09:20 | piston phase offset | 活塞相位偏移 | [推断：视频上下文] | — |
| 00:21:03 | Sub-tick | [待审核] 候选：亚刻（据 sub-tick 字面 + 游戏刻语境推测） | 未找到 | — |
```

- `[推断]`：Agent 从对白推测，用户重点确认；`[待审核]`：附候选 + 依据，确认或否决，不默认保留原文
- `ASR 修正` 列：列原始误识别词，可一次确认/纠正全部推测
- **时间戳列**：取首次出现处 `HH:MM:SS`（**从字幕时间码精确读取**，不是 cue 编号、不是凭记忆推算；SRT 时间码 `HH:MM:SS,mmm` 去毫秒即得），决策行缺失视为不完整输出
- **落盘**：确认后写 `02_terms.md`（[术语入库](#24-术语入库) 前）

### 2.4 术语入库

按 [term-registration#同步步骤](../term-registration/SKILL.md#同步步骤)：
1. 筛选已确认术语（排除 `[待审核]`）
2. **通用标准译名过滤**：判定为通用学科公认标准译名的词（如 bilinear interpolation 双线性插值、quicksort 快速排序、Perlin noise）标 `[通用词]` 且**不入库**（判定准则见 [term-registration#通用标准译名判定](../term-registration/SKILL.md#通用标准译名判定)）
3. 写 `_uncategorized.csv`（查重不覆盖）
4. ASR 映射登记 `asr_fixes.md`

`_uncategorized.csv` 变动不更新 `indexes/knowledge/`（纯静态索引，见 `indexing-rules`）。
