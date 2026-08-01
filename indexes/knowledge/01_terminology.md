# 第一类术语知识索引

> 生成时间：2026-08-01（更新：CSV 新增 B36/方块破坏进度保存/服务端碰撞箱 3 条术语；B36/服务端碰撞箱的视频特定机制细节拆至 `knowledge/02_mechanic/` 知识卡）
> 条目数已移除（见 `indexing-rules`：不写易漂移的精确计数，用范围/关键词描述）
> 对应目录：`knowledge/01_terminology/`

## CSV 术语表

- **`_example.csv`** — 表头模板，所有术语 CSV 共享此结构 [通用]
  - 列：`term_en,short_form,definition,notes,term_zh,term_ja`
  - 关键词：模板, 表头, CSV, 规范

- **`_uncategorized.csv`** — 待分拣术语暂存区，Agent 自动登记新术语的唯一写入目标 [通用]
  - 关键词：待分拣, 新术语, Agent写入, 社区发现, 鲁汶聚类, 铜傀儡分类器, 存储技术辅助程序, 沉积物切片, B36, 36号方块, 移动中的方块, 方块破坏进度保存, 服务端碰撞箱

- **`common.csv`** — 通用基础术语（当前为空，仅表头）[通用]
  - 关键词：通用, 基础

- **`game_system.csv`** — 游戏机制/系统术语 [通用]
  - 内容：游戏刻阶段（WTU 世界时间更新 / CT 区块刻 / EU 实体运算 / AT 异步事件 / 随机刻）、实体运动（yaw 偏航角 / pitch 俯仰角 / 流体加速）、物品组件（1.20.5+）、游戏刻加速（Tick Warping）
  - 关键词：游戏刻, 游戏阶段, 随机刻, 实体运动, 偏航角, 俯仰角, 物品组件, Tick Warping
  - 来源：gtmc-articles MicroTiming、Discovering-Minecraft 实体运动、cubicmetre 视频

- **`proper_nouns.csv`** — 专有名词：人物 / 组织 / 模组 [通用]
  - 内容：人物（cubicmetre、Red Nomster、Mumbo Jumbo、Hermit 隐士）、组织（Hermitcraft、Wavetech）、模组（Item Scroller、Axiom、Carpet 模组）、scarpet 脚本语言
  - 关键词：人物, 组织, 模组, YouTuber, SMP, Hermitcraft, 隐士, scarpet, Carpet

- **`redstone_concepts.csv`** — 红石核心概念 [通用]
  - 内容：切换状态（Toggle State）、强/弱充能（Strong/Weak Power）、红石门（Redstone Gate，中继器/比较器统称）、脚手架信号（Scaffoldstone 脚电）、存储类设计（三宽可堆叠、漏斗锁定、漏斗计数器）
  - 关键词：红石, 充能, 强充能, 弱充能, 二极管, 中继器, 比较器, 脚电, 切换状态, 三宽可堆叠, 漏斗锁定, 漏斗计数器

- **`storage.csv`** — 存储技术术语 [存储]
  - 内容：铜傀儡/铜箱子（快照新特性）、脉冲式物品分类器、无粉分类器、物品-潜影盒分离器、垂直整合、可变容器阈值、全物品仓库（Main Storage，本视频指 Wavetech）
  - 关键词：存储, 物品分类器, 无粉, 铜傀儡, 铜箱子, 潜影盒, 垂直整合, 容器阈值, 全物品仓库

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
