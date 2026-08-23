# 机制知识索引

> 生成时间：2026-08-23（新增 tnt-looting / hitbox-sorting 两张知识卡；box-crafter 内容 2026-08-13 泛化修订；B36 / server-sided hitbox 于 2026-08-01）
> 条目数已移除（见 `indexing-rules`：不写易漂移的精确计数，用范围/关键词描述）
> 对应目录：`knowledge/02_mechanic/`

## 知识卡

- **`tnt-looting.md`** — TNT 掠夺：只有玩家点燃的 TNT 击杀才算玩家击杀、才能吃「抢夺」增产；TNT 复制无法产生玩家点燃的 TNT，故需手动放置 + 箭点燃；弱加载掠夺苦力怕农场的击杀方式 [通用]
  - 关键词：TNT looting, TNT掠夺, 抢夺, 玩家点燃, TNT 复制, 苦力怕农场, 火药
  - 来源：Chronos SMP - Autocrafting Creeper Storage（QSDpdXT9SPs）+ 用户补充

- **`hitbox-sorting.md`** — 碰撞箱分选：存储系统的高阶布线方式，一条水道中利用不同大小的方块碰撞箱拦截物品、按尺寸归入不同槽位；物品实体碰撞箱一样大；烟花火箭按等级分选只过一条水道 [通用]
  - 关键词：hitbox sorting, 碰撞箱分选, 水道, 物品实体, 方块碰撞箱, 烟花火箭分选
  - 来源：Chronos SMP - Autocrafting Creeper Storage（QSDpdXT9SPs）+ 用户补充

- **`box-crafter.md`** — 潜影盒合成机（box crafter）：存储系统中自动合成空潜影盒的装置，可附带染色等功能，作为存储系统一部分自动补盒；装置名带 Ngt 前缀指运行周期 [1.21+]
  - 关键词：box crafter, 潜影盒合成机, 合成器, 染色, 自动补盒, 游戏刻周期, storage tech
  - 来源：Chronos SMP - Autocrafting Creeper Storage（QSDpdXT9SPs）

- **`B36.md`** — 36号方块（移动中的方块）：活塞移动路径上的移动中方块实体，不可见、不导电但有碰撞箱；世界边界是 1.17 中唯一能制造 B36 的途径 [通用]
  - 关键词：B36, 36号方块, 移动中的方块, Moving Piston, 移动中方块, 世界边界, 碰撞箱, 渲染异常
  - 来源：The Minecraft World Border - Technical Analysis（FX）、TechMCDocs Blocks/MovingBlock36

- **`server-sided-hitbox.md`** — 服务端碰撞箱：服务端维护的实体碰撞箱；B36 被推出世界边界后碰撞箱留在边界内、客户端渲染异常 [通用]
  - 关键词：hitbox, 碰撞箱, 服务端, 客户端, 世界边界, 渲染异常, B36
  - 来源：TechMCDocs GameMechanics/WorldBorder、The Minecraft World Border - Technical Analysis（FX）
