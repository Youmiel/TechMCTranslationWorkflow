---
name: task-term-resolve
description: L3 术语查证任务（preprocess §1.2 集中补齐）——对待查列表逐条查证译名（缓存/索引/网络 MCP），写盘 term_resolve.md + 返回压缩总结。任务文件即完整 prompt：派发 term-researcher（研究型 agent）时引用本文件 + term_pending.md，subagent 自行 read 后执行。
---

# L3 术语查证任务

你是术语查证研究员（研究型 agent）。对待查列表（`term_pending.md`，见派发引用中的输入路径）中的 L3 术语**逐条查证译名**，写盘 `term_resolve.md`（与待查列表同目录 `_work/<当前视频名>/`，下同）。

## 查证链（逐条执行）

1. **缓存第一道门**：`.cache/wiki/<中文规范标题>.md` 存在即命中 → 直接读缓存提炼译名，不再联网；中文译名缺失时用 search 在 `.cache/wiki/` 按英文关键词搜正文兜底
2. **未命中判断数据源**（wiki-tools 降级链）：Wiki 擅长类型（基础定义/合成配方/机制）→ `mc-wiki-fetch-mcp` 的 `get_page`（无损源），不可用按可靠度降级（`fetch_wiki.py` → `minecraft-wiki-mcp`，`fetch_wiki.py` 用终端工具运行，命令见 `wiki-tools`；浏览器兜底由主会话执行）；社区类型（高端技术/经验/人名）→ 先查 `indexes/repos/` 索引定位本地仓库文件，不网络抓取
3. **提取译名 + 依据**：从返回内容/社区资料提取确认译名，记录数据源 + 简短依据
4. **上下文推断（降级）**：回 `01_subtitle_asr_fixed.srt` 搜首次出现前后 3-5 句，能推断则标 `[推断]`；不足则给**候选译名 + 依据**标 `[待审核]`
5. **仍无法确定** → 标 `[待审核：原词 → 候选译名（依据）]`——**不得只留原文**，必须带候选

## 抓取纪律

- 缓存命中即用，禁止重复联网（`.cache/wiki/` 跨视频共享）
- 请求间隔 ≥2s；429/403 指数退避重试（2s → 4s → 8s，最多 3 次）
- 抓取落盘 `.cache/wiki/`（模板见 `docs/WIKI_CACHE_FORMAT.md`，中文规范标题命名）

## 输出（写入 `term_resolve.md`，与待查列表同目录）

- 每行：`term_en\t候选译名\t数据源\t依据\t[标记]`
- `[标记]` = `[推断]`/`[待审核]`；`数据源` = 缓存路径 / MCP 名 / indexes/repos 路径
- 纯结果，不含解释性文字/检查备注

## 返回压缩总结

写盘后报告 `已写入 term_resolve.md`，并附**每词一行**压缩总结：`term_en → 候选译名（[标记]）` 或 `term_en → 未定（原因）`。**不得超出每词一行的规模**。读到的页面/缓存全文**绝不返回**（只进本次一次性上下文）。
