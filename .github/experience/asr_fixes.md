# ASR 误识别校正表（跨视频通用）

> YouTube 自动字幕（ASR）经常误识别技术术语和人名。本文档沉淀**跨视频可复用**的误识别映射，
> 供翻译时快速解码"看起来不像词"的原文。
> 维护：Agent 每次识破新误识别后追加（只追加，不删改既有条目）；只有**跨视频通用**项入本表，
>       视频专属项（人名/服务器/一次性语境）归档到 `_work/<视频名>/asr_fixes.md`。
> 使用：阶段〇扫描字幕时，若某词在词典/术语表中找不到，先查本表；未命中再查 `_work/<视频名>/asr_fixes.md`。

## 使用规则

1. 命中本表 → 用正确词去查术语表/译名，原文行保留 ASR 原文（双语对照时可在中文侧注明正确词）
2. 未命中 → 查 `_work/<当前视频名>/asr_fixes.md`（本视频已识别映射）
3. 仍未命中 → 判断是否可能是 ASR 错误：
   - 词形近似已知 Minecraft 实体/人名/模组名（如 scarpet ≈ scraped）
   - 上下文强烈暗示某机制（如存储视频里出现"烧车"语境）
   - 是 → 按分层登记（登记规则见 `term-registration`「ASR 映射登记」）：
     - **跨视频通用**（音近规律/高频词变体）: 进本表，按正确词聚合
     - **视频专属**（人名/服务器/一次性语境）: 进 `_work/<视频名>/asr_fixes.md`
   - 否 → 正常术语流程
4. 用户确认后，将 `[ASR 推测]` 的条目移入"已验证映射"表

## 格式约定

```
正确词: 变体1 / 变体2 / ...（领域/上下文说明）
```

同一条多个变体合并为一行（`/` 分隔），**按正确词聚合**（查询时"看到怪词 → 找正确词"）。

> **时间戳不入库**：字幕时间戳是逐视频的反馈定位信息，仅在向用户反馈（`translate-redstone` §1.3 / 阶段二½）时附带，**不写入本表**——本表跨视频累积，不绑定具体视频。
> **规模上限 ~100 条**：超限触发整理（见 `maintain-knowledge`「经验文件维护」），把低价值/视频专属项移走归档。

## 已验证映射（跨视频通用，按正确词聚合）

