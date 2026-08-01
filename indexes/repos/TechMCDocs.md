# TechMCDocs 内容索引

> 生成时间：2026-08-02
> 上游 commit：40760453e4a58b104814e1b6e3ab4b205742cb83（2026-06-08）
> 仓库：https://github.com/TechMCDocs/pages
> 在线浏览：https://techmcdocs.github.io/（站名 Technical Minecraft Wiki，简称 TechMCDocs/TMC Docs）

Technical Minecraft Wiki 的页面源仓库，主题覆盖方块、游戏机制、游戏刻、实体、漏洞利用等，是红石技术视频翻译的高价值参考源。

## Blocks（方块）

- **Blocks/MovingBlock36.md** — 移动中的方块（B36/36号方块）机制：活塞移动路径上的方块实体，不导电、不可见但有 hitbox；hitbox 可偏移（tile entity 不被处理时留在原位）；1.17+ 不再能制造 tile-entity-less B36 [1.13-1.16]
  - 关键词：B36, 36号方块, 移动中的方块, Moving Piston, hitbox, tile entity, 世界边界
- **Blocks/Piston.md** — 活塞机制详解 [通用]
  - 关键词：活塞, 推动, 拉回, 黏性活塞, 移动方块

## BugsAndExploits（漏洞/特性）

- **BugsAndExploits/UpdateSuppression.md** — 更新抑制（Update Suppression）：利用栈溢出暂停更新链；1.19 更新系统重写后改为 Update Skipping（更新跳过），可达 100 万上限；副作用含 Portal Slicing、Soulbound chests、Item shadowing [1.13-1.21]
  - 关键词：更新抑制, 更新跳过, 栈溢出, Portal Slicing, 灵魂绑定箱子, 物品影子化
- **BugsAndExploits/LightSupression.md** — 光抑制（Light Suppression）：延迟光照更新并停止服务端以删除光照更新 [通用]
  - 关键词：光抑制, 光照更新, 服务端
- **BugsAndExploits/TntDuping.md** — TNT 复制机制 [通用]
  - 关键词：TNT复制, 爆炸, 移动方块
- **BugsAndExploits/ZeroTickFarms.md** — 零刻农场（Zero-Tick Farming）原理 [1.12]
  - 关键词：零刻, 农场, 甘蔗, 仙人掌, 快速生长

## Entities（实体）

- **Entities/EntityTransport.md** — 实体运输机制：实体速度/摩擦、活塞推动（0.51 块/gt 上限）、矿车吸轨、多种传送带示例（10bps 活塞带、活塞螺栓、懒实体发射器、TNT 炮） [通用]
  - 关键词：实体运输, 实体速度, 活塞传送带, 矿车, TNT炮, bps

## GameMechanics（游戏机制）

- **GameMechanics/WorldBorder.md** — 世界边界（World Border）详解：与 World Boundary（30M 不可见墙）区分；实体碰撞、出界方法（末影珍珠/紫颂果/睡觉等）、出界放置方块三法（脚手架/床/贴块放置/黏性活塞头）、B36 三法、方块破坏进度保存、MC-54587 等 bug 号 [1.16.4]
  - 关键词：世界边界, 世界边界外, B36, 方块放置, 实体碰撞, 末影珍珠, MC-54587
- **GameMechanics/BlockUpdates.md** — 方块更新机制 [通用]
  - 关键词：方块更新, 更新顺序, 更新传播
- **GameMechanics/ChunkLoading.md** — 区块加载机制：1.14+ 实体加载仅限玩家/传送门/出生点/末影龙；border loaded 区块无法提升为实体刻 [1.14+]
  - 关键词：区块加载, 实体刻, 懒加载, 出生点区块, 下界传送门加载
- **GameMechanics/ComparatorSignalStrength.md** — 红石比较器信号强度机制 [通用]
  - 关键词：比较器, 信号强度, 容器, 物品展示框
- **GameMechanics/QuasiConnectivity.md** — 准连接（QC）：活塞/投掷器/发射器在其上方一格位置被充能时也会被激活 [通用]
  - 关键词：准连接, QC, 活塞, 投掷器, 发射器
- **GameMechanics/RailBudding.md** — 铁轨芽（Rail Budding）：充能铁轨的类 BUD 特性 [通用]
  - 关键词：铁轨芽, 充能铁轨, 探测铁轨, BUD
- **GameMechanics/MobSpawning.md** — 生物生成机制 [通用]
  - 关键词：生物生成, 刷怪, 刷怪条件
- **GameMechanics/MobCap.md** — 生物上限（Mob Cap）机制 [通用]
  - 关键词：生物上限, 刷怪塔, 容量
- **GameMechanics/IronGolemSpawningMechanics.md** — 铁傀儡生成机制 [通用]
  - 关键词：铁傀儡, 村庄, 生成, 刷铁机
- **GameMechanics/PotionEffects.md** — 药水效果机制 [通用]
  - 关键词：药水, 状态效果, 信标
- **GameMechanics/Brewing.md** — 酿造机制 [通用]
  - 关键词：酿造, 药水, 酿造台
- **GameMechanics/HugeFungi.md** — 巨型菌类机制 [1.16+]
  - 关键词：巨型菌, 菌柄, 菌盖, 骨粉

## GameTick（游戏刻）

- **GameTick/TileTicks.md** — 计划刻（Tile Tick）机制：调度/执行、方块刻与流体刻、65536 上限、玩家输入时序 [通用]
  - 关键词：计划刻, 方块刻, 流体刻, 调度, 65536
- **GameTick/MobTick.md** — 生物刻机制 [通用]
  - 关键词：生物刻, AI, 移动
- **GameTick/Weather.md** — 天气机制 [通用]
  - 关键词：天气, 下雨, 雷暴, 随机刻

## Other（其他）

- **Other/Perimeters.md** — 刷怪区（Perimeter）：清空地形防止刷怪/减卡，常见 272 块；首个见于 ZipKrowd 服务器 [通用]
  - 关键词：刷怪区, 世界吞噬者, 刷怪上限, 减卡, ZipKrowd
- **Other/CarpetMod.md** — Carpet 模组说明 [通用]
  - 关键词：Carpet, 模组, 规则
- **Other/OlderVersions.md** — 旧版本相关说明 [旧]
  - 关键词：旧版本, 历史机制

## TechSubjects（技术主题）

- **TechSubjects/StorageTechMechanicsChanges.md** — 存储科技版本历史：1.11-1.20+ 各版本影响存储的机制变化（潜影盒/侦测器/铜块/可推动方块等） [1.11+]
  - 关键词：存储技术, 版本历史, 潜影盒, 侦测器, 机制变化

## Resources（资源）

- **Resources/StyleGuide.md** — 仓库写作风格指南（编辑贡献用，非翻译参考） [通用]
  - 关键词：风格指南, 贡献, 写作规范

## 顶层导航

- `Blocks.md` / `BugsAndExploits.md` / `Entities.md` / `GameMechanics.md` / `GameTick.md` / `Other.md` / `Resources.md` / `TechSubjects.md` — 各主题的文章导航页（可当主题目录用）
  - 关键词：导航, 目录, 主题索引
