# 项目级 Agent 指令

## 项目背景

本项目是一个 Minecraft 红石技术视频字幕翻译辅助工作流。目标是帮助译者外文红石技术视频字幕高质量翻译为简体中文。

## 项目结构

各目录用途与产物归属约定见 [`docs/PROJECT_STRUCTURE.md`](docs/PROJECT_STRUCTURE.md)。处理或产出文件时，不确定放哪里先查该文档。

## 核心原则

1. **本地优先** — 所有逻辑、数据、中间件全部在本地运行，数据不出硬盘
2. **资产即代码** — 知识以纯文本 Markdown 形式存在，可 Git 追踪、可人工审核
3. **渐进增强** — 从纯文件搜索起步，按需引入 RAG、向量索引，不提前过度设计
4. **物理隔离** — 人工精修的核心资产（`knowledge/`）与爬取缓存（`.cache/`）严格分离
5. **术语一致** — 严格遵循 `knowledge/01_terminology/` 中的标准译名
6. **禁止自动删除** — 任何删除文件/目录的操作必须由用户明确发起，Agent 不得主动执行删除。需要清理时，提示用户自行操作。

## 组织路由

- 翻译工作流 → `translate-redstone` Skill（细节在各扩展 Skill，见其「扩展 Skill 地图」）
- 语义回填工作流 → `reflow-redstone` Skill（共享阶段〇/一/二½/三，见其「依赖（扩展 Skill 地图）」）
- 知识/索引维护 → `maintain-knowledge` Skill（决策路由见其「维护任务决策」）
- Wiki 抓取/兜底 → `wiki-tools` Skill
- **主会话调度纪律（仅约束 translate/reflow 派发-校验阶段）**：零定点编辑、验证性读禁止等 token 纪律权威在 `subagent-dispatch`「主会话读写最小化 / 定点修正」，随两工作流 Skill 引用加载；**maintain-knowledge / wiki-tools 等日常维护不适用、不受影响**

## 工作流程

翻译红石技术内容时，Agent 应：

1. 加载术语源（按优先级）：
   - `.cache/glossary/<相关类别>.csv`（拆分缓存，使用前运行 `python scripts/refresh_cache.py` 统一检查/刷新）
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

当 MCP 工具不可用时，完整降级链与缓存保真阶梯见 `wiki-tools` Skill（权威）。要点：`python scripts/fetch_wiki.py "页面名"` → 浏览器访问 `https://zh.minecraft.wiki/`（终极兜底）。

### 抓取注意事项

抓取降级链、请求频率控制、缓存保真阶梯、抓取注意事项（中文搜英文关键词等）见 `wiki-tools` Skill（权威）。

## 参考理念

本项目遵循 [llm-wiki](https://gist.github.com/442a6bf555914893e9891c11519de94f) 的核心理念：LLM 增量构建并维护一个持久的 Wiki，而非每次从原始文档重新检索。
