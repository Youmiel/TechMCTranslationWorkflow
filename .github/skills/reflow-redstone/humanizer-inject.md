---
name: humanizer-inject
description: 字幕翻译去翻译腔/去 AI 味注入版（subagent 用）——字幕场景翻译腔清单（同词重复/句式直译/功能词机械直译）+ 简短 AI 词清单 + 真实「翻译腔 vs 自然」对照示范。供翻译/润色 subagent 派发时注入（reflow task-translate、translate 阶段二+）。通用文章去 AI 味全量版见 humanizer-zh Skill（submodule，主会话/审核深读用）。
---

# 字幕翻译去翻译腔（subagent 注入版）

目标不是"翻译正确"，而是**读起来像这个视频的主播在说中文**。按下面做，最后照第三节对照自查。

## 一、字幕翻译腔（重点——字幕最常见的问题）

### 1. 英文高频词别机械直译（同段出现 2 次以上必有问题：留一个，其余删或用变体）

| 英文 | 别翻成 | 处理 |
|---|---|---|
| quickly | 快速/很快 | 变体：赶紧/麻利/顺手/几下子；或省译（"快速检查一下"→"检查下"） |
| then | 然后 | 中文靠语序连句，多数"然后"删掉 |
| so | 所以 | 句首/句间的"所以"多数删掉，靠上下文 |
| corresponding | 对应的 | "那套坐标/跟它配对的/挨着的"，或重写整句 |
| basically/actually/really | 基本上/实际上/真的 | 一句至多一个，其余删 |
| grab/get | 拿/得到 | 变体：拎过来/整来/弄到手 |

### 2. 不镜像英文语序

- "create your own end portal for quick travel" 别翻"创建你自己的末地传送门用于快速旅行" → "自己搭个末地传送门快速传送"
- "the corresponding coordinates" 别翻"对应的坐标" → "那套坐标/跟它配对的"
- 英文主谓宾长句 → 中文拆短句、按"先说谁/后说谁"重排
- 英文抽象概念词（corresponding/relative/position）口语里不存在，用"那个/这套/挨着的"顶替

### 3. 通用 AI 味（只列最常犯的）

- 不用 AI 词：此外/至关重要/深入探讨/增强/强调/令人叹为观止/迷人的/不断演变的格局/标志着
- 不用三段式堆叠（"无缝、直观、强大"）、否定式排比（"不仅是…更是…"）
- 不写通用积极结论收尾（"这很有价值/令人印象深刻"）
- 不加粗、不加 emoji、不用破折号串长句

## 二、正向要求（要做的）

- 保留字幕口语感与节奏：短句有力、长句从容，混合长度
- 有观点：对内容有真实态度（"其实我觉得脚手架式更划算"）
- 保留主播的口头禅、自嘲、"我也不确定"式的话，别抹平
- 允许适度「我」；直接陈述，跳过软化/辩解/引导

## 三、对照示范（示例取自已验收的老项目 SciCraft 命令方块视频译文，是过审的自然中文）

**示范 1（翻译腔 vs 自然）**

英文原句：
> basically the key to going multi-threading is glass, so for some reason glass creates a new thread every time it's placed

✗ 翻译腔（机械直译、功能词照搬）：
> 基本上实现多线程的关键是玻璃，所以出于某种原因，玻璃每次被放置时都会创建一个新线程。

✓ 自然（省译 so、变体、语序重排）：
> 但实现多线程的关键就是玻璃。不知为何，玻璃有个奇怪的特性：每次放置它，都会新建一个线程。

**示范 2（口语化处理）**

英文原句：
> you can just place them down wherever you want and create your own end portal for quick travel

✓ 自然：
> 你可以想放哪就放哪，自己搭个末地传送门快速传送。

> 全量通用版（文章写作去 AI 味，24 模式 + 更多改写示例）见 `humanizer-zh` Skill（submodule，主会话/审核深读用）。
