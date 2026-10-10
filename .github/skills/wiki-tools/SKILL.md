---
name: wiki-tools
description: Minecraft Wiki 页面获取与缓存写入的规范（MCP 工具降级链、缓存保真阶梯、缓存过期与主动刷新、抓取注意事项、社区资料检索）。翻译工作流阶段一「term-scan#集中补齐」、或任何需要查询 Wiki/抓取页面的场景使用。
---

# Wiki 抓取与兜底

## 任务指令

- **任务**：按可靠度降级链获取 Minecraft Wiki 页面并写入 `.cache/wiki/`，遵循抓取注意事项与缓存保真阶梯；**命中的缓存若已过期，先主动刷新再读取**
- **触发**：阶段一「term-scan#集中补齐」查询术语/机制时；翻译过程中任何需请求 Wiki 的场合；MCP 工具不可用时降级
- **产出**：有留存价值时写 `.cache/wiki/<规范中文页面名>.md` 缓存（新增或刷新）+ 术语译名补充；派发场景另写 `_work/<视频名>/wiki_resolve_<i>.md`
- **关联工具**：`mc-wiki-fetch-mcp` / `minecraft-wiki-mcp`（MCP，只读不存）、`scripts/fetch_wiki.py`（抓取 + 刷新 + **保存落盘**，官方 API 直连）、`scripts/refresh_cache.py --check-page`（过期判定）、浏览器
- **派发载体**：`wiki-researcher`（研究型 agent）+ `task-wiki-query.md`（任务文件即完整 prompt）——需要抓取/长内容阅读的查询一律派发，主会话不读页面全文

## 缓存读取

**查词第一步是读 `.cache/wiki/`，不是联网**。`docs/WIKI_CACHE_FORMAT.md` 是唯一格式规范，读取流程如下：

1. **构造中文命中键**：对待查术语先用术语表（`.cache/glossary/`、`knowledge/`）得到中文译名/候选——缓存文件名 = 中文规范标题，直接以 `缓存文件名` 判定
2. **命中判定**：`.cache/wiki/<中文规范标题>.md` 存在即命中，**不再发网络请求**
   - 中文译名缺失（L3 新词）时：用**全文搜索工具**在 `.cache/wiki/` 按**英文关键词**搜正文兜底（如 `红石比较器.md` 正文含 "Comparator"）
   - 反向命中：`knowledge/01_terminology/*.csv` 的“来源”列已引用 `.cache/wiki/<页面>.md`，据此可反查已缓存页面
3. **过期判定（命中后必做，不得跳过）**：跑 `python scripts/refresh_cache.py --check-page "<页面名>" [...]`——它输出每页 `fetched` 时间与状态（`未过期` / `过期` / `未缓存`），退出码 1 = 有需处理项
   - **`过期` 且该查询依赖页面内容 → 先主动刷新再读**：`python scripts/fetch_wiki.py --refresh "<页面名>"`（wikitext/lossless 直连、保持高保真），成功后重读缓存
   - **`过期` 但该查询不依赖内容时效**（如事实已稳定）→ 可继续用，但后续若涉版本敏感结论必须刷新
   - **`未缓存`** → 走下方「Wiki 页面获取」降级链抓取
   - 判定不要靠 mtime 直觉或记忆：`fetched` 是声明的事实源（缺失回退 mtime），TTL 默认 7 天
4. **fidelity 回源判定**：命中后按内容保真度决定是否回源——
   - 查 **ID / 色值 / 历史 / 隐藏注释** → 需 `lossless`；`plain`/`degraded` 时回源 wikitext（`mc-wiki-fetch-mcp` `get_page`）
   - 只看**正文定义 / 机制** → `plain` / `refined` 足够，直接用
5. **未命中才联网**：走下方「Wiki 页面获取」降级链抓取；结果**是否有留存价值**按「读取通道与落盘通道」判定，需留存才落盘，供本视频后续与**跨视频复用**

> **跨视频复用**：`.cache/wiki/` 是全局共享缓存，其它视频抓过的页面直接读，禁止重复联网；**但复用的缓存同样要过第 3 步过期判定**——旧缓存不因跨视频复用而免检。
> **缓存不因“查过”而产生**：MCP 读取不留痕迹，未落盘的查询下次仍是「未缓存」，过期判定链也无从生效。

## 缓存过期与主动刷新

