# 陷阱词清单（看似普通、实为科技术语）

> 定位：与普通词汇表（术语 → 译名，知识层）**正交**的**防呆提示层**——专门收录**看似普通英文、易被固有思维误判为普通词而不去查**的科技术语（如 `filter`、`main storage`、`Hermits`）。
> 普通词汇表登记了译名 ≠ 不会漏查：语义扫描看到这类词的第一反应是普通英文，**根本不会触发查词冲动**，L1/L2 里的译名形同虚设。
> 使用：类别预判命中某分类时加载该分类清单；语义扫描/翻译时对清单词（含词形变体）**强制触发 L1/L2 查词**，不论是否已登记入 L1。
> 维护：Agent 每视频识破「没想到是术语」的词就追加（只追加，不删改既有条目），**与是否已入 L1 无关**——入 L1 只保证 `glossary_lookup.py scan` 字面覆盖，不保证语义扫描想起去查。分类与 `glossary_categories.yaml` 一致。

## 格式约定

```
陷阱词（词形/同义变体） → 正确术语 → 标准译名（依据）
```

同一条多个变体合并为一行（`/` 分隔）。

## storage（存储技术）

| 陷阱词 | 正确术语 | 标准译名 | 依据 |
|--------|----------|----------|------|
| main storage / main storage item sorter | main storage | 全物品仓库 | TechMC 存储分类；曾误判直译"主存储" |
| filter / item filter / filters | item filter | 物品分类器（语境常作"分类器"） | TechMC 存储分类；非"过滤器" |
| sorter | item sorter | 物品分类器 | TechMC 存储分类 |

## proper_nouns（人物/组织）

| 陷阱词 | 正确术语 | 标准译名 | 依据 |
|--------|----------|----------|------|
| Hermit(s) | Hermitcraft member | Hermitcraft 成员 | knowledge/ proper_nouns.csv |

## general（通用，始终加载）

| 陷阱词 | 正确术语 | 标准译名 | 依据 |
|--------|----------|----------|------|
| target / target block | target | 标靶 / 目标（按语境二选一） | knowledge/ 01_terminology/target.md；投射物/信号语境→标靶，仇恨/追踪语境→目标 |
| credits / credits video / credit video | credits | （简介）引用的视频 | knowledge/ 01_terminology/credits.md；credits video 指被引用/被致谢的视频，非"致谢视频" |
