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

