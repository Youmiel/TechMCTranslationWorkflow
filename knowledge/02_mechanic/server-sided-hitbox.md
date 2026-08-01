---
term: server-sided hitbox
aliases: [服务端碰撞箱, server hitbox]
category: mechanical
source: The Minecraft World Border - Technical Analysis (FX) / TechMCDocs GameMechanics/WorldBorder
version: [通用]
status: 待审核
---

# Server-sided Hitbox（服务端碰撞箱）

## 要点
- 服务端维护的实体碰撞箱，与客户端（client）相对。
- 本视频关键机制（世界边界场景）：B36 被推出世界边界后，服务端碰撞箱仍留在边界内一侧，客户端因此出现渲染异常（glitch）。

## 翻译注意事项
- 标准译名：服务端碰撞箱（2026-08-01 用户确认直译），相对 client（客户端）。
- 语境中常与 client-sided（客户端）对举。

## 备注
- 来源：TechMCDocs 文章 `GameMechanics/WorldBorder`（FX 视频），2026-08-01 用户确认；词汇表登记见 `01_terminology/_uncategorized.csv`。
- 关联：B36、世界边界、方块破坏进度保存（MC-54587）
