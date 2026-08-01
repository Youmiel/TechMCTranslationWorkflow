# 项目级 Agent 指令

## 项目背景

本项目是一个 Minecraft 红石技术视频字幕翻译辅助系统。目标是帮助译者将英文/日文红石技术视频字幕高质量翻译为简体中文。

## 核心原则

1. **本地优先** — 所有逻辑、数据、中间件全部在本地运行，数据不出硬盘
2. **资产即代码** — 知识以纯文本 Markdown 形式存在，可 Git 追踪、可人工审核
3. **渐进增强** — 从纯文件搜索起步，按需引入 RAG、向量索引，不提前过度设计
4. **物理隔离** — 人工精修的核心资产（`knowledge/`）与爬取缓存（`.cache/`）严格分离
5. **术语一致** — 严格遵循 `knowledge/01_terminology/` 中的标准译名
6. **禁止自动删除** — 任何删除文件/目录的操作必须由用户明确发起，Agent 不得主动执行删除。需要清理时，提示用户自行操作。

## 工作流程

翻译红石技术内容时，Agent 应：

1. 加载术语源（按优先级）：
   - `.cache/glossary/<相关类别>.csv`（拆分缓存，使用前运行 `python scripts/glossary_split.py --check`）
   - `knowledge/01_terminology/`（项目术语库，含译名标准、人物、组织）
2. 按三级路由检索知识：`knowledge/` → `.cache/` → MCP Wiki 工具
3. 严谨翻译红石术语，禁止自创译名
4. 遇到未收录术语标记 `[待审核: 原词]`
5. 所有结论附上知识来源

## MCP Wiki 工具

本项目配置了两个 MCP Wiki 工具，配置见 `.vscode/mcp.json`，部署指南见 `docs/MCP_DEPLOYMENT.md`。

- **minecraft-wiki-mcp**（可用）：通过 `L3-N0X/Minecraft-Wiki-MCP` 直连 MediaWiki API（工具 `minecraft_wiki_search` / `minecraft_wiki_get_page` 等）
- **mc-wiki-fetch-mcp**（可用）：`rice-awa/mc-wiki-mcp-pypi` 自定义 API 代理（工具 `search_wiki` / `get_page` 等）

### 兜底策略

当 MCP 工具不可用时，完整降级链与缓存保真阶梯见 `translate-redstone` Skill §「MCP 工具与兜底」（权威）。要点：`python scripts/fetch_wiki.py "页面名"` → 浏览器访问 `https://zh.minecraft.wiki/`（终极兜底）。

### 抓取注意事项

- **中文搜索用英文关键词**：`srsearch=redstone` 正常，`srsearch=红石` 会失败
- **parse 接口正常**：`page=红石` 中文页面名在 path 中无问题

## 参考哲学

本项目遵循 [llm-wiki](https://gist.github.com/442a6bf555914893e9891c11519de94f) 的核心理念：LLM 增量构建并维护一个持久的 Wiki，而非每次从原始文档重新检索。
