# 数据源覆盖范围日志

> 每次翻译任务后由 Agent 在阶段三追加记录。
> 逐步建立"哪个数据源擅长哪类知识"的经验地图。
>
> 永久指南见 `SOURCE_COVERAGE.md`。

## Solving Minecraft's Storage Problem — 2026-07-31 | 领域：存储

| 数据源 | 查询次数 | 命中 | 命中案例 | 缺失案例 |
|--------|----------|------|----------|----------|
| knowledge/ | 2 | 0 | — | 铜傀儡、无粉分类器、烧车式分类器等均为新术语，需本次登记 |
| .cache/mojang/redstone.csv | 1（全量加载） | ~8 | Comparator→红石比较器、Hopper→漏斗、Chest→箱子、Piston→活塞、Barrel→木桶 | Copper Golem（快照新特性未收录）；铜箱子由 Waxed Copper Chest 推断 |
| .cache/glossary/storage.csv | 1（全量加载） | ~9 | Item Sorter→物品分类、MIS→多物品分类、Hopper Speed→漏斗速、Hopper-Locked→锁漏斗、Unstackable→不可堆叠、Item Overflow→物品溢出、Unloader→拆包机、Main Storage→全物品仓库、Cart Yeet→烧车 | Toggle State、Vertical Integration、Tick Warping 等非标准术语 |
| .cache/glossary/general.csv | 1（全量加载） | ~6 | Dustless→无粉、Tileable→可堆叠、Signal Strength→信号强度、Slice→单片、Game Tick→游戏刻、MSPT | — |
| .cache/wiki/ | 0 | 0 | — | — |
| MCP Wiki（本次新抓） | 2 | 1 | Copper Golem→铜傀儡（生成/行为机制） | Tutorials/Item sorter 页面不存在 |
| _repos/（索引定位） | 0 | 0 | — | 本视频术语已由术语表+Wiki覆盖，未触发 |

