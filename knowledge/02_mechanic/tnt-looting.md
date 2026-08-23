---
term: TNT looting
aliases: [TNT掠夺, looting TNT, 玩家点燃的TNT击杀, player-lit TNT kill]
category: mechanical
source: Chronos SMP - Autocrafting Creeper Storage（QSDpdXT9SPs）+ 用户人工补充（2026-08-23）
version: [通用]
status: 已确认
---

# TNT Looting（TNT 掠夺）

## 要点

- **机制定义**：只有被**玩家点燃**的 TNT 炸死的生物才计入"玩家击杀"，才能通过手持「抢夺」附魔武器增产（如苦力怕火药）。
- **关键约束**：TNT 复制技术（TNT duper）目前无法制造"由玩家点燃"的 TNT——复制产生的 TNT 不算玩家点燃。因此想用 TNT 掠夺，**必须由玩家手动放置 TNT**（通常再用玩家射出的箭点燃）。
- **应用场景**：弱加载掠夺苦力怕农场——苦力怕生成在视距外的弱加载区块，用 TNT 击杀可以正常吃「抢夺」，产出极高（如 350 万火药/时）。
- **副作用**：因 TNT 需手动放置，农场下界侧始终需要一名玩家在场操作。

## 翻译注意事项

- 标准译名：TNT 掠夺（`.cache/glossary/mob_farm.csv` L2 词条 `TNT Looting`→TNT掠夺；looting=抢夺，官方译名）。
- 语境区分：`looting`（附魔「抢夺」）与「掠夺」在农场语境指同一机制；`non-looting`=非抢夺模式。
- "玩家点燃的 TNT"（player-lit TNT）是本机制的成立条件，翻译时需与"玩家放置的 TNT"（放置≠点燃）区分。

## 备注

- 来源：Chronos SMP - Autocrafting Creeper Storage（QSDpdXT9SPs）c16-17（弱加载掠夺农场语境）；玩家点燃判定、TNT 复制限制为 2026-08-23 用户人工补充。
- 玩家长按放置 TNT 约 4 游戏刻/块 ≈ 1.8 万 TNT/时（自给计算参考）。
- 关联：lazy looting creeper farm（弱加载掠夺苦力怕农场）、抢夺附魔、TNT duper、空置域