> 缓存保真 ≠ 缓存新鲜。命中缓存只是省下了“有没有”的判断，**内容是否仍准确必须另行判定**。翻译质量直接取决于术语/机制描述是否与当前版本一致，过期缓存的静默复用是最隐蔽的错误来源，必须主动刷新。

- **过期判定（单页）**：`python scripts/refresh_cache.py --check-page "<页面名>" [...]`
  - 输出每页状态 + `fetched` 时间（如 `fetched=2026-08-01T00:00:00Z（43.0 天前）`）；退出码 1 = 有需处理项
  - 页面名可用缓存文件名（`红石比较器`）或 front matter `title`；支持一次多页
- **主动刷新（单页/多页，保真度不降）**：`python scripts/fetch_wiki.py --refresh "<页面名>" [...]`
  - 官方 MediaWiki API 直连抓 wikitext 写盘（`fidelity: lossless`），**不经 MCP 工具**（避免大量 wikitext 涌入 Agent 上下文），刷新后缓存保真度只会维持或提升
  - `--dry-run` 只探测规范标题与体积（不写盘）、不带页面名则刷新**全部**现缓存（维护场景，见 `maintain-knowledge`）
  - 刷新后**重新读缓存**取新内容；规范名变化的告警需按 「WIKI_CACHE_FORMAT.md#命名规则」处理
- **何时必须刷新**（主动刷新触发条件）：
  1. 该页已过期且本轮查询要从中取结论（术语译名、机制描述、数值）
  2. 只能命中 `plain`/`degraded` 但查询需精确数据——先刷新拿 `lossless`，比回源 MCP 更省上下文
  3. 同一页面在**同一视频内被二次查询**且间隔较久，先用判定命令确认再利用
- **何时可不刷新**：查询只用于确认“某词存在/某链接有效”且结论不依赖版本；或刷新失败时的降级（必须显式标注数据来源与 `fetched` 时间，不得静默使用）
- **刷新失败的降级**：`fetch_wiki.py --refresh` 报错（网络/规范名不匹配）→ 回退「Wiki 页面获取」降级链抓取，并在结论中标注保真度与时间
- **批量维护**：全量刷新属维护动作，由用户在 `maintain-knowledge` 场景触发，不在单次翻译中做

## 任务文件与派发

