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