| 正确词 | 变体（ASR） | 说明 |
|--------|------------|------|
| falling block(s) | following / volume blocks / volume docs / funding blocks / phoning blocks / form block / fine suns / following sand | 落沙系列，最高频误听 |
| falling sand | fine suns / following sand | 落沙 |
| falling block setup | one dog setup | 落沙方案 |
| falling portal frame | following form | 落沙传送门框架 |
| shulker box | shocker box / shock boxes / shelter boxes / sugar box / add bottles / a shocker of half blocks | 潜影盒系列变体 |
| beacon(s) | beaten / beating / beaten tower / four peaking blocks / the buildings / without any weakness in / without any beatings / five thousand beatens | 信标系列 |
| nether portal | never portal / never puddle / never probably / never bothered / narrow products / reporting never parted | 下界传送门 |
| end portal | end port / airport / end water | 末地传送门 |
| end portal frame | endpoint frame / input frame / airport frame / n portal frames / place and portal frames / falling end for the frame | 末地传送门框架 |
| world border | wharf border / word butter / corner to win generator / the word hearing into a box eight core option | 世界边界 |
| word tear | word staring thing / word hearing into a box eight core option | 字撕裂（1.12.2 黑科技） |
| Block 36 | box 36 | 移动方块 |
| sorter | sorder / sortter / sortters | 分类器 |
| multi-item sorter | multi-to solder / are multi-item | 多物品分类器 |
| dustless | DOSless | 无粉 |
| MSPT | MPT / MSP T / msbt / msvt | 毫秒每刻 |
| hopper counters | copper counters | 漏斗计数器 |
| copper golems | cup golems | 铜傀儡（快照新生物） |
| scarpet | scraped / scarpad | Carpet 模组脚本语言 |
| cart yeeting | part eating | 烧车（存储科技 Cart Yeet 技术） |
| latest snapshot | layer snapshot | 最新快照 |
| caustic | costic | 难缠的（形容物品集） |
| redstone | resto | 红石（装置） |
| Louvain | levane | 鲁汶（图聚类算法） |
| update suppressor | object suppressor | 更新抑制器（即时红石/更新抑制语境） |
| ideal | idol | — |
| higher-end | higherend | — |
| sort bee | sort be | 蜂巢（bee nests） |
| item sorter breaks | item sort of breaks | ASR 漏词 |
| three-wide tileable | free wide tilable | 三宽可堆叠 |
| wither skulls | river skulls | 凋灵之首 |
| /tp | slash tv | 命令（/teleport） |
| ghast | gas | 恶魂 |
| end pillar | n pillar | 末地黑曜石柱 |
| in creative | hearing / in creative | ASR 多词/漏词 |
| farm in creative | farming creative | ASR 漏介词 |
| convinced | comforted | 确信（"fully convinced"） |
| obsidian farm | obscene farm | 黑曜石农场 |
| ender dragon | enemy dragon / gender dragon | 末影龙 |
| end stone farm | start farm | 末地石农场 |
| we built | we bought | 口语（"built an obsidian farm"） |
| scared you'll mess my stuff up | scared you my stuff up | ASR 漏词 |
| kill that wither | feel that wither | 击杀凋灵 |
| carts | cars / cards | 矿车（minecart） |
| shulker | sugar / should / shocker / shoulder / shelter / choker / schulker / shoulders | 潜影贝（本视频最高频误听） |
| aggro | agreeing / agree on / I grow / agar / Egger engine | 仇恨（潜影贝农场/红石语境） |
| trash mob | trash Muppets / trash weapons / trash puppets | 垃圾怪（不参与复制的边缘潜影贝） |
| minecart | mine guards / mine car / Minecraft / my car / cars | 矿车 |
| shulker bullet | Bulls / bolts / Ebola | 潜影弹 |
| peeking | peaking | 开壳（潜影贝） |
| game tick | game decks / game takes / takes | 游戏刻 |
| comparator | comparative | 比较器 |
| schematic | scam | 投影/原理图 |
| scaffolding-based | scaffolding by | 脚手架式（农场） |
| tileability | title ability | 可堆叠性 |
| redstone coder | red coder | 红石编码器 |
| placement chute | replacement shoes / replacement shoe | 放置滑道 |
| loader | TNT leader / lazy leader | 打包机（storage 语境） |
| kill area | killaria | 击杀区 |
| lag | light | 卡顿 |
| Litematica | lymatica | 投影模组 |
| Tweakeroo | twicroot | 辅助模组 |
| MiniHUD | midi HUD | 信息显示模组 |
| farm | phone | 农场 |
| ritual | rich / original | 仪式 |
| spyglass | spy glass | 望远镜 |
| netherrack | dandarak | 下界岩 |
| wither | widow / weapon | 凋灵 |
| overworld | overwatch | 主世界 |
| portal cooldown | nk21 | 传送门冷却 |
| piston clock | piston club | 活塞时钟 |
| sand | sans / sand | 沙子 |
| the end dimension | the n dimension | 末地维度 |
| mycelium | misalignment | 菌丝 |
| eye of ender | head bottle | 末影之眼 |
| dragon egg | dragon axe / dragon x | 龙蛋 |
| wither skeletons | weapon dogs | 凋灵骷髅 |
| update suppressor | pressure / update to pressure / important extra update to pressure | 更新抑制器 |
| async chunk | ac chunk / 18 chunk | 异步区块（重载） |
| cluster chunk | cluster change / cluster shank / plus a chunk / few hundred plus / a few hundred plus the chance | 集群区块 |
| main thread | mainframe | 主线程 |
| threads | three frets / first running at once | 线程 |
| contraption | a contraction / the contract will be shot / where contraption whenever | 机器/装置 |
| water in the nether | water in another / water in the ladder | 下界水 |
| waterlogged stairs / blocks | water locked stairs / water lock blocks | 含水方块 |
| water buckets | creating weapon dogs | 水桶 |
| a strand of sand with a dragon egg | a stand of sand with dragon axe | 沙线+龙蛋 |
| the trapped chest trick | the trapped chest two to get | 陷阱箱技巧 |
| unlucky hopper | unholy hopper / unlocked hopper | 倒霉漏斗（社区梗） |
| piston heads | improvement hits | 活塞头 |
| piston block 36 | eight plus block 36 | 活塞 |
| grid out of stone bricks | good out of stone bricks | 石砖网格 |
| hoe | hole in the dirt block | 锄 |
| server tour | server to us | 服务器游览 |
| record a little bit | require a little bit | 录制 |
| Mojang fix that bug | moyan fix that book | Mojang 修 bug |
| lava pocket | liquid pocket | 岩浆池 |
| the lava RNG | the liquid rng | 岩浆随机数 |
| drone | fall off the door | 无人机 |
| flying machine | pingu freedom of flying machine | 飞行器 |
| palette of blocks | palace down there / palette of blogs | 方块调色板 |
| cubicmetre | cubic meter | 人名（频道名，存储技术） |
| my old mate | me old mate | 口语语法 |
| design in snapshot | design snapshot | ASR 漏介词 in |
| node | note / notes / endnote / i know / red nose / a no | 节点（末影龙寻路机制主题高发） |
| pathfind | path finds / pat find / path find | 寻路（末影龙寻路机制） |
| island | iceland | 岛（末地岛） |
| place blocks | play blocks | 放置方块 |
| y level | by level | Y 坐标层 |
| valid path | pallet path | 有效路径（语义+音近） |
| dirt | third | 泥土（音近） |
| blocks | logs | 方块（语义+音近，dirt blocks 语境） |
| cut it | carry | 剪辑用语（"我要切掉这段"） |
| social aggro | social I grow / social Agro / social like or | 群体仇恨（潜影贝复制机制的仇恨信号，aggro 变体 + social 前缀） |
| omega long pulse extender | an ilmango um | 欧米伽长脉冲延长器（ilmango 人名误听） |

<!-- 历史单视频专属映射（无法确认归属视频或已不在 _work 追踪）：不参与通用解码。
     清理遵循 AGENTS.md 核心原则 #6，提示用户手动归档到 _work/<视频名>/asr_fixes.md，不自动删。 -->

