# 脚本

按用途**分表**：词汇表/术语 · ASR 修正 · 字幕通用 · 长视频分块与合并 · 各字幕工作流（translate / reflow / reflow2）专用 · 编排渲染 · 数据源与缓存 · 文档一致性 · 环境。
文件名前缀标识类别（`glossary_` 术语词表、`asr_` ASR 修正链路、`srt_` 字幕工具、`text_` 通用文本分块/合并、`srt_reflow_` / `srt_reflow2_` 对应回填工作流）；无前缀者为跨工作流通用或独立工具。**跨表多用的脚本**（如 `srt_check_terms` / `srt_join_parts`）收在最先使用它的表内，其余表不再重复。

**目录约定**：本目录（`scripts/`）只放**工作流与维护会用到的工具**（有 CLI 入口）；
不含 CLI 的**共享模块放语义文件夹**——
`shared/`（跨工具共享：`srt_common.py` 字幕公共层——含**跨语言通用标点角色表**、`asr_common.py` ASR 修正链路公共层、`request_identity.py` 请求身份、`glossary_sources.py` **术语源适配层**）、
`srt_reflow_core/`（reflow 实现包，含断句引擎 `punct.py`）、`mojang_glossary/`（Mojang 词表实现包）。
**`_dev/`**（开发分析工具，**非工作流依赖**——见下方专节）。
导入方式：工具内 `from shared.srt_common import ...`（**绝对导入**——包存在顶层/包内两种导入路径，
相对导入 `..shared` 在顶层路径下会越界；`scripts/__init__.py` 已把 `scripts/` 追加进 `sys.path` 兜底）。

**脚本编写约定**：

- **主逻辑必须包在 `def main()` + `if __name__ == "__main__":` 内**——可运行工具虽以 CLI 为主，
  但顶层裸露的可执行语句会让 `import` 产生副作用（argparse 报错并 `sys.exit(2)`，或直接执行完整
  计算并打印）。模块级只留 import / 常量 / `def`；被模块级函数引用的 argparse 派生变量，优先把
  该函数一并收进 `main` 内。

## 词汇表 / 术语工具

| 脚本 | 用途 | 用法 |
|------|------|------|
| `glossary_split.py` | 将上游合并术语 CSV 按类别拆分到 `.cache/glossary/` | `python scripts/glossary_split.py [--check\|--help]` |
| `glossary_fetch_mojang.py` | 从 Mojang 官方 API 下载最新翻译词汇表 | `python scripts/glossary_fetch_mojang.py [--check]` |
| `glossary_lookup.py` | 按 L1→L1.5→L2 查术语中文译名（只读） | `python scripts/glossary_lookup.py <term> [<term> ...]` |
| `dictionary_lookup.py` | 查 `_repos/storage-archive` 存储科技术语词典（词→英文定义/条目，L2 社区源；与 `glossary_lookup` 正交：**定义 vs 译名**） | `python scripts/dictionary_lookup.py query <term>` / `scan <srt>` / `list` |
| `glossary_hit_rate.py` | **术语表命中率回测（长期维护、可定期重跑）**：以历史视频为语料统计每张表该不该加载。两个口径——**离线全量重扫**（拿当前全部词汇表重新匹配完整字幕，不受历史 `--categories` 限制 → 零命中即真零）与**历史 `scan_terms.txt` 对照**（未加载的表必显示零命中 → 假零）；另有预判命中（yaml keywords）与噪声观测。输出**常驻候选**（判据见脚本 `--help` 与 `maintain-knowledge`）；`--root` 支持**视频目录**与**平铺 `.srt`** 两种语料形态；**语料过少时告警并标注不可信**（防语料被清理后误判） | `python scripts/glossary_hit_rate.py --root _input [--root <目录> ...] [--out <报告>] [--history <趋势文件>] [--min-videos N] [--predict-cues N] [--offline-cues N] [--no-offline] [--top N] [--stopwords <文件>]` |
| `glossary_load_plan.py` | **术语表加载集判定 + 用户门禁**：常驻集无条件加载（清单与词数用 `--list-resident` 查，**勿写死**）；**用字幕逐表扫**非 L1.5 各表 → 命中词条数达阈值者列为候选 → 报用户门禁裁定（剔除不要的表）。产出 `glossary_load_plan.md`（含**探测全貌**：未达阈值表 + 常驻命中对照，供调阈值）与**追加式** `glossary_gate_log.md`（探测范围 → 用户决策）。`--list-resident` 不需要字幕 | `python scripts/glossary_load_plan.py <字幕.srt> [--threshold N] [--out <报告>] [--json]` / `<字幕> --record "[表1,表2]"`（无参 = 候选全保留）/ `--list-resident` |

> `shared/glossary_sources.py` — **术语源适配层（单一权威）**：三套词汇表表头差异（L1 项目库 / L1.5 Mojang / L2 社区表）在此统一；按**列名**取、位置仅兜底，并提供同义词/别名展开与缩写过滤（防 `BE`/`AT` 命中 `be`/`at`）。
> **历史教训**：`render_preprocess_prompt.load_glossary` 曾按**固定列位**取值，只对 L2 有效——**L1 项目库整表被静默丢弃**，阶段〇 ASR 纠错从未拿到项目自定译名。
>
> **新增词汇表时**：只需在 `glossary_sources.EN_CANDIDATES`/`ZH_CANDIDATES`/`SHORT_CANDIDATES` 补该表的列名即可被全部消费方识别，**不要在各工具里另写解析**。

