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


## SciCraft Getting Command Blocks In Survival (6sPS4yqC72I)

### 已验证映射

| 误识别（ASR） | 正确 | 说明 |
|---------------|------|------|
| christopher paolini | Christopher Paolini | 人名（嘉宾，作家） |
| eldridge mc | ElRichMC | 人名（SciCraft 成员） |
| myron / myren | Myren | 人名（SciCraft 成员，JKM 搭档） |
| pingu | Pingu | 人名（SciCraft 成员） |
| coolman / cool then | Coolman | 人名（SciCraft 成员） |
| kirby | Kirby | 人名（SciCraft 成员） |
| starcraft | SciCraft | 服务器名 |
| cyborg / cyclops | SciCraft | 服务器名（"SciCraft member"） |
| x-com / xcom | XCOM | 人名（SciCraft 成员） |
| earth computer cheater codes | EarthComputer / CheaterCodes | 人名（两个 SciCraft 成员） |
| following | falling | 落沙（"falling block" 高频被听错） |
| volume blocks | falling blocks | 落沙方块 |
| beaten / beating | beacon | 信标（"beacon tower"） |
| sugar box / shocker box | shulker box | 潜影盒（合并既有 shocker box 变体） |
| dandarak | netherrack | 下界岩 |
| widow | wither | 凋灵 |
| overwatch | overworld | 主世界 |
| wharf border / word butter | world border | 世界边界 |
| nk21 | portal cooldown | 传送门冷却 |
| box 36 | Block 36 | 移动方块 |
| piston club | piston clock | 活塞时钟 |
| sans / sand | sand | 沙子 |
| regul | Regou | 人名, SciCraft 成员 |
| cyborg members / cyclops members | SciCraft members | 服务器名误听 |
| a cyborg member | SciCraft member | 同上 |
| the n dimension | the end dimension | 末地维度（c1133，用户确认；上下文为末地传送门/末地折跃门坐标） |
| word hearing into a box eight core option | word tear | 字撕裂（c1178，1.12.2 术语） |

### [ASR 推测]（待逐块 subagent 确认）

| 误识别（ASR） | 正确 | 说明 |
|---------------|------|------|
| i sound is creaking | a sand is creating | 落沙生成语境（c103） |
| fine suns / fine sounds | falling sand / falling blocks | 落沙/落沙方块 |
| beaten tower | beacon tower | 信标塔 |
| volume docs | falling blocks | 落沙方块 |
| form block | falling block | 落沙方块 |
| funding blocks | falling blocks | 落沙方块 |
| phoning blocks | falling blocks | 落沙方块 |
| following sand | falling sand | 落沙 |
| palace down there | palette down there | 方块调色板语境 |
| palette of blogs | palette of blocks | 方块调色板 |
| word staring thing | word tear thing | 字撕裂（1.12.2 术语） |
| misalignment | mycelium | 菌丝 |
| head bottle | eye of ender | 末影之眼 |
| dragon axe / dragon x | dragon egg | 龙蛋 |
| weapon dogs | wither skeletons | 凋灵骷髅 |
| weapon | wither | 凋灵 |
| pressure | suppressor | 更新抑制器 |
| update to pressure | update suppressor | 更新抑制器 |
| important extra update to pressure | important extra update suppressor | 更新抑制器 |
| ac chunk / 18 chunk | async chunk | 异步区块（重载） |
| cluster change / cluster shank | cluster chunk | 集群区块 |
| plus a chunk | cluster chunk | 集群区块 |
| few hundred plus | few hundred cluster chunks | 集群区块 |
| four peaking blocks | beacons | 信标 |
| the buildings | the beacons | 信标 |
| without any weakness in / without any beatings / they didn't use speaking | without any beacons / they didn't use beacons | 信标 |
| five thousand beatens | five thousand beacons | 信标 |
| mainframe | main thread | 主线程 |
| three frets | three threads | 线程 |
| first running at once | threads running at once | 线程 |
| a contraction | a contraption | 机器/装置 |
| the contract will be shot | the contraption built | 机器/装置 |
| where contraption whenever | we have a contraption which | 机器/装置 |
| endpoint frame / input frame / airport frame / n portal frames / place and portal frames / falling end for the frame | end portal frame | 末地传送门框架 |
| end port | end portal | 末地传送门 |
| airport | end portal | 末地传送门 |
| end water | end world | 末地 |
| reporting never parted | falling nether portal | 下界传送门 |
| never portal / never puddle / never probably / never bothered | nether portal | 下界传送门 |
| narrow products | nether portals | 下界传送门 |
| water in another | water in the nether | 下界水 |
| water in the ladder | water in the nether | 下界水 |
| water locked stairs / water lock blocks | waterlogged stairs / waterlogged blocks | 含水方块 |
| creating weapon dogs | creating water buckets | 水桶 |
| a stand of sand with dragon axe | a strand of sand with a dragon egg | 沙线+龙蛋 |
| the word hearing into a box eight core option | the world border ... coordinate option | 世界边界坐标选项 |
| corner to win generator | corner world generator | 世界边界角落 |
| the trapped chest two to get | the trapped chest trick to get | 陷阱箱技巧 |
| unholy hopper / unlocked hopper | unlucky hopper | 倒霉漏斗（社区梗） |
| sugar box | shulker box | 潜影盒 |
| add bottles | shulker boxes | 潜影盒 |
| box 36 | Block 36 | 移动方块 |
| improvement hits | in piston heads | 活塞头 |
| eight plus block 36 | a piston block 36 | 活塞 |
| one dog setup | falling block setup | 落沙方案 |
| following form | falling portal frame | 落沙传送门框架 |
| good out of stone bricks | grid out of stone bricks | 石砖网格 |
| a shocker of half blocks | a shulker of half blocks | 潜影盒 |
| hole in the dirt block | hoe on the dirt block | 锄 |
| server to us | server tour | 服务器游览 |
| require a little bit | record a little bit | 录制 |
| moyan fix that book | Mojang fix that bug | Mojang 修 bug |
| liquid pocket | lava pocket | 岩浆池 |
| the liquid rng | the lava RNG | 岩浆随机数 |
| fall off the door | fall off the drone | 无人机 |
| pingu freedom of flying machine | Pingu ... flying machine | Pingu, 人名, SciCraft 成员  |
| nice pack | nice, back | c1101 |
| falling flag | falling flag | c1235 语境（游戏规则标记） |
| two no two names | 2No2Name | 人名，SciCraft 成员|


