# 脚本

按用途分组，文件名前缀标识类别（`glossary_` 术语词表、`srt_` 字幕工具（两工作流共用 + 通用）、`text_` 通用文本分块/合并（长视频机制）、`srt_reflow_` 回填工作流专用）；独立工具保留原名。

## 术语词汇表工具（`glossary_*`）

| 脚本 | 用途 | 用法 |
|------|------|------|
| `glossary_split.py` | 将上游合并术语 CSV 按类别拆分到 `.cache/glossary/` | `python scripts/glossary_split.py [--check\|--help]` |
| `glossary_fetch_mojang.py` | 从 Mojang 官方 API 下载最新翻译词汇表 | `python scripts/glossary_fetch_mojang.py [--check]` |
| `glossary_lookup.py` | 按 L1→L1.5→L2 查术语中文译名（只读） | `python scripts/glossary_lookup.py <term> [<term> ...]` |

> `mojang_glossary/` 是 `glossary_fetch_mojang.py` 的实现包（内部逻辑），**非独立工具，勿直接调用**；`__init__.py`、`LICENSE` 非工具。

## 字幕流水线工具（`srt_*`，translate / reflow 两工作流共用）

| 脚本 | 用途 | 用法 |
|------|------|------|
| `srt_check_width.py` | 检查 SRT 中文行视觉宽度（行宽规则；`--warn` 软告警 / `--hard` 硬限制；`--order` 指定双语语言顺序） | `python scripts/srt_check_width.py <draft.srt> [--warn 22] [--hard 26] [--order en-zh|zh-en]` |
| `srt_check_segments.py` | 校验分段/成稿时间约束：相邻段时间不重叠、时间边界 ⊆ 原边界集、段序不逆序、cue 覆盖完整（segment-subtitles Skill 用；`03_segments.md` 的 `~`=估算切分点；`--cue-exact` 用于 01 修正字幕：cue 数一致 + 逐 cue 时间戳与原始完全一致，输出目标/原始时间戳供返工） | `python scripts/srt_check_segments.py <目标> --orig <原字幕.srt> [--allow-estimated] [--cue-exact]` |
| `text_chunk.py` | **长视频通用分块（SRT 与非 SRT 统一，新任务入口）**：SRT 默认按「N cue 负责 + M 上下文」；`--gaps` 按空隙组分组成「空隙组-片」（reflow 从 01 分块用，块边界优先在空隙点）；非 SRT（r01/r02/r03）按语义单位（段/句/整句组），超长单位自动细分「组-片」；输出统一块格式（含块头元数据 + manifest）；`--inherit` 已弃用 | `python scripts/text_chunk.py <输入> --out <dir> [--type srt\|text] [--unit 段\|句\|整句组] [--owned N] [--ctx M] [--max-chars N] [--gaps]` |
| `text_merge.py` | **长视频分块合并（A 模式：全自动拼接 + 异常清单）**：按块序读 subagent 结果归位拼接；无异常直接产出，异常出报告 + 异常块头尾窗口供 Agent 决策；替代主 Agent 手工读头尾组装 | `python scripts/text_merge.py <chunks_dir> <results_dir> --out <合并产物> [--report <报告>] [--window N]` |
| `srt_join_parts.py` | **SRT 片段拼接（第一次遍历合并链路）**：各块 SRT 片段（`chunk_<k>.srt`，保留原时间码）按块序拼接 + 全局段号重排 + cue 数强制校验（`--chunks`，漏/多 cue 拦截）；时间轴精确校验交 `srt_check_segments --cue-exact`；区别于 text_merge（其 srt 模式丢时间码，面向断句合并） | `python scripts/srt_join_parts.py <results_dir> --out <01.srt> [--chunks <chunks_dir>]` |
| `srt_chunk.py` | 旧版长视频分块（仅 SRT，按「N 负责 + M 上下文」）；**保留兼容，新任务一律用 `text_chunk.py`** | `python scripts/srt_chunk.py <srt> --out <dir> --owned N --ctx M [--order en-zh|zh-en]` |

## 通用字幕工具（`srt_*`）

