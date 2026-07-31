# 第一类术语知识索引

> 生成时间：2026-07-31
> 对应目录：`knowledge/01_terminology/`

## CSV 术语表

- **`_example.csv`** — 表头模板，所有术语 CSV 共享此结构 [通用]
  - 列：`term_en,short_form,definition,notes,term_zh,term_ja`
  - 关键词：模板, 表头, CSV, 规范

- **`_uncategorized.csv`** — 待分拣术语暂存区 [通用]
  - Agent 自动登记新术语的唯一写入目标，人工定期分拣
  - 当前条目：12 条（2026-07-31 首次从 _repos/ 提取）
  - 关键词：待分拣, 新术语, Agent写入, 暂存

## 子目录

- **`organizations/`** — 组织/团队名录
  - 当前状态：空
  - 关键词：组织, 团队, 社区

- **`people/`** — 人物名录
  - 当前状态：空
  - 关键词：人物, 作者, 译者

## 参考缓存

以下缓存文件由脚本自动生成（`.cache/`），翻译时作为术语参考：

### Mojang 官方词汇（`scripts/fetch_mojang_glossary.py`）

| 文件 | 内容 |
|------|------|
| `redstone.csv` | 红石相关方块/物品官方译名 |
| `blocks.csv` | 方块官方译名 |
| `items.csv` | 物品官方译名 |
| `entities.csv` | 实体官方译名 |
| `misc.csv` | 杂项（生物群系、状态效果等） |
| `MC_version.txt` | 数据对应的游戏版本 |

### 社区术语表（`scripts/split_glossary.py`）

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
