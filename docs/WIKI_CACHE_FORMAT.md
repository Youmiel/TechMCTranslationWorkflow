# Wiki 页面缓存规范（`.cache/wiki/`）

本文档是 `.cache/wiki/` 的**唯一格式规范**。所有写入该目录的通道（MCP 工具、`fetch_wiki.py`、浏览器兜底）必须遵循本规范。

## 命名规则

- 文件名 = **MediaWiki 解析后的规范标题（中文）**，如 `红石比较器.md`
- 同一页面只保留一份缓存；**禁止**再用英文查询词命名（如 `Redstone_Comparator.md`），以免中英文并存导致重复抓取
- 文件名字符安全化：`/` `\` 空格 替换为 `_`（中文规范标题通常无空格，文件名即标题）
- Agent 的工作方式：先查术语表（`.cache/glossary/`、`knowledge/`）得到中文译名 → 用中文译名命中 `.cache/wiki/` → 未命中才去联网获取

## 文件模板

```markdown
---
title: 红石比较器
url: https://zh.minecraft.wiki/w/红石比较器
fetched: 2026-08-01T00:00:00Z
via: minecraft-wiki-mcp | mc-wiki-fetch-mcp | fetch_wiki | browser
fidelity: lossless | refined | plain | degraded
---

# 红石比较器

> 来源：[Minecraft Wiki](<url>)

<内容>
```

字段说明：

| 字段 | 含义 |
|---|---|
| `title` | 解析后的规范页面标题（= 文件名） |
| `url` | 来源页面 URL |
| `fetched` | 抓取时间（ISO 8601 UTC） |
| `via` | 本次内容的来源通道 |
| `fidelity` | 内容保真度分级，见下 |

## 保真度分级 `fidelity`

| 值 | 含义 | 何时产生 |
|---|---|---|
| `lossless` | 无损：ID 表 / 颜色表 / 历史 / 隐藏注释全保留 | 内容直接来自 wikitext（`mc-wiki-fetch-mcp` 原始返回） |
| `refined` | Agent 整理：可读正文 + 关键数据表保留 | Agent 获取后**顺手提取要点 + 格式化**（默认推荐） |
| `plain` | 纯文本：正文可读，但表格被 API 剥离 | `fetch_wiki.py`（explaintext） |
| `degraded` | 降级：存在模板占位 / 乱码 / 数值丢失 | `minecraft-wiki-mcp`（markdown），仅当其他源不可用时 |

Agent 读缓存时根据 `fidelity` 决定是否回源补精确数据：

- 查 **ID / 色值 / 历史 / 隐藏注释** → 需要 `lossless`，否则回源 wikitext
- 只看**正文定义 / 机制** → `plain` / `refined` 足够

## 写入优先级（保真阶梯）

写入缓存时**按内容保真度优先选源**，而非按工具可用性：

1. **wikitext（`mc-wiki-fetch-mcp`）→ `lossless`** — 首选，唯一无损源
2. **Agent 整理（任意源获取后顺手提取+格式化）→ `refined`**
3. **`fetch_wiki.py` → `plain`**
4. **`minecraft-wiki-mcp`（markdown）→ `degraded`** — 最差，仅当其他源都不可用

## 工具获取优先级（按数据源可靠度）

按数据源可靠度降级（与保真阶梯一致，非"哪个在线"的顺序）：

1. `mc-wiki-fetch-mcp`（MCP-2，wikitext，无损）→ **首选**，唯一无损源
2. `python scripts/fetch_wiki.py "页面名" ["页面名" ...]`（纯文本，正文可读，表格剥离）
3. `minecraft-wiki-mcp`（MCP-1，markdown，降级）→ 仅快速浏览正文
4. 浏览器访问 `https://zh.minecraft.wiki/`（终极兜底；读取后也要按本模板落盘）

## 内容保真约束

- **数值、ID、HEX 色值等精确数据逐字保留，不得改写**
- 不增删事实；不确定的内容显式标注
- 来源链接必须保留
- 版别标记（`[仅Java版]`、`{{only}}` 等）尽量保留
- 隐藏注释（"不完整章节"提示等）尽量保留

## 刷新策略

- 统一入口：`python scripts/refresh_cache.py`（检查三类缓存；Mojang/TechMC 自动刷新）
- Wiki 缓存过期判断：基于文件 mtime，TTL 默认 7 天（`--ttl` 可调）
- **Wiki 缓存只检查过期并告警，不自动抓取**——刷新由 Agent 在查找时按 wiki-tools 降级链按需做（MCP-2 lossless 优先），避免脚本用 `plain` 降级覆盖已有高保真缓存
- `.cache/metadata.json` **已废弃**：时间戳 / 来源由各文件 front matter 承担

## 数据源特征备忘（Agent 实测，2026-08-01）

| 对比项 | MCP-1 `minecraft-wiki-mcp`（markdown） | MCP-2 `mc-wiki-fetch-mcp`（wikitext） | fetch_wiki.py（纯文本） |
|---|---|---|---|
| 模板渲染 | ❌ 变 `:::Template` 占位 | ✅ 完整保留 | ✅ 渲染为可读文本 |
| 乱码 / Lua 错误 | ❌ Base64 乱码、Lua 报错 | ✅ 无 | ✅ 无 |
| 正文段落 | ✅ 可读 | ✅（wikitext 需会读） | ✅ 最干净、最易读 |
| 版别标记 | ⚠️ 部分丢失 | ✅ 完整（`{{only}}`） | ✅ 内联 `[仅Java版]` |
| 概率数值（7⁄9、1⁄8…） | ❌ 变 `{{{1}}}` 占位 | ✅ 完整 | ✅ 完整 |
| ID 表 | ❌ "缺失ID" | ✅ 完整 | ❌ 空 |
| 颜色表 / HEX 色值 | ❌ 占位 | ✅ 完整 | ❌ 丢失 |
| 历史 | ⚠️ 拆散部分丢失 | ✅ 完整 | ❌ 空 |
| 隐藏注释 | ❌ 丢失 | ✅ 保留 | ❌ 丢失 |

三个源**同源**（同一 zh.minecraft.wiki 页面），正文事实一致，保真度呈阶梯分布：查**精确数据/术语定义**用 wikitext（MCP-2）最可靠；查**可读正文**用 fetch_wiki.py；MCP-1（markdown）仅适合快速浏览，模板驱动数据不可信。
