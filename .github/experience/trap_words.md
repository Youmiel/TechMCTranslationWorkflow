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
| blocker / blocker items | blocker | 占位物 | TechMC 存储分类（`.cache/glossary/storage.csv`：填充物, 占位物）；非"阻挡物" |
| loader / box loader / unloader | box loader / unloader | 打包机 / 拆包机 | TechMC 存储分类；潜影盒语境作"潜影盒打包机/拆包机" |
| tileable / tiling | tileable | 可堆叠 | L1 three-wide tileable=三宽可堆叠；非"可平铺/可拼接" |
| footprint | footprint | 占地尺寸 | 红石装置语境；非"足迹/脚印" |
| bleed over | bleed over | 信号溢出 | 比较器信号越阈值外溢到相邻单元；非"流血/渗出" |
| impulse filter / impulse sorter | impulse sorter | 经典物品分类器（上下文提及作者时用原名 Impulse 分类器） | 指最经典的物品分类器（三格红石粉布局），最早由 Impulse SV 推广使用，词源于人名而非"脉冲"（2026-09-13 用户确认）；**禁用"脉冲式分类器"** |
| pots / pot | decorated pot | 陶罐（正式作「饰纹陶罐」） | 判据：**陶罐是容器**（存 1 格物品、漏斗/投掷器/比较器可交互），**花盆不是容器**（JE 非方块实体、无红石交互、3/8 格高）——与 droppers / composters 等容器并列、讲存储/漏斗/比较器 → 「陶罐」；与植物/装饰并列 → 「花盆」；`flower pot` 才译花盆，勿见 pot 即译花盆（2026-09-13 用户指正；2026-09-17 wiki 查证补判据，详见 knowledge/02_mechanic/pot.md） |

## mechanical（红石元件、信号、更新机制）

| 陷阱词 | 正确术语 | 标准译名 | 依据 |
|--------|----------|----------|------|
| provide redstone power / powered / powered block | powering / activating / charging | 供能 / 激活 / 充能（三级严格区分） | wiki `红石电路/充能与激活`；非红石导体（如漏斗）不宜称"充能"；详见 knowledge/02_mechanic/power-vs-charge.md |

## proper_nouns（人物/组织）

| 陷阱词 | 正确术语 | 标准译名 | 依据 |
|--------|----------|----------|------|
| Hermit(s) | Hermitcraft member | Hermitcraft 成员 | knowledge/01_terminology/proper_nouns.csv |

## general（通用，始终加载）

| 陷阱词 | 正确术语 | 标准译名 | 依据 |
|--------|----------|----------|------|
| target / target block | target | 标靶 / 目标（按语境二选一） | knowledge/02_mechanic/target.md；投射物/信号语境→标靶，仇恨/追踪语境→目标 |
| credits / credits video / credit video | credits | （简介）引用的视频 | knowledge/02_mechanic/credits.md；credits video 指被引用/被致谢的视频，非"致谢视频" |