> `mojang_glossary/` 是 `glossary_fetch_mojang.py` 的实现包（内部逻辑），**非独立工具，勿直接调用**；`__init__.py`、`LICENSE` 非工具。

## ASR 修正工具

> 链路全貌：**触发清单（脚本检出）→ subagent 逐项语境判定 → 清单覆盖率闸门 → 登记入映射表**。
> 分工原则 = 脚本做**确定性检出**（整串精确匹配），LLM 只做**语境判定**——“发现怪词”不再依赖注意力。

| 脚本 | 用途 | 用法 |
|------|------|------|
| `asr_trigger.py` | **ASR 触发清单生成器（第一次遍历的必跑前置）**：用确定性判据（映射**整串精确匹配**，大小写不敏感 + 空白折叠 + **扫全文**）产出待判清单，subagent 只做语境判定。**分层**：多词 / 单字非停用词 / 单字停用词（噪声层默认不列）。**检出必带绑定**（变体 → 完整正确词形；注入裸词条实测会丢词）。**无状态**：只读当前视频字幕 + 正式资产（`asr_fixes.md`），不碰其它视频/历史语料统计。设计与实测依据见 `Project_Plan/2026-10-04_ASR检测层-可执行方案.md`（工作区根目录） | `python scripts/asr_trigger.py scan <字幕.srt> [--video <工作目录>] [--out <tsv>] [--local-fixes <局部asr_fixes.md>] [--layers M,S] [--no-stopwords]` |
| `asr_check_trigger.py` | **触发清单覆盖率闸门**：清单每项是否在 `_en_results/chunk_*.asr.tsv` 被消化（修正 `[ASR]` / 放行 `[放行]`）。**三级判据**（纯字符串 + 结构，零语义）：已决策（同 cue + 原词列互为包含，容忍 subagent 写上下文片段）/ 改后未登记（输出 SRT 已无该变体，提示级）/ **未处理（打回）**。来源口径不符为提示级——已消化就不拦，混为一谈会误伤已完成的工作。**`--stats`** 另报观测指标（清单字符数按块分布 / 决策来源分布 / 发现能力），**不拦退出码**——用于监测「清单挤占上下文」与「发现能力退化」两个风险 | `python scripts/asr_check_trigger.py --video <工作目录> [--chunk <k>] [--expand] [--stats]` |

> `shared/asr_common.py` — **ASR 修正链路公共层（单一权威）**：映射表解析 + 归一化 + **停用词表** + SRT 读取。
> 停用词表原只存于 `glossary_hit_rate.py`，ASR 触发清单的噪声层过滤**复用同一张表** → 两处各存一份必然漂移，故迁入本模块；`glossary_hit_rate.load_stopwords` 保留同名薄壳。
> ⚠️ 两处**口径故意不同**：回测“宁可漏报不可误杀”（软档只计数不剔除），清单“宁可清短”（硬软两档都滤）。

## 开发分析工具

> ⚠️ **非工作流依赖**——本目录脚本**不被任何 Skill / 维护流程调用**，仅供
> **实验分析、能力标定、映射表审计**，按需手动跑。故与生产脚本分开放
> （`scripts/` 只放工作流与维护会用到的工具）。
> 命令根仍为 `Project_Main/`；**运行时读写的仍是生产资产**（`asr_fixes.md` / `_input/` / `_work/`）。

| 脚本 | 用途 | 用法 |
|------|------|------|
| `asr_bench.py` | **ASR 修正能力实测脚手架**：从历史配对（原始 ASR + `01_subtitle_asr_fixed.srt`）生成**隔离测试材料**（只给英文原文，不给词表），供评估“LLM 无词表时能修多少 ASR 误听”。**自动过滤 cue 数不对齐的样本**（参考稿有合并/拆分 → 按行号对照会错位）。`merge` 汇总产出 | `python scripts/_dev/asr_bench.py gen [--videos N] [--chunk-cues N]` / `merge` |
| `asr_bench_b.py` | **ASR 对照实验材料生成**：B 组（仅注入常驻集词表）/ C 组（词表 + `asr_fixes` 映射，`--with-fixes`）。与既有无词表组**逐字对齐**（唯一变量 = 注入内容），配合 `asr-fixer-b` agent 派发。**Y 层复活条件**里列为备用手段（见 `References/ASR修正-实测资料/pre-implementation/Y_LAYER_VERIFICATION.md`） | `python scripts/_dev/asr_bench_b.py gen [--with-fixes] [--videos N] [--only <视频,视频>]` |
| `asr_fixes_audit.py` | **`asr_fixes` 审计（证据驱动）**：**唯一可删类 = 拼写错误**（普通英文词错拼，与术语无关）；其余全部**保留**——映射的价值不止“补模型不知道的词”，还有**提供精确词形 + 抑制乱猜**。另出**多词长术语**（边界锚定，尤其要留）、**重复条目**、**高风险变体**（短小合法词，易反向误纠）。**只报告不自动删** | `python scripts/_dev/asr_fixes_audit.py [--out <报告>] [--expand]` |
| `asr_fixes_scope.py` | **`asr_fixes` 归档筛选清单**：按“变体在几个视频的原始 ASR 里出现”分组，出**可勾选** Markdown（勾选 = 归档到该视频局部表）。**判据有已知局限**：只出现在单视频 ≠ 视频专属（可能别的视频还没遇到该话题）→ **需人工筛**。`--apply` 只打印方案不改文件。`maintain-knowledge` 仅作「确需下沉视频专属项时」的备用手段引用 | `python scripts/_dev/asr_fixes_scope.py [--out <清单>]` / `--apply` |

