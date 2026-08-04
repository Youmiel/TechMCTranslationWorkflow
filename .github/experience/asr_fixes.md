# ASR 误识别校正表

> YouTube 自动字幕（ASR）经常误识别技术术语和人名。本文档沉淀已验证的误识别映射，
> 供翻译时快速解码"看起来不像词"的原文。
> 维护：Agent 每次识破新误识别后追加（只追加，不删改既有条目）。
> 使用：阶段〇扫描字幕时，若某词在词典/术语表中找不到，先查本表。


## 使用规则

1. 命中映射 → 用正确词去查术语表/译名，原文行保留 ASR 原文（双语对照时可在中文侧注明正确词）
2. 未命中 → 判断是否可能是 ASR 错误：
   - 词形近似已知 Minecraft 实体/人名/模组名（如 scarpet ≈ scraped）
   - 上下文强烈暗示某机制（如存储视频里出现"烧车"语境）
   - 是 → 登记到本表 + 按正确词处理，标注 `[ASR 推测]` 供用户确认
   - 否 → 正常术语流程
3. 用户确认后，将 `[ASR 推测]` 的条目移入"已验证映射"表


## 格式约定

```
误识别文本 → 正确词（领域/上下文）
```

同一条多个变体合并为一行（`/` 分隔）。

> **时间戳不入库**：字幕时间戳是逐视频的反馈定位信息，仅在向用户反馈（`translate-redstone` §1.3 / 阶段二½）时附带，**不写入本表**——本表跨视频累积，不绑定具体视频。


## 已验证映射

| 误识别（ASR） | 正确 | 说明 |
|---------------|------|------|
| Red Knobs / Red Noms / Knobs / Noms | Red Nomster | 人名 |
| scraped / scarpad | scarpet | Carpet 模组的脚本语言 |
| part eating | cart yeeting（烧车） | 存储科技 Cart Yeet 技术 |
| sorder / sortter / sortters | sorter | 分类器 |
| idol | ideal | — |
| MPT | MSPT | 毫秒每刻 |
| shocker box | shulker box（潜影盒） | — |
| copper counters | hopper counters（漏斗计数器） | — |
| DOSless | dustless（无粉） | — |
| cup golems | copper golems（铜傀儡） | 快照新生物 |
| multi-to solder | multi-item sorter | 多物品分类器 |
| layer snapshot | latest snapshot | 最新快照 |
| wavet's | Wavetech's | 服务器名 |
| costic | caustic | 难缠的（形容物品集） |
| resto | redstone | 红石（装置） |
| levane | Louvain | 鲁汶（图聚类算法） |
| design snapshot | design in snapshot | ASR 漏介词 in |
| Cubic meter | Cubicmetre | 人名（频道名） |
| me old mate | my old mate | 口语语法 |
| are multi-item | a multi-item | 冠词误识别 |
| higherend | higher-end | — |
| sort be | sort bee | 蜂巢（bee nests） |
| item sort of breaks | item sorter breaks | ASR 漏词 |
| free wide tilable | three-wide tileable | 三宽可堆叠 |
| river skulls | wither skulls（凋灵之首） | 世界边界相关实体 |
| slash tv | /tp | 命令（/teleport） |
| gas | ghast | 恶魂 |
| n pillar | end pillar | 末地黑曜石柱 |
| wave tech 7 | wavetech | 服务器名 |
| hearing / in creative | in creative | ASR 多词/漏词 |
| farming creative | farm in creative | ASR 漏介词 |
| comforted | convinced | 确信（"fully convinced"） |
| obscene farm | obsidian farm | 黑曜石农场 |
| shock boxes / shelter boxes | shulker box（潜影盒） | 合并 shocker box 变体 |
| enemy dragon | ender dragon | 末影龙 |
| start farm | end stone farm | 末地石农场 |
| we bought | we built | 口语（"built an obsidian farm"） |
| scared you my stuff up | scared you'll mess my stuff up | ASR 漏词 |
| feel that wither | kill that wither | 击杀凋灵 |
| cars / cards | carts | 矿车（minecart） |
| phone | farm | 农场 |
| rich / original | ritual | 仪式 |
| spy glass | spyglass | 望远镜 |
| skull bucket bucket button | skull bucket button | ASR 叠词 |
| jkm | JKM | 人名（Wavetech 成员） |
| even hon toons | Huntoon's | 人名（Wavetech 成员） |
| [ __ ] it | bucket | 凋灵笼流程语境（"头颅、桶、按钮"口诀），ASR 误听成脏话 |
| results of the year | results of the gear | 用户确认听感；语义存疑（"the gear"仍不明） |