| 脚本 | 用途 | 用法 |
|------|------|------|
| `srt_verify.py` | 核对并重编号修正 SRT（块数/时间码对齐）；**ASR 修正差异工具，非双语翻译稿校验器** | `python scripts/srt_verify.py <orig.srt> <fixed.srt>` |
| `srt_diff.py` | 逐块对比两个 SRT（ts/正文差异） | `python scripts/srt_diff.py <a.srt> <b.srt>` |
| `srt_split.py` | 将双语/多语 SRT 按字段拆分成多个单语文件（`FIELDS` 常量配置行顺序，字段名即输出后缀，加新语言只需添名字） | `python scripts/srt_split.py <双语.srt> [-o 前缀] [-d 目录] [--out 字段=路径]` |

## 回填工作流工具（`srt_reflow_*`，`reflow-redstone` Skill 用）

| 脚本 | 用途 | 用法 |
|------|------|------|
| `srt_reflow.py` | 语义回填确定性时间运算：`reflow`（r03 方案 + 01 → r04 时间轴 + `r03_anchored.jsonl` 锚定明细（JSONL 每行一整句）；整句锚定 + 单元级 cue 锚定 + 分割点就近吸附真实边界 + 100ms 预测点）、`attach-en`（双语组装，英文行 = r03 互斥英文片段）、`check-r03`（r03 写时即合规预检：锚定唯一性 / 拆句互斥 / 行宽 ≤26（软 22 硬 26） / ZH 忠实，违规退出码 1 打回） | `python scripts/srt_reflow.py reflow <r03> <01> [-o r04_draft.srt] [--anchored r03_anchored.jsonl]` / `... attach-en <r04> <r03> [-o r04_bilingual.srt]` / `... check-r03 <r03_results/> <01> <r02_results/> --chunks <chunks/>` |
| `srt_reflow_gap_scan.py` | 空隙探测（长停顿 >5s / 剪辑跳转 >10s）→ `r00_gaps.md` | `python scripts/srt_reflow_gap_scan.py <01> [-o reflow/r00_gaps.md]` |
| `srt_reflow_breaks.py` | r01 硬性断句输入：断句点清单（含 Agent 复核字段）→ `r01_breaks.md` | `python scripts/srt_reflow_breaks.py <01> [-o reflow/r01_breaks.md]` |
| `srt_reflow_check_breaks.py` | r01 硬性断句校验：逐空隙点查句末标点 `.?!`；违规退出码 1（打回信号，受控例外 Agent 裁决）；块级模式（`--chunks <chunks目录> --gaps r00_gaps.md`，复用已验证空隙点清单；N=1 为单块骨架） | `python scripts/srt_reflow_check_breaks.py <01> <r01_results/> --chunks <chunks/> --gaps r00_gaps.md` |
| `srt_reflow_check_words.py` | r01 措辞校验：词序列与 01 一致（不得改动措辞）；块级模式（`--chunks <chunks目录>`，逐块对比块↔cue 区间词序列；N=1 为单块骨架）；difflib 一次列出全部分歧（错词/缺词/多词，不再只报第一处），默认每处一行摘要，`--expand` 展开每处上下文/行号/cue 定位 | `python scripts/srt_reflow_check_words.py <01> <r01_results/> --chunks <chunks/> [--expand]` |
| `srt_reflow_normalize.py` | 块目录归一化（两种输入形态自动检测）：chunks 模式（步骤 3，`## 分区` cue 文本合并 + 折行 → `r01_normalized/`）、纯文本模式（r02 折行副本 **已停用**——由预分句 `srt_reflow_presplit.py` → `r03_normalized_2/` 取代）；折行 ≤1000 字符/行（英文不拆词、中文按字符），一次跑完整个目录，命令只运行一次 | `python scripts/srt_reflow_normalize.py <chunks/> -o reflow/r01_normalized/` |
| `srt_reflow_presplit.py` | 预分句 + ZH 机械化断句（方案 4，步骤 5 分句输入）：EN 按句末标点 `.?!`（`r01_results/`）→ `r03_normalized_1/`（E1..En）；ZH 按句号 `。！？`（`r02_results/` 直读原稿）→ `r03_normalized_2/`（**r03 模板骨架**：Z 句 + 句内切分段预填 [15,22] 硬 ≤26，分句 agent 填空后即 r03_results）；缩写/省略号/括号配平保护；折行合并保留中英/数字空格（`Carpet 的 fillUpdates`、`139 147 11`）；切分标点/句长区间全参数化（`--punct-levels/--soft-min/--soft-max/--hard-max/--min-unit`，默认 CJK）；切分标点按优先级层级（`--punct-levels` 可多次，默认逗号族>顿号>破折号，超宽段才降级）；忠实铁律由结构保证（段只在标点处切、不增删改） | `python scripts/srt_reflow_presplit.py <r01_results/> <r02_results/> -o reflow/` |
| `srt_reflow_build_r03.py` | 脚本断句填回（步骤 5 路径 A 脚本断句，2026-08-21）：由「匹配文件 `r03_matches/`（LLM 句子匹配）+ EN 预分句 `r03_normalized_1/` + ZH 模板骨架 `r03_normalized_2/`」机械生成 `r03_results/`——子单元复用模板子句段（机械断句）、EN 整句按匹配 E 组拼接、子单元 EN 按宽度比例机械切分（互斥拼接 == 整句）；**漏句留空**（匹配未覆盖的 Z/E 句产物写 `> ⚠️ 脚本断句·未匹配` 标记，不静默消失）；退出码 1 = 匹配解析问题 | `python scripts/srt_reflow_build_r03.py <r03_matches/> <r03_normalized_1/> <r03_normalized_2/> -o r03_results/` |
| `srt_reflow_check_sentence_len.py` | r01 补标点质量校验（步骤 3）：按 `.?!` 分句检测补标点质量——**分级告警**：硬（打回）单句逗号 >10（实测 11 逗号 E5/E22 为堆砌）/ 单句 >600 字符 / 句均 >350（断句稀疏）；软（提示复核，不阻断）单句逗号 ≥8 且字符 ≥250（疑似可断句，如 E15 式）；带文件:行号+上下文；退出码 1 = 有硬命中 | `python scripts/srt_reflow_check_sentence_len.py <r01_results/> [--max-comma 10] [--max-sent 600] [--max-avg 350] [--soft-comma 8] [--soft-sent 250] [--verbose]` |
| `srt_reflow_check_terms.py` | r02 术语全量核对：逐条遍历 02_terms.md——01 定位原文出现块 → 该块 r02 译文须含确认译名（变体容错/长术语覆盖）；⚠️/ℹ️ 带文件行号 + 上下文供 Agent 直接核对编辑；退出码 1 = 有未命中（复核后才放行） | `python scripts/srt_reflow_check_terms.py <01> <02_terms.md> <r02_results/> --chunks <chunks/> [--verbose]` |

