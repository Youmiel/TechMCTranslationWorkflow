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
| `srt_reflow_check_words.py` | r01 措辞校验：词序列与 01 一致（不得改动措辞）；块级模式（`--chunks <chunks目录>`，逐块对比块↔cue 区间词序列；N=1 为单块骨架） | `python scripts/srt_reflow_check_words.py <01> <r01_results/> --chunks <chunks/>` |
| `srt_reflow_normalize.py` | 块目录归一化（两种输入形态自动检测）：chunks 模式（步骤 3，`## 分区` cue 文本合并 + 折行 → `r01_normalized/`）、纯文本模式（步骤 5，r02 译文**复制 + 折行** → `r02_normalized/`）；折行 ≤1000 字符/行（英文不拆词、中文按字符），一次跑完整个目录，命令只运行一次 | `python scripts/srt_reflow_normalize.py <chunks/> -o reflow/r01_normalized/` / `<r02_results/> -o reflow/r02_normalized/` |
| `srt_reflow_check_terms.py` | r02 术语全量核对：逐条遍历 02_terms.md——01 定位原文出现块 → 该块 r02 译文须含确认译名（变体容错/长术语覆盖）；⚠️/ℹ️ 带文件行号 + 上下文供 Agent 直接核对编辑；退出码 1 = 有未命中（复核后才放行） | `python scripts/srt_reflow_check_terms.py <01> <02_terms.md> <r02_results/> --chunks <chunks/> [--verbose]` |

> `srt_reflow_core/` 是 `srt_reflow.py` 的实现包（io / plan / anchor / allocate / alerts / reflow / attach），**非独立工具，勿直接调用**；入口只有 `srt_reflow.py`。

## 独立工具

| 脚本 | 用途 | 用法 |
|------|------|------|
| `fetch_wiki.py` | MediaWiki API 直连（兜底，MCP 不可用时） | `python scripts/fetch_wiki.py "页面名" ["页面名" ...]` |
| `refresh_cache.py` | 统一入口：检查三类缓存；Mojang/TechMC 自动刷新；Wiki 只告警不自动抓取（Agent 按 wiki-tools 降级链按需刷新） | `python scripts/refresh_cache.py [--force\|--dry-run\|--ttl N]` |
| `check_index_stale.py` | 对比 submodule 当前 commit 与索引记录 commit，报告哪些索引需更新 | `python scripts/check_index_stale.py [--only <repo>]` |
| `setup_editors.py` | 编辑器适配初始化（跨平台，创建 Claude Code 等所需的 symlink） | `python scripts/setup_editors.py [--force]` |

每个脚本的详细说明见 `python <script>.py --help`。

## 安全规则

所有脚本只写入 `.cache/`（Git 忽略），不删除任何文件。需要清理缓存时请用户手动操作。