> 需要抓取页面 / 阅读长内容的 Wiki 查询**一律派 `wiki-researcher`（研究型 agent）**，主会话不读页面全文（token 纪律见 [subagent-dispatch#主会话读写最小化](../subagent-dispatch/SKILL.md#主会话读写最小化)）。
>
> **任务文件自带完整纪律**（查询链 / 刷新规则 / 终端白名单 / 输出与只读边界）——不等同于执行型任务（无纪律母版拼接），**agent 定义不可用/未迁移时任务文件仍可独立执行**（通用性优先）。

- **任务文件**：`task-wiki-query.md`（本目录）——含任务规则、缓存读取与刷新链路、输出契约；**任务文件即完整 prompt**，不追加执行型纪律母版
- **派发方式**：`wiki-researcher` + 任务文件 + 待查清单/问题（双引用），subagent 先读两者再执行
- **产物**：`_work/<视频名>/wiki_resolve_<i>.md`（与待查清单 `wiki_pending_<i>.md` 同名前缀）+ 返回每问一行压缩总结
- **与术语查证的分工**：术语译名查证走 `term-scan/task-term-resolve.md` + `term-researcher`（产物 `term_resolve_<i>.md`）；本任务面向**非术语查证**的 Wiki 请求（机制细节、数值核对、版本行为对比、页面存在性核查、翻译中临时追问）
- **不适用本任务**：纯术语译名清单批量查证（走 `task-term-resolve.md`，产物契约不同）

## Wiki 页面获取

1. `mc-wiki-fetch-mcp` → `search_wiki(q)` / `get_page(pageName)`（wikitext，**lossless**，ID 表/色值/历史/隐藏注释全保留）——**需 Agent 直接阅读内容并判断**时用它；**读取不落盘**，需留存时另跑下方第 2 项保存命令
2. `python scripts/fetch_wiki.py --wikitext "页面名" ["页面名" ...]`（**官方 MediaWiki API 直连**，wikitext，**lossless**、与上一行同数据源）
   - 逐页抓取（wikitext 体量大，不批量）、间隔 ≥2s；结果写入 `.cache/wiki/`，返回 JSON 摘要供 Agent 解析
   - **刷新缓存 / 保存落盘 / 批量抓取 / 避免 wikitext 涌入上下文**时用它（内容只落盘）
   - 只要可读正文时去掉 `--wikitext`（`explaintext` 模式 → `fidelity: plain`，表格被剥离）
3. `minecraft-wiki-mcp` → `minecraft_wiki_search(q)` / `minecraft_wiki_get_page(pageName)`（markdown，模板占位/乱码/数值丢，仅快速浏览正文）
4. 浏览器访问 `https://zh.minecraft.wiki/` → 站内搜索 → 阅读页面内容（终极兜底，所有 API 都不可用时）
   - 若判定该页有留存价值，按「读取通道与落盘通道」落盘（首选 `scripts/fetch_wiki.py --wikitext`，保证 `lossless`；无网络工具时才手工按模板写 `via: browser`）

## 读取通道与落盘通道

> **MCP 只读不存**：`mc-wiki-fetch-mcp` / `minecraft-wiki-mcp` 的返回只用于当场判断与提取结论，**不自动形成 `.cache/wiki/` 缓存**。需要留存时，由执行者**额外调用保存命令**落盘。

- **保存命令**：`python scripts/fetch_wiki.py --wikitext "<页面名>"`——与 `mc-wiki-fetch-mcp` 同数据源（官方 MediaWiki API）、同为 `lossless`，但**内容只落盘、不进上下文**
  - 已用 MCP 读过该页时，保存命令是**第二次请求**（同页间隔 ≥2s 后再跑）——这是有意代价：换无损缓存 + 零上下文成本
  - 浏览器兜底读过页面后，若官方 API 仍可用，同样优先用它落盘，避免复述全文
- **有留存价值 → 落盘**，判据是**之后还要引用该页内容**：
  1. 该页的机制 / 数值 / 版本行为会被本次翻译的其它块或后续工序引用
  2. 该页值得跨视频复用（通用方块 / 机制 / 术语表页）
  3. 后续需以该页缓存做时效判定（`refresh_cache.py --check-page`）
- **无留存价值 → 不落盘**，结论落盘即可：
  1. 仅核对页面存在性或官方译名，结论已写入 `02_terms.md` / `term_resolve_<i>.md` / `wiki_resolve_<i>.md`
  2. 页面全文对后续无用途的一次性追问
- 落盘后的命中路径与保真规则同「缓存读取」；**未落盘的查询不产生缓存**，下次仍需联网

## 缓存写入保真阶梯

- `mc-wiki-fetch-mcp`（wikitext）→ `fidelity: lossless`，无损源（ID 表/颜色表/历史/隐藏注释全保留），查**精确数据/术语定义**用它最可靠
- `fetch_wiki.py --wikitext`（官方 API wikitext）→ `fidelity: lossless`，与上一行同数据源、更省上下文（不进 MCP 返回），刷新场景首选
- Agent 获取后顺手提取要点 + 格式化 → `fidelity: refined`（默认推荐）
- `fetch_wiki.py`（explaintext 默认）→ `fidelity: plain`，正文+版别+数值可读，但**表格被剥离**，查 ID/色值/历史不能信它
- `minecraft-wiki-mcp`（markdown）→ `fidelity: degraded`，三源中最差（模板占位/乱码/数值丢），只适合快速浏览正文
- 缓存文件格式规范见 `docs/WIKI_CACHE_FORMAT.md`；读取 / 回源规则见上「缓存读取」
- **保真度只升不降（脚本强制）**：`fetch_wiki.py` 默认**拒绝**用低保真内容覆盖已有高保真缓存（如 `plain` 覆盖 `lossless` 会丢表格/色值/历史）——遇拒绝改用 `--wikitext` / `--refresh`（lossless）；确需强制加 `--force`
- 请求身份（UA 联系方式）属**环境配置**，见 [`docs/SETUP.md`](../../../docs/SETUP.md#请求身份)

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

- MCP 配置：`.vscode/mcp.json`；部署指南：`docs/SETUP.md`
- 数据源擅长/不擅长类型：`docs/SOURCE_COVERAGE.md`；经验沉淀：`.github/experience/source_experience.md`（流水见 `coverage_log.md`）