> `srt_reflow_core/` 是 `srt_reflow.py` 的实现包（io / plan / anchor / allocate / alerts / reflow / attach），**非独立工具，勿直接调用**；入口只有 `srt_reflow.py`。

## 独立工具

| 脚本 | 用途 | 用法 |
|------|------|------|
| `fetch_wiki.py` | MediaWiki API 直连（兜底，MCP 不可用时） | `python scripts/fetch_wiki.py "页面名" ["页面名" ...]` |
| `render_preprocess_prompt.py` | **preprocess 阶段一执行型块级任务 prompt 渲染（会话外落盘 `prompts/`）**：接入 `task-term-recognition`（scan 命中项按 OWNED cue 过滤 + 领域术语集 + ASR 修正映射）/ `task-en-preprocess`（asr_fixes 全局+局部 + 领域术语集）；独立于 reflow 渲染链路 `render_subagent_prompt.py`（reflow 阶段二专用）。**§1.2 查证（`task-term-resolve`）不走本脚本**——研究型单次任务，任务文件即 prompt，派发双引用 | `python scripts/render_preprocess_prompt.py <task> --video <工作目录> [--chunk <k> \| --all] [--scan <scan_terms.txt>] [--glossary <csv...>] [--asr-fixes <局部文件>]` |
| `refresh_cache.py` | 统一入口：检查三类缓存；Mojang/TechMC 自动刷新；Wiki 只告警不自动抓取（Agent 按 wiki-tools 降级链按需刷新） | `python scripts/refresh_cache.py [--force\|--dry-run\|--ttl N]` |
| `check_index_stale.py` | 对比 submodule 当前 commit 与索引记录 commit，报告哪些索引需更新 | `python scripts/check_index_stale.py [--only <repo>]` |
| `setup_editors.py` | 编辑器适配初始化（跨平台，创建 Claude Code 等所需的 symlink） | `python scripts/setup_editors.py [--force]` |

每个脚本的详细说明见 `python <script>.py --help`。

## 安全规则

所有脚本只写入 `.cache/`（Git 忽略），不删除任何文件。需要清理缓存时请用户手动操作。