### 发现
- ✅ 本次在 **MCP Wiki** 中新发现可覆盖的知识类型：快照新生物/方块（铜傀儡）的中文标准名及其行为机制描述。
- ✅ 本次在 **.cache/glossary/storage.csv** 确认：cart-eating 在存储科技中对应 Cart Yeet（烧车），用于纠正 ASR 误识别。
- ❌ 本次 **knowledge/** 未能覆盖任何本视频术语（目录基本为空），22 条新术语已登记到 `knowledge/01_terminology/_uncategorized.csv`。
- ❌ **Mojang 术语表**未覆盖快照新增特性（铜傀儡、铜箱子），需以 Wiki 为兜底。

## Solving Minecraft's Storage Problem — 2026-08-01（审核循环修订） | 领域：存储

### 审核循环（阶段二½）修正记录

| 类别 | 原译 | 修正为 | 依据 |
|------|------|--------|------|
| main storage | 主存储 | 全物品仓库 | TechMC Glossary：MS=全物品/全物品分类仓库 |
| Hermits | 村民 | Hermitcraft 成员（隐士们） | 用户审计：指 Hermitcraft 服务器成员 |
| filter（物品分类语境 6 处） | 过滤器 | 分类器 | 术语表既有标准（脉冲式/无粉物品分类器） |
| the bow and sorter [待审核] | 保留原文 | 普通分类器（按语境猜测） | 用户确认后按上下文取意译 |
| 段 59-60 重复 | "36 个分区"×2 | 段 60 去重为"这么选是刻意的" | 用户审核 |

### 数据源效果补充

| 数据源 | 查询次数 | 命中 | 命中案例 | 缺失案例 |
|--------|----------|------|----------|----------|
| _repos/techmc-glossary | 1 | 1 | Main Storage(MS)→全物品/全物品分类仓库（审核中修正主存储误译） | — |

### 发现
- ✅ **TechMC Glossary** 在审核阶段命中关键映射：`MS→全物品/全物品分类仓库`，纠正了初译"主存储"（直译陷阱：storage tech 中 main storage 是专有名词，非字面"主存储"）。
- ✅ **术语一致性原则**成功拦截 filter→分类器：初译 6 处"过滤器"与术语表"脉冲式物品分类器/无粉物品分类器"不一致，审核中统一。
- ✅ 审核循环新增登记 2 条项目术语（Main Storage→全物品仓库、Hermit→隐士），`_uncategorized.csv` 现共 9 条。

## The Minecraft World Border - Technical Analysis — 2026-08-01 | 领域：世界边界/活塞机制

| 数据源 | 查询次数 | 命中 | 命中案例 | 缺失案例 |
|--------|----------|------|----------|----------|
| knowledge/01_terminology/ | 1 | 0（读旧） | — | 本视频 3 条核心术语此前未收录（B36、方块破坏进度保存、服务端碰撞箱），本次登记 |
| .cache/glossary/general.csv | 1（全量加载） | 2 | B36→36号方块、Moving Piston→移动中的方块 | — |
| .cache/glossary/mechanical.csv | 1（全量加载） | ~8 | Piston→活塞、Sticky Piston→黏性活塞、Observer→侦测器、Dropper→投掷器、Dispenser→发射器 | — |
| .cache/mojang/blocks.csv | 1（全量加载） | 8 | Ancient Debris→远古残骸、Cobweb→蜘蛛网、Scaffolding→脚手架、Moving Piston→移动的活塞 | — |
| .cache/mojang/entities.csv | 1（全量加载） | 5 | Wither Skull→凋灵之首、Ender Dragon→末影龙、Thrown Ender Pearl→掷出的末影珍珠、Snowball→雪球、Trident→三叉戟 | — |
| .cache/mojang/items.csv | 1（全量加载） | 1 | Chorus Fruit→紫颂果 | — |
| .cache/wiki/ | 0 | 0 | — | — |
| MCP Wiki | 0 | 0 | — | TechMCDocs 文章已覆盖全部机制细节，未触发兜底 |
| _repos/TechMCDocs/pages | 2 | 2 | GameMechanics/WorldBorder.md（实体碰撞/出界方法/方块放置/B36 三法/方块破坏进度保存/MC-54587 等 bug 号）、Blocks/MovingBlock36.md（B36 不导电、不可见但有 hitbox、tile entity 不处理时 hitbox 原位） | — |

### 发现
- ✅ **Technical Minecraft Wiki 文章**（_repos 子仓库）是本视频技术知识的主要来源：WorldBorder.md 覆盖全部 7 个章节机制细节，并给出 MC-54587/MC-54119/MC-220191/MC-223190 四个 bug 号；MovingBlock36.md 补充 B36 行为。
- ✅ **world border 译名**取 Mojang 官方 zh_cn.json `commands.worldborder.*` 的「世界边界」；TechMCDocs 区分 World Border（可见屏障）与 World Boundary（30M 不可见墙），本视频仅涉及前者。
- ✅ **technical wiki 为专有名词**：指 https://techmcdocs.github.io/（站名 Technical Minecraft Wiki），不译为"技术 Wiki"，直接保留英文。
- ✅ 本次登记 3 条新术语（B36→36号方块/移动中的方块、block breaking progression saving→方块破坏进度保存、server-sided hitbox→服务端碰撞箱），`_uncategorized.csv` 现共 7 条；ASR 映射 8 处已登记 `.github/experience/asr_fixes.md`。
- ❌ MCP Wiki 本次未使用——知识已由 Technical Minecraft Wiki 原文 + Mojang 官方术语表覆盖。

## We Caged 52 Withers to Make This Farm — 2026-08-03 | 领域：凋灵笼/黑曜石农场（末地机制）

| 数据源 | 查询次数 | 命中 | 命中案例 | 缺失案例 |
|--------|----------|------|----------|----------|
| knowledge/01_terminology/ | 2（proper_nouns.csv + storage.csv） | 3 | cubicmetre→cubicmetre、Wavetech→Wavetech（proper_nouns.csv）；Main Storage→全物品仓库（storage.csv） | — |
| .cache/glossary/ | 1（refresh_cache.py 统一刷新） | 0 | — | 凋灵笼、切片下界传送门、Boss栏等本视频新术语均未收录（本次登记） |
| .cache/mojang/ | 1（按类加载） | ~15 | Obsidian→黑曜石、Wither Skeleton Skull→凋灵骷髅头颅、Ice→冰、End Stone→末地石、Slab→台阶（blocks.csv）；End Crystal→末地水晶、Ghast→恶魂、Shulker Box→潜影盒、Boat/Minecart→船和矿车、Ender Dragon→末影龙（entities.csv）；Ghast Tear→恶魂之泪、Lava Bucket→熔岩桶、Spyglass→望远镜（items.csv）；Dispenser→发射器（redstone.csv）；End Portal/Ender Chest→末地传送门/末影箱 | — |
| .cache/wiki/ | 0 | 0 | — | 本次 8 个相关页面全部为新抓，预存缓存未命中 |
| MCP Wiki（本次新抓） | 8 | 8 | 黑曜石柱（end pillar/东侧黑曜石柱）、黑曜石农场（教程）（end pillar obsidian farm）、末影龙（ritual→末影龙复活仪式）、凋灵（block breaking attack→破坏方块攻击）、凋灵笼（教程）（suffocation damage→窒息伤害、blue skulls→蓝色凋灵之首、wither cage→凋灵笼）、凋灵骷髅头颅（wither skeleton farm→凋灵骷髅农场）、末地水晶、Boss栏 | — |
| _repos/（索引定位） | 1 | 1 | TechMCDocs/BugsAndExploits/UpdateSuppression.md（sliced nether portals→切片下界传送门） | — |

### 发现
- ✅ 本次在 **MCP Wiki** 中确认：凋灵/凋灵笼机制术语（窒息伤害、蓝色凋灵之首、破坏方块攻击、凋灵笼）来自中文 Wiki 教程页，是「凋灵笼」主题术语的可靠来源；黑曜石柱（End Spike）译名取自中文 Wiki 页面，纠正 ASR 误识别 obscene farm。
- ✅ 本次在 **_repos/TechMCDocs** 确认：切片下界传送门（sliced nether portal）为 TechMC 社区专有术语，源自 Update Suppression 相关技术文章，非 Wiki 页面收录。
- ✅ **知识三级路由有效**：proper_nouns/storage 术语表直接覆盖人名与全物品仓库；Mojang 官方表覆盖方块/物品/实体；Wiki 补机制类术语；TechMCDocs 补社区专有技术。
- ✅ 本次登记 6 条新术语（end pillar→黑曜石柱、wither cage→凋灵笼、blue wither skull→蓝色凋灵之首、sliced nether portal→切片下界传送门、dragon respawn ritual→末影龙复活仪式、boss bar→Boss栏），`_uncategorized.csv` 现共 13 条；ASR 映射 22 处已登记 `.github/experience/asr_fixes.md`。
- ❌ **上下文推断**承担了若干术语（Y0 platform、fortune pick、temporary bulk storage、torch farm、skull bucket button 口诀、portal tech），无直接数据源；`results of the year`、`brazil`、`even hon toons` 等 ASR 存疑项保留原词待用户审核，未注册。

## SciCraft Getting Command Blocks In Survival — 2026-08-04 | 领域：1.12.2 黑科技/落沙/命令方块

| 数据源 | 查询次数 | 命中 | 命中案例 | 缺失案例 |
|--------|----------|------|----------|----------|
| knowledge/01_terminology/ | 1（proper_nouns.csv + storage.csv） | 1 | Main Storage→全物品仓库（storage.csv）；人名库确认各人名保持原名 | 本视频核心黑科技术语（落沙、字撕裂、安全状态等）此前未收录，本次登记 |
| .cache/glossary/ | 1（refresh_cache.py 统一刷新 + 按类加载） | ~8 | Chunk Population→区块装饰、Word Tear→字撕裂、Blockstate palettes→方块状态调色板（1.12.2_magic.csv）；Cobblestone Farm→刷石机、Sand Duping→刷沙/复制（contraptions.csv）；Game Tick→游戏刻（general.csv）；Instant→瞬时 | — |
| .cache/mojang/ | 1（按类加载） | ~15 | End Portal Frame→末地传送门框架、Monster Spawner→刷怪笼、End Gateway→末地折跃门、Anvil→铁砧、Observer→侦测器、Barrier→屏障、Structure Void→结构空位、Grass Path→土径、Farmland→耕地（blocks.csv）；Enderman→末影人（entities.csv） | 1.12 独有黑科技概念（falling block 非法形态、字撕裂、safe state）非 Mojang 官方表收录 |
| .cache/wiki/ | 0 | 0 | — | 预存缓存无 1.12 黑科技页面（活塞/草方块/黏液块等均为通用机制），未命中 |
| MCP Wiki（本次新抓） | 1 | 1 | 下界（nether ceiling→下界天花板；下界↔主世界 8:1 坐标映射→乘八漏洞） | 要塞页未抓（stronghold 由用户确认 + 02_terms 既有登记） |
| _repos/（索引定位） | 0 | 0 | — | 本视频术语已由术语表 + Wiki 覆盖；1.12 黑科技类文章（字撕裂等）在 TechMCDocs 中未见直接页面 |

### 发现
- ✅ 本次 **1.12.2_magic.csv**（TechMC Glossary 拆分缓存）是黑科技术语的主来源：字撕裂（Word Tear）、区块装饰（Chunk Population）、方块状态调色板（Blockstate palettes）均命中，证明「.cache/glossary/ 按主题拆分」策略对 1.12 黑科技领域有效。
- ✅ 本次 **MCP Wiki「下界」页**一次抓取同时解决两项：nether ceiling（下界天花板）+ 8:1 坐标比（乘八漏洞依据），Wiki 适合补「机制性」术语。
- ✅ **用户确认**承担大量视频内部 jargon：safe state（安全状态）、global flag（全局标志）、falling flag（落沙标志）、spawn tower（出生点塔）、half block（半砖）、fortress 口误判定——这类 SciCraft 服务器内部黑话无公开数据源，只能靠上下文 + 用户确认。
- ✅ **ASR 映射 114 条**已登记 `.github/experience/asr_fixes.md`（本视频段落），为历次最多（人名/落沙/命令方块主题误识别密集）。
- ✅ 本次登记 12 条新术语（nether ceiling→下界天花板、lightning farm→闪电农场、safe state→安全状态、global flag→全局标志、falling flag→落沙标志、spawn tower→出生点塔、half block→半砖、multiply by eight glitch→乘八漏洞、illegal blocks→非法方块、stronghold→要塞、server tour→服务器游览、falling nether portal→落沙下界传送门），`_uncategorized.csv` 现共 18 条。
- ❌ **上下文推断**承担若干术语（block state corruption→方块状态损坏、registry palette→方块状态调色板、async thread→异步线程、multi-threading→多线程、initial generation→初始生成、command block bits→命令方块数据位），无直接数据源。
- ❌ **c790 conversion contraption** 疑 ASR 误听，按「broken contraption for creating player heads」语境处理，未注册。

