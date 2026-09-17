---
term: pot
aliases: [decorated pot, flower pot, clay pot, 陶罐, 饰纹陶罐, 花盆]
category: storage
source: Minecraft Wiki 花盆 / 饰纹陶罐 / 漏斗 页 + 用户裁定（2026-09-13，ZXGpmaIcMMo PRR 5）+ wiki 查证补齐判据（2026-09-17）
version: [通用]
status: 已确认
license: CC BY-NC-SA
---

# Pot（花盆 / 陶罐）

## 要点

英文 `pot` 单独出现时可指两个完全不同的方块，**是否容器**是区分关键：

| 方块 | 官方英文 | 官方中文 | 容器 | 方块实体 | 碰撞箱高度 |
|------|----------|----------|------|----------|------------|
| 花盆 | Flower Pot | 花盆 | ✗ | JE 非方块实体（盆内植物由方块状态 `potted_*` 记录；仅 BE 用方块实体值） | 3/8 格 |
| 饰纹陶罐 | Decorated Pot | 饰纹陶罐 | ✓ 1 格（至多 1 组同类物品） | ✓ | 满格高，但罐口在碰撞箱外、截面非满 |

- **饰纹陶罐**：投掷器 / 漏斗 / 合成器可存入，漏斗与漏斗矿车可取出（玩家不能直接取出）；红石比较器可读取其填充度并输出信号
- **花盆**：无任何容器功能，只能手持植物交互放入 / 取出；与漏斗、投掷器、比较器均无交互
- 二者均**不可放置红石线**（上表面支撑形状不完整）；花盆会被水流、熔岩流与活塞破坏
- 饰纹陶罐历史用名 **Clay Pot**（Minecraft Live 2020 展示名）；无 `terracotta pot` 之类官方别名

## 翻译注意事项

**判定顺序**：先看是否属「容器 / 存储 / 红石」语境，再排除植物、装饰信号。

| 语境信号 | 所指 | 译名 |
|----------|------|------|
| 与 dropper / composter / hopper / 潜影盒等**容器**并列，讲装物品、容量、漏斗抽取、比较器读取 | decorated pot | **陶罐**（正式作「饰纹陶罐」） |
| 与植物、盆栽、装饰并列，讲种植、放置植物、装饰建筑 | flower pot | **花盆** |

- 原文已写全名（`flower pot` / `decorated pot`）→ 直接对应「花盆」/「饰纹陶罐」，无需推断
- **勿见 pot 即译「花盆」**——中文「花盆」的语义引力极强，容器语境极易译错

## 备注

### 实例（ZXGpmaIcMMo PRR 5）

原文 00:11:42（c349）：`you will often see people covering their exposed hoppers with things like droppers or composters or even pots`

- 三个并列项 dropper / composter / pot **均为容器**（这正是作者列举它们的理由，见下节机制），故此处 pot = 饰纹陶罐，非花盆（2026-09-13 用户裁定）

### 附带机制：漏斗上方放容器 / 完整方块可减少卡顿

wiki「漏斗」页「开启的漏斗」小节：漏斗捕捉凹槽内及上方 1×1×1 范围内的 1 个物品实体；**满足下列条件时漏斗不再尝试检查与捕捉物品实体**（可用于减少卡顿）：

| 版本 | 不检查的条件 |
|------|--------------|
| Java 版 | 上方是**容器**（无例外）**或**碰撞箱完整的方块（蜂巢、蜂箱除外） |
| 基岩版 | 上方是**容器**（饰纹陶罐除外） |

- 另有补充：Java 版下凹槽内的物品实体仍会主动进入漏斗
- 因此「用方块盖住漏斗以省算力」在 Java 版下**容器与完整方块皆可**——作者列举的 dropper / composter / pot 三者都是容器
- 与本卡的关系：正因陶罐是容器（花盆不是），它才能承担这个用途——可作判定语境的旁证

### 来源与关联

- 来源：`.cache/wiki/花盆.md`、`.cache/wiki/饰纹陶罐.md`（2026-09-17 新抓取）、`.cache/wiki/漏斗.md`、`.cache/wiki/判定箱.md`、`.cache/wiki/堆肥桶.md`
- 关联：`.github/experience/trap_words.md`（storage 分类）、`.cache/mojang/blocks.csv`（官方译名）、`knowledge/01_terminology/storage.csv`
- 查证记录：`_work/wiki_resolve.md`（第 1 批）、`_work/wiki_resolve_2.md`（第 2 批，纠正版别标注读法）
