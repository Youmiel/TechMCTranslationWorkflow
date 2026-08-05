# 脚本

按用途分组，文件名前缀标识类别（`glossary_` 术语词表、`srt_` 字幕流水线）；独立工具保留原名。

## 术语词汇表工具（`glossary_*`）

| 脚本 | 用途 | 用法 |
|------|------|------|
| `glossary_split.py` | 将上游合并术语 CSV 按类别拆分到 `.cache/glossary/` | `python scripts/glossary_split.py [--check\|--help]` |
| `glossary_fetch_mojang.py` | 从 Mojang 官方 API 下载最新翻译词汇表 | `python scripts/glossary_fetch_mojang.py [--check]` |
| `glossary_lookup.py` | 按 L1→L1.5→L2 查术语中文译名（只读） | `python scripts/glossary_lookup.py <term> [<term> ...]` |

> `mojang_glossary/` 是 `glossary_fetch_mojang.py` 的实现包（内部逻辑），**非独立工具，勿直接调用**；`__init__.py`、`LICENSE` 非工具。

## 字幕流水线工具（`srt_*`，`translate-redstone` Skill 用）

| 脚本 | 用途 | 用法 |
|------|------|------|
| `srt_check_width.py` | 检查 SRT 中文行视觉宽度（translate-redstone 行宽规则；`--order` 指定双语语言顺序） | `python scripts/srt_check_width.py <draft.srt> [--warn 24] [--order en-zh|zh-en]` |
| `srt_check_segments.py` | 校验分段/成稿时间约束：相邻段时间不重叠、时间边界 ⊆ 原边界集、段序不逆序、cue 覆盖完整（segment-subtitles Skill 用；`03_segments.md` 的 `~`=估算切分点；`--cue-exact` 用于 01 修正字幕：cue 数一致 + 逐 cue 时间戳与原始完全一致，输出目标/原始时间戳供返工） | `python scripts/srt_check_segments.py <目标> --orig <原字幕.srt> [--allow-estimated] [--cue-exact]` |
| `srt_chunk.py` | 长视频按「N 负责 + M 上下文」分块（segment-subtitles Skill 用） | `python scripts/srt_chunk.py <srt> --out <dir> --owned N --ctx M [--order en-zh|zh-en]` |
| `srt_verify.py` | 核对并重编号修正 SRT（块数/时间码对齐）；**ASR 修正差异工具，非双语翻译稿校验器** | `python scripts/srt_verify.py <orig.srt> <fixed.srt>` |
| `srt_diff.py` | 逐块对比两个 SRT（ts/正文差异） | `python scripts/srt_diff.py <a.srt> <b.srt>` |
| `split_subtitles.py` | 将双语/多语 SRT 按字段拆分成多个单语文件（`FIELDS` 常量配置行顺序，字段名即输出后缀，加新语言只需添名字） | `python scripts/split_subtitles.py <双语.srt> [-o 前缀] [-d 目录] [--out 字段=路径]` |

## 独立工具

| 脚本 | 用途 | 用法 |
|------|------|------|
| `fetch_wiki.py` | MediaWiki API 直连（兜底，MCP 不可用时） | `python scripts/fetch_wiki.py "页面名" ["页面名" ...]` |
| `refresh_cache.py` | 统一入口，检查并刷新三类本地缓存 | `python scripts/refresh_cache.py [--force\|--dry-run\|--ttl N]` |
| `check_index_stale.py` | 对比 submodule 当前 commit 与索引记录 commit，报告哪些索引需更新 | `python scripts/check_index_stale.py [--only <repo>]` |
| `setup_editors.py` | 编辑器适配初始化（跨平台，创建 Claude Code 等所需的 symlink） | `python scripts/setup_editors.py [--force]` |

每个脚本的详细说明见 `python <script>.py --help`。

## 安全规则

所有脚本只写入 `.cache/`（Git 忽略），不删除任何文件。需要清理缓存时请用户手动操作。