## 字幕通用工具

> 两个工作流共用、与具体工作流无关的字幕按行/按 cue 操作。

| 脚本 | 用途 | 用法 |
|------|------|------|
| `srt_mech_fix.py` | **阶段〇机械修复（纯脚本、零知识、零 LLM）→ `00_subtitle_snapped.srt`**：结构清理（重叠/倒序 cue 顺延；异常时长仅告警）+ 时间轴吸附（可选，需音频，**起终点分向**以保留 cue 间隙）；**绝不动文本**；带不变量自检（cue 数/文本/`start<end`/无重叠/**间隙数守恒**），未过则不产出；无音频自动降级跳过 | `python scripts/srt_mech_fix.py <原始ASR.srt> -o 00_subtitle_snapped.srt [--audio <音频> \| --video <视频>]` |
| `srt_snap_audio.py` | 时间轴吸附实现层（以语音能量谷为真值修正时间戳偏移；SRT / `en_timeline` 两种模式）；一般经 `srt_mech_fix.py` 调用 | `python scripts/srt_snap_audio.py --audio <音频> --srt <输入.srt> [-o <输出>] [--apply]` |
| `srt_check_width.py` | 中文行视觉宽度校验（`--warn` 软告警 / `--hard` 硬限；`--order` 指定双语语言顺序）；**硬闸门**：超硬限计 ERROR 并定位 `文件:行号`（`--expand`），退出码 1 = 打回信号；默认只给超限段数。阈值权威 = `shared/srt_common` | `python scripts/srt_check_width.py <draft.srt> [--warn <软限>] [--hard <硬限>] [--order en-zh\|zh-en] [--expand]` |
| `srt_check_segments.py` | 校验分段/成稿时间约束：相邻段时间不重叠、时间边界 ⊆ 原边界集、段序不逆序、cue 覆盖完整（`s03_plan.md` 的 `~`=估算切分点）；`--cue-exact` 用于 01 修正字幕（cue 数一致 + 逐 cue 时间戳与 `00_subtitle_snapped.srt` 完全一致，输出目标/原始时间戳供返工）；`--missing-ctx N` 给缺失 cue 明细窗口；默认只给问题数，`--expand` 展开每条明细 | `python scripts/srt_check_segments.py <目标> --orig <原字幕.srt> [--allow-estimated] [--cue-exact] [--missing-ctx N] [--expand]` |
| `srt_join_parts.py` | **SRT 片段拼接**：各块 SRT 片段（`chunk_<k>.srt`，照抄输入时间码）按块序拼接 + 全局段号重排 + cue 数强制校验（`--chunks`，漏/多 cue 拦截）；时间轴精确校验交 `srt_check_segments --cue-exact`（基准 = `00_subtitle_snapped.srt`）；区别于 `text_merge`（其 srt 模式丢时间码，面向断句合并） | `python scripts/srt_join_parts.py <results_dir> --out <01.srt> [--chunks <chunks_dir>]` |
| `srt_check_terms.py` | **译文术语全量核对**（reflow r02 / translate 共用）：逐条遍历 `02_terms.md`——01 定位原文出现单元 → 该单元译文须含确认译名（变体容错 / 长术语覆盖）；支持三种产物形态：reflow 块级（`<r02_results/> --chunks`）、translate 块级（`<_trans_results/> --chunks`，剥离 CARRY 结转行）、translate 合并稿（`<s04_draft.srt> --plan <s03_plan.md>`，段→cue 区间映射）；默认只给问题数，`--expand` 展开每条 ⚠️/ℹ️ 明细；退出码 1 = 有未命中（复核后才放行） | `python scripts/srt_check_terms.py <01> <02_terms.md> <译文目录或srt> --chunks <chunks/> 或 --plan <s03_plan.md> [--expand] [--chunk k] [--verbose]` |
| `srt_verify.py` | 核对并重编号修正 SRT（块数/时间码对齐）；**ASR 修正差异工具，非双语翻译稿校验器** | `python scripts/srt_verify.py <orig.srt> <fixed.srt>` |
| `srt_diff.py` | 逐块对比两个 SRT（时间戳 / 正文差异） | `python scripts/srt_diff.py <a.srt> <b.srt>` |
| `srt_split.py` | 将双语/多语 SRT 按字段拆分成多个单语文件（`FIELDS` 常量配置行顺序，字段名即输出后缀；加新语言只需添名字） | `python scripts/srt_split.py <双语.srt> [-o 前缀] [-d 目录] [--out 字段=路径]` |

## 长视频分块与合并

> 分块机制通用（SRT 与非 SRT 产物共用）；块文件格式契约见 `docs/PRODUCT_FORMATS.md#通用文本分块`。

| 脚本 | 用途 | 用法 |
|------|------|------|
| `text_chunk.py` | **长视频通用分块（SRT 与非 SRT 统一，新任务入口）**：SRT 按“N cue 负责 + M 上下文”，**`--gaps-file <r00_gaps_active.tsv>`（推荐）读生效空隙点集**（人已裁决、`excluded` 自动跳过）分组（块边界优先在空隙点），或 `--gaps`（旧：自行探测）；非 SRT（r01/r02/r03）按语义单位（段/句/整句组），超长单位自动细分“组-片”；输出统一块格式（含块头元数据 + manifest）；`--inherit` 已弃用 | `python scripts/text_chunk.py <输入> --out <dir> [--type srt\|text] [--unit 段\|句\|整句组] [--owned N] [--ctx M] [--max-chars N] [--gaps] [--gaps-file <tsv>]` |
| `text_merge.py` | **长视频分块合并（A 模式：全自动拼接 + 异常清单）**：按块序读 subagent 结果归位拼接；无异常直接产出，异常出报告 + 异常块头尾窗口供 Agent 决策；替代主 Agent 手工读头尾组装 | `python scripts/text_merge.py <chunks_dir> <results_dir> --out <合并产物> [--report <报告>] [--window N]` |
| `srt_chunk.py` | 旧版长视频分块（仅 SRT）；**保留兼容，新任务一律用 `text_chunk.py`** | `python scripts/srt_chunk.py <srt> --out <dir> --owned N --ctx M [--order en-zh\|zh-en]` |

## translate-redstone 工作流工具

| 脚本 | 用途 | 用法 |
|------|------|------|
| `srt_check_plan_words.py` | **断句措辞一致性校验**：`s03_plan.md` 各段英文词序列 == 01 对应 cue 区间（断句只合并/分割、**不改措辞**）；difflib 一次列全部分歧（错词/缺词/多词）；`--asr-fixes` 把 `02_terms.md` ASR 修正列（含 `→` 映射）应用到 01 侧再对比（容错组装期修正）；默认只给问题数，`--expand` 展开每处上下文；退出码 1 = 有分歧（打回） | `python scripts/srt_check_plan_words.py <01.srt> <s03_plan.md> [--asr-fixes <02_terms.md>] [--expand]` |


## reflow-redstone 工作流工具

> 语义回填专用。
> 链路：空隙探测 → 断句点 → 补标点 → 整段翻译 → 分句 → 回填 → 组装。
> 标点角色表 / 括号配对的**单一事实源在 `shared/srt_common.py`**（一张跨语言通用表，不按语言分表）；`srt_reflow_core/punct.py` 只留算法（guards / 代价最小化 DP）。

| 脚本 | 用途 | 用法 |
|------|------|------|
| `srt_reflow.py` | 确定性时间运算：`reflow`（r03 方案 + 01 → r04 时间轴 + `r03_anchored.jsonl` 锚定明细（JSONL 每行一整句）；整句锚定 + 单元级 cue 锚定 + 分割点就近吸附真实边界 + 预测点）、`attach-en`（双语组装，英文行 = r03 互斥英文片段）、`check-r03`（r03 写时即合规预检：锚定唯一性 / 拆句互斥 / **行宽** / ZH 忠实，违规退出码 1 打回；默认只给问题数+分类，`--expand` 展开每处明细，`--chunk <k>` 只校验单块） | `python scripts/srt_reflow.py reflow <r03> <01> [-o r04_draft.srt] [--anchored r03_anchored.jsonl]` / `... attach-en <r04> <r03> [-o r04_bilingual.srt]` / `... check-r03 <r03_results/> <01> <r02_results/> --chunks <chunks/> [--expand] [--chunk k]` |
| `srt_reflow_gap_scan.py` | **空隙探测 + 疑点识别**（长停顿 / 剪辑跳转，阈值见 `shared/srt_common`）→ `r00_gaps.md`（人读报告）+ `r00_gaps_active.tsv`（**生效空隙点集单一事实源，人工可编辑**）；**自动标记“疑似源切分缺陷”**（判据：前 cue 末尾无句末标点 **且** 后 cue 首字母小写——同一句被切成两条 cue 的典型形态），只报告不改行为；人工把 tsv 该行 `status` 改为 `excluded` 即正式排除，**重跑不覆盖人工决定** | `python scripts/srt_reflow_gap_scan.py <01> [-o reflow/r00_gaps.md] [--tsv reflow/r00_gaps_active.tsv]` |
| `srt_reflow_breaks.py` | 硬性断句输入：断句点清单（含 Agent 复核字段）→ `r01_breaks.md`；**优先读 `r00_gaps_active.tsv`**（人工已裁决的生效集，`excluded` 项跳过），疑点处附“改 tsv 为 excluded”引导；缺失则回退自行探测 | `python scripts/srt_reflow_breaks.py <01> [-o reflow/r01_breaks.md] [--tsv reflow/r00_gaps_active.tsv]` |
| `srt_reflow_check_breaks.py` | **r01 硬性断句校验**：逐生效空隙点查句末标点；违规退出码 1（打回信号，受控例外 Agent 裁决）；块级模式（`--chunks <chunks目录> --gaps r00_gaps_active.tsv`，`excluded` 项自动跳过；N=1 为单块骨架）；**传旧 `r00_gaps.md` 亦兼容**（自动找同目录 tsv）；命中未排除的疑似源缺陷时提示“改 tsv”而非要求强制断句；默认只给问题数，`--expand` 展开每处违规详情，`--chunk <k>` 只查涉及该块的空隙点 | `python scripts/srt_reflow_check_breaks.py <01> <r01_results/> --chunks <chunks/> --gaps r00_gaps_active.tsv [--expand] [--chunk k]` |
| `srt_reflow_check_words.py` | **r01 措辞校验**：词序列与 01 一致（不得改动措辞）；块级模式（`--chunks <chunks目录>`，逐块对比块↔cue 区间词序列）；**跨块互补判定**（前块多出的词 == 邻块缺失的词 → 衔接归位的正常结果，放行）；difflib 一次列出全部分歧（错词/缺词/多词）；默认只给问题数，`--expand` 展开每处上下文/行号/cue 定位，`--chunk <k>` 只查单块 | `python scripts/srt_reflow_check_words.py <01> <r01_results/> --chunks <chunks/> [--expand] [--chunk k]` |
| `srt_reflow_normalize.py` | 块目录归一化（两种输入形态自动检测）：chunks 模式（补标点，`## 分区` cue 文本合并 + 折行 → `r01_normalized/`）、纯文本模式（r02 折行副本 **已停用**——由预分句 `srt_reflow_presplit.py` → `r03_normalized_2/` 取代）；折行宽度见 `shared/srt_common.MAX_LINE`（英文不拆词、中文按字符）；一次跑完整个目录 | `python scripts/srt_reflow_normalize.py <chunks/> -o reflow/r01_normalized/` |
| `srt_reflow_presplit.py` | **预分句 + ZH 机械化断句**：EN 按句末标点（`r01_results/`）→ `r03_normalized_1/`（E1..En）；ZH 按句号（`r02_results/` 直读原稿）→ `r03_normalized_2/`（**r03 模板骨架**：Z 句 + 句内切分段预填目标区间、硬限引 `shared.srt_common`）；**断句/切分委托 `srt_reflow_core.punct`**（角色表 + guards：缩写/小数点/省略号/括号配平/序号）；折行合并保留中英/数字空格；**拼合 = 代价最小化**（断点强度 + 段宽偏离 + 碎片罚）——参数与角色表均可 `--punct-*` / `--soft-*` 覆盖（旧 `--punct-levels` 按字符归属映射、不推荐）；忠实铁律由结构保证（段只在标点处切、不增删改）；**`--zh-list-out <目录>`（可选）**：额外生成整句级 Z 精简列表（`r03_zslim/`，供句子匹配 `task-match`） | `python scripts/srt_reflow_presplit.py <r01_results/> <r02_results/> -o reflow/ [--zh-list-out reflow/r03_zslim]` |
| `srt_reflow_build_r03.py` | **脚本断句填回**（分句的脚本断句路径）：由「匹配文件 `r03_matches/`（LLM 句子匹配）+ EN 预分句 `r03_normalized_1/` + ZH 模板骨架 `r03_normalized_2/`」机械生成 `r03_results/`——子单元复用模板子句段（机械断句）、EN 整句按匹配 E 组拼接、子单元 EN 按宽度比例机械切分（互斥拼接 == 整句）；**漏句留空**（匹配未覆盖的 Z/E 句产物写 `> ⚠️ 脚本断句·未匹配` 标记，不静默消失）；退出码 1 = 匹配解析问题 | `python scripts/srt_reflow_build_r03.py <r03_matches/> <r03_normalized_1/> <r03_normalized_2/> -o r03_results/` |
| `srt_reflow_check_sentence_len.py` | **r01 补标点质量校验**：按句末标点分句检测补标点质量——**分级告警**：硬（打回）单句逗号过多 / 单句过长 / 句均过长（断句稀疏）；软（提示复核，不阻断）疑似可断句（逗号与字符数双达标）；阈值均可 `--max-*` / `--soft-*` 覆盖；默认只给问题数，`--expand` 展开每处文件:行号+上下文，`--chunk <k>` 只查单块；退出码 1 = 有硬命中 | `python scripts/srt_reflow_check_sentence_len.py <r01_results/> [--max-comma N] [--max-sent N] [--max-avg N] [--soft-comma N] [--soft-sent N] [--expand] [--chunk k] [--verbose]` |

> `srt_reflow_core/` 是 `srt_reflow.py` 的实现包（io / plan / anchor / allocate / alerts / reflow / attach / **punct** 断句引擎），**非独立工具，勿直接调用**；入口只有 `srt_reflow.py`。

## reflow2 工作流工具

> 时间轴源头固化专用：E 句时间戳脚本固化、Z 句每次重算、中文继承英文时间。

| 脚本 | 用途 | 用法 |
|------|------|------|
| `srt_reflow2_etimeline.py` | **时间轴源头固化**：每块 r01（衔接归位后）按句末标点切 E 句（复用 `split_en`），每 E 句在块内 OWNED cue 区间锚定（与消费端 `io.build_full` 同构：norm 去空格、无缝拼接；相邻 E 句共享 cue 按字符占比切分）→ `en_timeline/`（`E<n>\t<start> --> <end>\t<c<cues>>\t<文本>`，**只读真值锚**）；内嵌方括号标记剥离后锚；退出码 1 = 有 E 句锚定失败（MISS） | `python scripts/srt_reflow2_etimeline.py <chunks/> <r01_results/> --srt <01> -o reflow2/en_timeline/` |
| `srt_reflow2_check_consistency.py` | **一致性复核产物校验**：逐块查 `consistency/` 形态与句号引用——块覆盖与 `en_timeline` 一致、首行固定注释行、疑点行 4 字段 TSV、`无矛盾` 与疑点行互斥、引用 E 号存在且文本有效（`MISS` / 空不参与）；字段超长仅告警。**不判断矛盾是否判对**（内容真伪脚本无法验） | `python scripts/srt_reflow2_check_consistency.py reflow2/consistency/ [--etimeline <目录>] [--expand] [--chunk k]` |
| `srt_reflow2_zsent.py` | **切 Z 句**（切 Z 句与对齐的前半）：每块 r02 按中文句末标点切 Z 句（复用 `split_zh`）→ `zh_sentences/`（每行 `Z<n> <整句>`，**Z 每次从 r02 重算**） | `python scripts/srt_reflow2_zsent.py <r02_results/> -o reflow2/zh_sentences/` |
| `srt_reflow2_stitch.py` | **跨块句衔接归位**（补标点的校验项，文档设计落地）：块边界常落句中，补标点在两侧各补全同一句 → 本脚本**只在一侧留无标记完整句、另一侧不留文本**（保留前块、后块整句删除）；单边标记/内容不等 → 只删标记保留句并告警。归位后 `check_words` 走“跨块互补”判定放行 | `python scripts/srt_reflow2_stitch.py reflow2/r01_results/ [--dry-run]` |
| `srt_reflow2_backfill.py` | **继承回填**：读 `zh_sentences/`（Z 文本）+ `align/`（Z组=E组，`task-match` LLM 产物）+ `en_timeline/`（E 固化时间）——**先做“跨块句衔接归位”**（合并被块边界劈成两半的同一句：判据 = 两侧 EN 归一化后相等 / 前句末尾悬空成分 + 后句碎片；ZH 互补拼接、EN 去重、时间并集），再每 Z 组继承 E 组覆盖时间（源头固化、天然零重叠）；Z 超宽按**标点功能角色表**拆子段 + 按阅读速度比例在 E 区间内细分（复用 `allocate._allocate_by_weight`：吸附真实 cue 边界，无则取整预测点）——拼合 = 代价最小化（分号由硬断降为强优先，可被宽度否决）；同步生成 `r04_bilingual.srt`（`--order` 控制行序）+ `r04_alerts.md`；退出码 1 = 对齐不完整 | `python scripts/srt_reflow2_backfill.py <zh_sentences/> <align/> <en_timeline/> -o reflow2/r04_draft.srt [--alert reflow2/r04_alerts.md] [--bilingual reflow2/r04_bilingual.srt] [--order zh-en]` |

> `shared/request_identity.py` — **请求身份（HTTP User-Agent 联系方式）统一解析**（Wikimedia 政策要求脚本 UA 含联系方式，本项目由使用者配置而非内置作者信息）：优先级 = 环境变量 `TCTW_CONTACT` → `configs/request_identity.yaml` → git remote 探测 → 占位符+告警；被 `fetch_wiki.py` / `mojang_glossary` 共用。查看当前解析结果：`python -c "import sys;sys.path.insert(0,'scripts');from shared.request_identity import user_agent;print(user_agent())"`。

> **SRT 解析注意（空 cue 必须保留）**：SRT 中的空文本 cue（仅索引 + 时间行、无正文）**必须保留**——`parse_srt` 用 `len(lines) >= 2` 判定，cues 数组才能与 SRT 序号严格对齐；若退回 `len(lines) < 3` 跳过空 cue，数组即错位、按 `idx-1` 访问全错。`srt_reflow_check_breaks` / `srt_reflow_breaks` / `srt_reflow_gap_scan` / `text_chunk` / `srt_check_segments` 等已统一为 `>=2`，**勿回退**；个别脚本仍用 `<3`（`srt_reflow_check_words` / `srt_check_terms` / `srt_check_plan_words`）但以 `cue_map.get(i, "")` 兜底，跳过空 cue 不致错位。

## translate + reflow 共用编排工具

| 脚本 | 用途 | 用法 |
|------|------|------|
| `context_estimate.py` | **确定性 token 估算 + 分块建议**：按窗口配置与分块比例给出 `--owned` 建议值；放大协调 = 单块输入上限 `min(输入阈值, 输出阈值 ÷ amplification)`；`--no-amplification` 关闭；输出每 cue 平均字符与建议 `--owned`（长视频分块的**前置判断**依据，见 `redstone-conventions#长视频分块`） | `python scripts/context_estimate.py <文件> [--window N] [--split-ratio R] [--no-amplification] [--owned N]` |
| `render_preprocess_prompt.py` | **preprocess 阶段二执行型块级任务 prompt 渲染**（会话外落盘 `prompts/`）：接入 `task-term-recognition` / `task-en-preprocess`；按任务注入先验知识（触发清单 / asr_fixes 映射 / 领域术语集，按 OWNED cue 过滤）；**`task-en-preprocess` 缺触发清单直接报错**。独立于 `render_subagent_prompt.py`（后者管 reflow/reflow2/translate 阶段三）。**集中补齐查证（`task-term-resolve`）不走本脚本**——研究型单次任务，任务文件即 prompt | `python scripts/render_preprocess_prompt.py <task> --video <工作目录> [--chunk <k> \| --all] [--scan <scan_terms.txt>] [--glossary <csv...>] [--asr-fixes <局部文件>]` |
| `render_subagent_prompt.py` | **reflow/reflow2/translate 阶段二执行型块级任务 prompt 渲染**：接入 `task-punctuate`/`task-translate`/`task-split`/`task-match`（reflow，**reflow2 同名任务 `--skill reflow2`**）+ `task-consistency`（reflow2）+ `task-merge`/`task-translate`/`task-humanize`（translate，**`--skill translate-redstone`**）；读模板 + 纪律母版 `_discipline.md` + 产物格式约定 + 先验知识 → `prompts/<task>-chunk_<k>.txt`；完整 prompt 不进主会话历史 | `python scripts/render_subagent_prompt.py <task> --video <工作目录> [--chunk <k> \| --all] [--chunks-dir <chunks目录>] [--skill <skill>] [--prior-file <文件>]` |


## 数据源与缓存维护

| 脚本 | 用途 | 用法 |
|------|------|------|
| `fetch_wiki.py` | **Wiki 页面获取与缓存刷新（官方 MediaWiki API 直连，不经 MCP）**。内容源：默认 `explaintext` → `fidelity: plain`（正文可读、表格剥离）；`--wikitext` → `fidelity: lossless`（ID 表/色值/历史全保留）。工作模式：默认 **抓取**（参数 = 页面名）；`--refresh` = **刷新现缓存**（页面名作筛选，省略 = 全部）——用于缓存过期时的主动刷新与批量维护，`--dry-run` 只探测。**保真度只升不降**：默认拒绝低保真覆盖已有高保真缓存（防 `plain` 覆盖 `lossless`），`--force` 绕过 | `python scripts/fetch_wiki.py <页面...> [--wikitext] [--force]` / `python scripts/fetch_wiki.py --refresh [<页面...>] [--dry-run] [--interval N]` |
| `refresh_cache.py` | 统一入口：检查三类缓存；Mojang/TechMC 自动刷新；Wiki 只告警不自动抓取（Agent 按 `wiki-tools` 降级链按需刷新）。**`--check-page <页面...>`** = 单页过期判定（读缓存后必做）：按 front matter `fetched`（缺失回退 mtime）与 TTL 判 `未过期`/`过期`/`未缓存`，退出码 1 = 有需处理项 | `python scripts/refresh_cache.py [--force\|--dry-run\|--ttl N] [--check-page <页面...>]` |
| `check_index_stale.py` | 对比 submodule 当前 commit 与索引记录 commit，报告哪些索引需更新（索引时间戳策略见 `project-structure`） | `python scripts/check_index_stale.py [--only <repo>]` |

## 文档一致性校验

> 两类均**零副本**：注册表只登记“文件 + 正则/锚点”，期望值运行时从代码常量或文档解析——不存在“脚本自己过期”。

| 脚本 | 用途 | 用法 |
|------|------|------|
| `check_param_sync.py` | **参数同步校验**：文档里的参数值 vs `shared.srt_common` 常量。同时查：旧模块名残留（改名后静默生效的隐患）、未使用的值占位符（死代码）。**改参数后必跑** | `python scripts/check_param_sync.py [--list] [--file <子串>] [--expand]` |
| `check_phase_sync.py` | **阶段编号与引用一致性校验**：七组检查——A 阶段令牌合法（唯一空间 `〇一二三四五六`，禁 零/阿拉伯数字/½/+/A）、无残留 `§1.x`；B 跳文件 `#锚点` 可解析 + 被引用锚点在冻结清单内；C 有序列表序号连续、阶段标题集合与注册表一致、自称阶段数吻合、禁合并标题、表格阶段行升序；D 无残留数字步骤号；E 标题禁括注；**F `「」` 弱引用可解析**（警告级，不拦退出码）；**P 引用块短语 + 标题禁数量词**。**改阶段编号 / 标题后必跑** | `python scripts/check_phase_sync.py [--list] [--group A\|B\|C\|D\|E\|F\|P] [--file <子串>] [--expand] [--out <文件>]` |

## 环境

| 脚本 | 用途 | 用法 |
|------|------|------|
| `setup_editors.py` | 编辑器适配初始化（跨平台，创建 Claude Code 等所需的 symlink） | `python scripts/setup_editors.py [--force]` |

## 验证脚本统一反馈约定

所有校验闸门脚本（`srt_check_width` / `srt_check_segments` / `srt_check_plan_words` / `srt_check_terms` / `srt_reflow_check_*` / `srt_reflow2_check_consistency` / `check-r03` / `check_param_sync` / `check_phase_sync` / `asr_check_trigger`）统一反馈策略，控制上下文占用：

- **默认（不带展开参数）**：只输出“问题数目 + 提示”——各问题定位一行统计（块/段/空隙点/检查组 + 数量），**不输出错误内容、不输出上下文**（行号/片段/原文）。
- **`--expand`**：展开每处问题的详细内容 + 上下文（文件:行号 + 片段，供 Agent 直接定位编辑；主会话收集 task-fix 错误清单时用）。
- **`--chunk <k>`**（仅块级验证脚本：`srt_check_terms` / `srt_reflow_check_breaks` / `srt_reflow_check_words` / `srt_reflow_check_sentence_len` / `check-r03` / `asr_check_trigger`）：只校验/对比块 k，**单块模式默认展开该块详情**——针对某块修复时其他块的问题零输出、零占用上下文。
- **`--verbose`**（部分脚本）：展开通过项统计，与 `--expand` 正交。
- **`--out <文件>`**（`check_phase_sync`）：问题多（上百处）时写 UTF-8 报告文件再读，避开 PowerShell 控制台代码页乱码。
- 退出码语义不变（0=通过；1=打回/有未命中）。

每个脚本的详细说明见 `python <script>.py --help`。

## 修改参数 / 阈值时的同步清单

数值**不是**只存一处就能自动一致——代码要能执行、文档要能说明，所以存在一个天然下限：**每类读者各 1 处**（详见下表）。改参数时按此逐项核对，**勿凭记忆填写数值**。

| 读者 | 能否解析常量名 | 占位符能否注入 | 该读者侧存值下限 |
|------|----------------|----------------|------------------|
| 主 agent（读 SKILL 主文） | 能（有全局视野 + 工具） | 不适用 | 1 处**权威段**；**其余内联处保留自包含值**（见下“为何不全部改成指向”） |
| subagent（被注入任务模板 / 纪律母版） | **不能**（无主 agent 上下文） | **能**（渲染脚本） | **0 处**——模板写占位符，由 `render_subagent_prompt.py` 填真实值 |
| subagent（自行 read `docs/PRODUCT_FORMATS*.md`） | **不能** | **不能**（不经渲染） | 保留值，但须标注**形态描述、非判据**（防与判据冲突时误信） |

> **为何不全部改成“指向权威段”**：多个 Skill 明确**运行时不加载** `segment-subtitles`（见 `reflow-redstone/SKILL.md` 权威表“规则已内联语义回填文件，**不加载**”）。在这些位置写“见权威段”会使 agent 要么额外加载（违背省上下文）、要么拿不到值。**这是“省上下文”与“单一事实源”的真实取舍** —— 取舍结论 = 内联保留值 + 权威段登记消费方清单 + **校验脚本兜底同步**（`check_param_sync.py`）。

**改动步骤**：

1. 改**共享层常量**（`shared/srt_common.py` 等；每个常量旁标注了“权威说明位置”注释，只含路径、不含值）。
2. 打开该注释指向的**权威文档段**（如 「segment-subtitles#行宽规则」），同步语义描述 + 上下界约束 + **该段的“内联消费方”表**（改一处即可看全需同步的文件）。
3. **跑 `python scripts/check_param_sync.py`** —— 零副本校验：期望值运行时从代码常量读取，直接列出所有滞后文档位置（含行号）。按报错逐项改。
4. 若模板新增了值占位符，在 `render_subagent_prompt.py` 的 `VALUE_PLACEHOLDERS` 登记（渲染时校验无残留并告警）。
5. 跑对应校验脚本确认行为未变（对比 `--help` 默认值 + 既有 `_work/` 产物重跑比对）。

## 修改阶段编号 / 标题时的同步清单

阶段编号、阶段标题名、子节编号是**跳文件引用的键**（Markdown `#锚点` 一格不差才有效，否则**静默失效**）。改动时按此核对：

1. 改**标题**（`阶段〇…` / `术语扫描`）——锚点随之改变
2. 同步全部**跳文件链接**（同类 skill 目录内的 `SKILL.md#锚点`）——含脚本体、`docs/**`、`.github/experience/**`
3. 同步 **`check_phase_sync.py` 注册表**：`PHASES`（阶段号→角色名）/ `PHASE_HEADING_SETS`（各文件应出现的阶段号）/ `FROZEN_ANCHORS`（被引用锚点冻结清单）
4. **跑 `python scripts/check_phase_sync.py --expand`** —— 零副本校验：直接列出所有滞后位置（含行号）与失效锚点。按报错逐项改，退出码 0 为止
5. 确认 `python scripts/check_param_sync.py` 仍 0（两者锚定的正文短语不重叠，但同文件改动后必须复验）

> ⚠️ **阶段三内部一律用角色名引用**（空隙探测 / 分块 / 补标点 / 翻译 / 分句 / 回填 / 组装），**不写数字编号**——reflow 与 reflow2 的数字 4–7 语义不同（同号异义），数字引用无法自验。
> ⚠️ **别把“无脚本兜底”的数值写成“由脚本判定”**——subagent/agent 会误信而不再自查，比留着旧值更危险。约束类型（硬闸门 / 脚本判定 / 实践建议）须在权威段显式标注。

## 安全规则

**写入范围**——脚本只写下列位置，**不触碰** `_repos/`（只读 submodule）、`_input/`（用户地盘）、`knowledge/` 与 `.github/experience/`（人工/Agent 维护的正式资产）：

| 位置 | Git 状态 | 谁写 |
|------|---------|------|
| `_work/` | 忽略（`_work/.gitignore` 的 `**/*`） | **绝大多数脚本的默认或典型输出**：`asr_trigger`、`glossary_hit_rate`、`glossary_load_plan`、`render_*`（落 `prompts/`）、全部 `srt_*` / `text_*` 工作流脚本、`_dev/` 的开发分析脚本 |
| `.cache/` | 忽略（根 `.gitignore`） | 缓存类：`glossary_split`、`glossary_fetch_mojang`、`fetch_wiki`、`refresh_cache`、各 `--cache` 音频解码缓存 |
| 调用方指定的路径 | 随使用者 | 所有带 `--out` 的脚本；位置参数型（如 `srt_mech_fix` / `srt_join_parts` / `text_merge`）写到参数所指处。⚠️ **`srt_verify.py` 会就地重写你传入的那个 fixed 文件** |
| `.claude/`、`CLAUDE.md`（项目根） | **未忽略** | 仅 `setup_editors.py`——它是**唯一写到项目根、落在 Git 忽略范围外**的脚本 |

**删除 / 覆盖行为**（均需显式开关；其余脚本不删除任何文件）：

- `setup_editors.py --force`：**先删后建**——`unlink` 或 `rmtree` 掉 `.claude/skills/`，并 `unlink` `CLAUDE.md`，然后重建
- `fetch_wiki.py --force`：允许**低保真缓存覆盖已有高保真缓存**（默认拒绝，防 `plain` 覆盖 `lossless`）
- 业务意义上的"删除"（非删文件）：`srt_reflow2_stitch.py` 归位时会删掉块内的重复句文本

> 需要清理 `_work/` / `.cache/` 时请用户手动操作——总原则见 `AGENTS.md` 核心原则的“禁止自动删除”（任何删除须由用户明确发起）。

