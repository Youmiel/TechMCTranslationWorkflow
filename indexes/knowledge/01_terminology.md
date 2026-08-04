# 第一类术语知识索引

> 生成时间：2026-08-04
> 时间戳 = **刷新判断依据**：仅在**非 `_uncategorized`** 内容实质变更时更新（`_uncategorized.csv` 词条变动不更新索引，见 `indexing-rules`「索引时间戳与更新策略」）
> 对应目录：`knowledge/01_terminology/`

## CSV 术语表

- **`_example.csv`** — 表头模板，所有术语 CSV 共享此结构 [通用]
  - 列：`term_en,short_form,definition,notes,term_zh,term_ja`
  - 关键词：模板, 表头, CSV, 规范

- **`_uncategorized.csv`** — 待分拣术语暂存区，Agent 自动登记新术语的唯一写入目标（未识别分类）[通用]
  - 说明：内容随每次翻译工作新增而变动，本索引不列出其词条、不随其变动更新（人工定期分拣到对应类别）
  - 关键词：待分拣, 未识别分类, 新术语, Agent写入

- **`common.csv`** — 通用基础术语（当前为空，仅表头）[通用]
  - 关键词：通用, 基础

- **`contraptions.csv`** — 装置/机制术语（玩家制造的装置类设施）[通用]
  - 内容：凋灵笼（wither cage）、闪电农场（lightning farm，1.12 黑科技）、铜傀儡分类器（Copper Golem Sorter，存储装置）
  - 关键词：凋灵笼, 闪电农场, 铜傀儡分类器, 装置, 黑科技, 存储
  - 来源：凋灵笼教程、6sPS4yqC72I 视频、cubicmetre 视频

- **`game_system.csv`** — 游戏机制/系统术语 [通用]
  - 内容：游戏刻阶段（WTU 世界时间更新 / AT 异步事件 / 随机刻；CT 区块刻、EU 实体运算已并入 `.cache/glossary/`，2026-08-03 清理）、实体运动（yaw 偏航角 / pitch 俯仰角 / 流体加速）、物品组件（1.20.5+）、游戏刻加速（Tick Warping）
  - 关键词：游戏刻, 游戏阶段, 随机刻, 实体运动, 偏航角, 俯仰角, 物品组件, Tick Warping
  - 来源：gtmc-articles MicroTiming、Discovering-Minecraft 实体运动、cubicmetre 视频

- **`glitches.csv`** — 漏洞/非法方块形态术语 [通用]
  - 内容：切片下界传送门（sliced nether portal，更新抑制/跳过）、落沙下界传送门（falling nether portal，落沙非法形态）
  - 关键词：下界传送门, 更新抑制, 更新跳过, 落沙, 非法方块, 切片传送门
  - 来源：TechMCDocs BugsAndExploits/UpdateSuppression、6sPS4yqC72I 视频

- **`proper_nouns.csv`** — 专有名词：人物 / 组织 / 模组 [通用]
  - 内容：人物（cubicmetre、Red Nomster、Mumbo Jumbo、Hermit 隐士）、组织（Hermitcraft、Wavetech）、模组（Item Scroller、Axiom、Carpet 模组）、scarpet 脚本语言
  - 关键词：人物, 组织, 模组, YouTuber, SMP, Hermitcraft, 隐士, scarpet, Carpet

- **`redstone_concepts.csv`** — 红石核心概念 [通用]
  - 内容：切换状态（Toggle State）、强/弱充能（Strong/Weak Power）、红石门（Redstone Gate，中继器/比较器统称）、脚手架信号（Scaffoldstone 脚电）、存储类设计（三宽可堆叠、漏斗锁定、漏斗计数器）
  - 关键词：红石, 充能, 强充能, 弱充能, 二极管, 中继器, 比较器, 脚电, 切换状态, 三宽可堆叠, 漏斗锁定, 漏斗计数器

- **`storage.csv`** — 存储技术术语 [存储]
  - 内容：脉冲式物品分类器、无粉分类器、物品-潜影盒分离器、垂直整合、可变容器阈值、全物品仓库（Main Storage，本视频指 Wavetech；铜傀儡/铜箱子已由 `.cache/mojang/` 覆盖，2026-08-03 清理）
  - 关键词：存储, 物品分类器, 无粉, 潜影盒, 垂直整合, 容器阈值, 全物品仓库

## 子目录

- 当前 `knowledge/01_terminology/` 下无子目录；人物/组织暂存于 `proper_nouns.csv`，待量增后再分拆

## 参考缓存

以下缓存文件由脚本自动生成（`.cache/`，Git 忽略），翻译时作为术语参考，不属于第一类知识：

### Mojang 官方词汇（`scripts/glossary_fetch_mojang.py` → `.cache/mojang/`）

| 文件 | 内容 |
|------|------|
| `redstone.csv` | 红石相关方块/物品官方译名 |
| `blocks.csv` | 方块官方译名 |
| `items.csv` | 物品官方译名 |
| `entities.csv` | 实体官方译名 |
| `misc.csv` | 杂项（生物群系、状态效果等） |
| `MC_version.txt` | 数据对应的游戏版本 |

### 社区术语表（`scripts/glossary_split.py` → `.cache/glossary/`）

从 `_repos/techmc-glossary/` 拆分，按类别独立：

| 文件 | 类别 |
|------|------|
| `general.csv` | 通用红石术语 |
| `computational.csv` | 计算/数电 |
| `mechanical.csv` | 机械/时序 |
| `slimestone.csv` | 史莱姆科技 |
| `storage.csv` | 存储技术 |
| `tree_farm.csv` | 树场 |
| `mob_farm.csv` | 刷怪塔 |
| `contraptions.csv` | 装置/机械 |
| `coding.csv` | 编码/编程 |
| `glitch.csv` | 漏洞/特性 |
| `1.12.2_magic.csv` | 1.12.2 魔法 |
| `other.csv` | 其他 |
| `people.csv` | 人物 |
