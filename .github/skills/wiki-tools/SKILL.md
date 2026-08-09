---
name: wiki-tools
description: Minecraft Wiki 页面获取与缓存写入的规范（MCP 工具降级链、缓存保真阶梯、抓取注意事项、社区资料检索）。翻译工作流阶段一「集中补齐」、或任何需要查询 Wiki/抓取页面的场景使用。
---

# Wiki 抓取与兜底

## 任务指令

- **任务**：按可靠度降级链获取 Minecraft Wiki 页面并写入 `.cache/wiki/`，遵循抓取注意事项与缓存保真阶梯
- **触发**：阶段一「集中补齐」查询术语/机制时；MCP 工具不可用时降级
- **产出**：`.cache/wiki/<规范中文页面名>.md` 缓存 + 术语译名补充
- **关联工具**：`mc-wiki-fetch-mcp` / `minecraft-wiki-mcp`（MCP）、`scripts/fetch_wiki.py`（兜底）、浏览器

## 缓存读取（先查缓存，命中即用）

**查词第一步是读 `.cache/wiki/`，不是联网**。`docs/WIKI_CACHE_FORMAT.md` 是唯一格式规范，读取流程如下：

1. **构造中文命中键**：对待查术语先用术语表（`.cache/glossary/`、`knowledge/`）得到中文译名/候选——缓存文件名 = 中文规范标题，直接以 `缓存文件名` 判定
2. **命中判定**：`.cache/wiki/<中文规范标题>.md` 存在即命中 → 直接读缓存内容，**不再发网络请求**
   - 中文译名缺失（L3 新词）时：用 grep_search 在 `.cache/wiki/` 按**英文关键词**搜正文兜底（如 `红石比较器.md` 正文含 "Comparator"）
   - 反向命中：`knowledge/01_terminology/*.csv` 的「来源」列已引用 `.cache/wiki/<页面>.md`，据此可反查已缓存页面
3. **fidelity 回源判定**：命中后按内容保真度决定是否回源——
   - 查 **ID / 色值 / 历史 / 隐藏注释** → 需 `lossless`；`plain`/`degraded` 时回源 wikitext（`mc-wiki-fetch-mcp` `get_page`）
   - 只看**正文定义 / 机制** → `plain` / `refined` 足够，直接用
4. **未命中才联网**：走下方「Wiki 页面获取」降级链抓取，结果按「缓存写入保真阶梯」落盘，供本视频后续与**跨视频复用**

> **跨视频复用**：`.cache/wiki/` 是全局共享缓存，其它视频抓过的页面直接读，禁止重复联网。

## Wiki 页面获取（按数据源可靠度降级，优先保真度高的源）

1. `mc-wiki-fetch-mcp` → `search_wiki(q)` / `get_page(pageName)`（wikitext，**唯一无损源**，ID 表/色值/历史/隐藏注释全保留，查精确数据/术语定义最可靠）
2. `python scripts/fetch_wiki.py "页面名" ["页面名" ...]`（纯 urllib，正文+版别+数值可读，但**表格被剥离**）
   - 批量调用 MediaWiki API（`titles=A|B|C` 管道符）
   - 结果写入 `.cache/wiki/`，返回 JSON 摘要供 Agent 解析
3. `minecraft-wiki-mcp` → `minecraft_wiki_search(q)` / `minecraft_wiki_get_page(pageName)`（markdown，模板占位/乱码/数值丢，仅快速浏览正文）
4. 浏览器访问 `https://zh.minecraft.wiki/` → 站内搜索 → 阅读页面内容（终极兜底，所有 API 都不可用时）
   - **读取后同样按模板写入 `.cache/wiki/`**（`via: browser`），不得跳过落盘

## 缓存写入保真阶梯（与获取优先级一致，按内容质量选源）

- `mc-wiki-fetch-mcp`（wikitext）→ `fidelity: lossless`，唯一无损源（ID 表/颜色表/历史/隐藏注释全保留），查**精确数据/术语定义**用它最可靠
- Agent 获取后顺手提取要点 + 格式化 → `fidelity: refined`（默认推荐）
- `fetch_wiki.py`（纯文本）→ `fidelity: plain`，正文+版别+数值可读，但**表格被剥离**，查 ID/色值/历史不能信它
- `minecraft-wiki-mcp`（markdown）→ `fidelity: degraded`，三源中最差（模板占位/乱码/数值丢），只适合快速浏览正文
- 缓存文件格式规范见 `docs/WIKI_CACHE_FORMAT.md`；读取 / 回源规则见上「缓存读取」

## 抓取注意事项

- **中文搜索用英文关键词**：`srsearch=redstone` 正常，`srsearch=红石` 会失败
- **parse 接口正常**：`page=红石` 中文页面名在 path 中无问题
- **请求频率控制**（阶段一集中补齐遵守）：
  - 每次 `get_page` 调用之间间隔至少 2 秒
  - 遇到 429/403 错误时指数退避重试（2s → 4s → 8s，最多 3 次）
  - 一个视频的 Wiki 查询通常在 5-15 次，总耗时约 10-30 秒，在合理范围内
- **缓存命名**：文件名用**解析后的中文规范标题**，禁止用英文查询词命名（避免中英文重复缓存）

## 社区资料

非 Wiki 来源（博客、深度分析）优先查 `indexes/repos/` 定位本地仓库文件，不通过网络抓取。

## 相关配置

- MCP 配置：`.vscode/mcp.json`；部署指南：`docs/MCP_DEPLOYMENT.md`
- 数据源擅长/不擅长类型：`docs/SOURCE_COVERAGE.md`；经验沉淀：`.github/experience/source_experience.md`（流水见 `coverage_log.md`）
