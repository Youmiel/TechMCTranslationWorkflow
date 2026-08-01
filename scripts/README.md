# 脚本

按用途分组，文件名前缀标识类别（`glossary_` 术语词表、`srt_` 字幕流水线）；独立工具保留原名。

## 术语词汇表工具（`glossary_*`）

| 脚本 | 用途 | 用法 |
|------|------|------|
| `glossary_split.py` | 将上游合并术语 CSV 按类别拆分到 `.cache/glossary/` | `python scripts/glossary_split.py [--check\|--help]` |
| `glossary_fetch_mojang.py` | 从 Mojang 官方 API 下载最新翻译词汇表 | `python scripts/glossary_fetch_mojang.py [--check]` |
| `glossary_lookup.py` | 按 L1→L1.5→L2 查术语中文译名（只读） | `python scripts/glossary_lookup.py <term> [<term> ...]` |

## 字幕流水线工具（`srt_*`，`translate-redstone` Skill 用）

| 脚本 | 用途 | 用法 |
|------|------|------|
| `srt_check_width.py` | 检查 SRT 中文行视觉宽度（skill 行宽规则） | `python scripts/srt_check_width.py <draft.srt> [--warn 24]` |
| `srt_verify.py` | 核对并重编号修正 SRT（块数/时间码对齐） | `python scripts/srt_verify.py <orig.srt> <fixed.srt>` |
| `srt_diff.py` | 逐块对比两个 SRT（ts/正文差异） | `python scripts/srt_diff.py <a.srt> <b.srt>` |

## 独立工具

| 脚本 | 用途 | 用法 |
|------|------|------|
| `fetch_wiki.py` | MediaWiki API 直连（兜底，MCP 不可用时） | `python scripts/fetch_wiki.py "页面名" ["页面名" ...]` |
| `refresh_cache.py` | 统一入口，检查并刷新三类本地缓存 | `python scripts/refresh_cache.py [--force\|--dry-run\|--ttl N]` |
| `setup_editors.py` | 编辑器适配初始化（跨平台，创建 Claude Code 等所需的 symlink） | `python scripts/setup_editors.py [--force]` |

每个脚本的详细说明见 `python <script>.py --help`。

## 安全规则

所有脚本只写入 `.cache/`（Git 忽略），不删除任何文件。需要清理缓存时请用户手动操作。
