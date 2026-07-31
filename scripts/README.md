# 脚本

| 脚本 | 用途 | 用法 |
|------|------|------|
| `split_glossary.py` | 将上游合并术语 CSV 按类别拆分到 `.cache/glossary/` | `python split_glossary.py [--check\|--help]` |
| `fetch_mojang_glossary.py` | 从 Mojang 官方 API 下载最新翻译词汇表 | `python fetch_mojang_glossary.py [--check]` |
| `fetch_wiki.py` | MediaWiki API 直连（兜底，MCP 不可用时） | `python fetch_wiki.py "页面名" ["页面名" ...]` |
| `refresh_cache.py` | 统一入口，检查并刷新三类本地缓存 | `python refresh_cache.py [--force\|--dry-run\|--ttl N]` |
| `setup_editors.py` | 编辑器适配初始化（跨平台，创建 Claude Code 等所需的 symlink） | `python setup_editors.py [--force]` |

每个脚本的详细说明见 `python <script>.py --help`。

## 安全规则

所有脚本只写入 `.cache/`（Git 忽略），不删除任何文件。需要清理缓存时请用户手动操作。
