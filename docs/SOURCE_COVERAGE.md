# 第二类知识源覆盖范围指南

> 第二类知识 = 所有需要网络请求获取的内容（Wiki、社区网页等）或可脚本生成的缓存（Mojang 词汇表）。
> Agent 无法在请求前预知数据源内容，本文档帮助判断"什么去哪个源找"。
>
> 经验积累：每次翻译任务后，Agent 在阶段三向 `.github/experience/coverage_log.md` 追加流水，并向 `.github/experience/source_experience.md` 提炼可复用结论。

## Mojang 官方词汇表（`.cache/mojang/redstone.csv`）

> **来源**：Mojang 官方 API → `scripts/glossary_fetch_mojang.py` 自动下载。
> **权威性**：最高——这是 Minecraft 中文版的官方译名，不可覆盖。

适用范围：
- 所有物品/方块的**标准中文名称**（如 Redstone Comparator → 红石比较器）
- 仅覆盖游戏内正式名称，不含社区俗称或技术术语

使用规则：
- 若 Mojang 有译名 → **必须使用**，不得自创
- 若 Mojang 无译名（如社区术语 "BUD"）→ 查 TechMC Glossary 或 Wiki
- 运行 `python scripts/glossary_fetch_mojang.py` 检查并获取最新版本

## Wiki（MCP: `get_page` / `search_wiki`）

> **反爬注意**：本系统通过 MCP 代理访问 Wiki（非直连），单次翻译仅 5-15 次查询，
> 请求间间隔 ≥2 秒，行为接近人类查阅资料。不进行大规模爬取。
> 若遇 429/403，指数退避重试（2s→4s→8s，最多 3 次）。

Wiki 擅长（优先查询）：
- 方块/物品基础属性（合成、爆炸抗性、可堆叠等）
- 基础机制官方定义（比较器模式、信号传输规则）
- 版本更新内容（新增特性、机制变更）
- 方块状态与数据值
- 历史版本行为变化记录

Wiki 不擅长（优先查 `_repos/` 或 `knowledge/`）：
- 高端技术优化设计（如高频脉冲极限时序、最优布线）
- 经验总结与最佳实践
- Bug/特性深度技术分析（更新抑制、光照抑制原理）
- 社区术语与俗称
- 跨版本兼容性细微差异对比
- 模组机制（Carpet、Lithium 等）
- 概率/效率测算数据

## 社区网页 / 博客（+ wiki 网页 API，兜底用）

适用于：
- Wiki 未覆盖的深度技术文章
- 玩家个人博客的经验总结
- 特定版本的 Bug 分析

注意事项：
- 优先确认授权状态
- 仅提取客观事实，用自己的语言重组
- 结果写入 `.cache/community/`

## 决策流程

```
待查概念
├─ "XX的标准中文名是什么"？ → Mojang (.cache/mojang/redstone.csv) → knowledge/
├─ "XX是什么""XX怎么合成"？ → Wiki (.cache/wiki/ 或 MCP get_page)
├─ "XX的最优设计""XX效率多少"？ → _repos/（查 indexes/repos/ 定位）
├─ "XX的译名是什么"（社区术语）？ → .cache/glossary/ → knowledge/
├─ "XX的Bug原理"？ → _repos/（Discovering-Minecraft 等）
├─ 玩家全新发现、任何外部源都无记录？ → 视频原文上下文推断
│    └─ 技术视频常以"今天介绍一个新发现..."开头，字幕本身包含定义
│    └─ Agent 标记为 `[推断：原词 — 基于视频上下文]`，用户确认
└─ 不确定？ → 先 Wiki 获取基础定义，再 _repos/ 获取深度分析
```

## 视频原文（无法联网时、全新知识时）

当所有外部数据源都失败，且术语属于玩家全新发现时，字幕对白本身即数据源：

- 搜索术语首次出现位置，提取前后 3-5 句
- 判断是否存在解释性语句（"这就是...""我们称之为...""它的原理是..."）
- 从上下文推断译名，标记为 `[推断]` 而非 `[待审核]`
- 用户确认后，可将该术语登记到 `knowledge/01_terminology/_uncategorized.csv`
