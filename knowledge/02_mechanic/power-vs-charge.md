---
term: powering / activating / charging
aliases: [power, powered, activate, charge, 供能, 激活, 充能]
category: mechanical
source: Minecraft Wiki 红石电路/充能与激活 + 用户裁定（2026-09-13，ZXGpmaIcMMo PRR 5）
version: [通用]
status: 已确认
license: CC BY-NC-SA
---

# Powering / Activating / Charging（供能 / 激活 / 充能）

## 要点

`provide redstone power`、`powered`、`charged` 一组词在中文里都容易被笼统写成"充能 / 通电 / 通能量"，但 wiki 对三者有**严格三级区分**，混用会让"红石导体"相关机制描述失真。

| 术语 | 英文 | 定义 | 例 |
|------|------|------|-----|
| **供能** | Powering | 一个方块的输出端对齐另一方的输入端，前者使后者**产生非零红石信号强度或特定响应**的过程 | 拉杆供能铁门 |
| **激活** | Activating | 供能过程中被供能方块**确实产生了响应**（改变方块状态、召唤实体、生成粒子、播放声音、执行命令等） | 投掷器被激活并投掷 |
| **充能** | Charging | 被供能方块**能以所有方向为输出端继续向其他方块供能** | 红石块充能毗邻导体 |

- **充能的前提 = 红石导体**（Redstone Conductor，即"导电方块"）；非导体（如漏斗、台阶等）**不能被充能**，只能被供能 / 被激活
- 充能分**强充能（Strongly Charging）**与**弱充能（Weakly Charging）**：前者能激活毗邻红石线，后者不能
- 正在被充能的导体称**充能方块**
- 激活与充能**可同时存在**（如发射器/投掷器被强充能时，既被激活也被充能）
- wiki 注明：充能是**玩家为方便研究而提出的理论**，游戏内并无"充能/未充能"方块状态，本质是方块更新 + 元件激活

## 翻译注意事项

| 英文原文 | 建议译法 | 说明 |
|----------|----------|------|
| `provide redstone power to X` | 给 X **供能** / 给 X **通入红石信号** | 避免一律写"充能"（X 未必是导体） |
| `X is powered` | X **被供能** / X **已激活** | 按是否强调"产生响应"选 |
| `X is (strongly/weakly) charged` | X **被强充能 / 弱充能** | 仅当 X 是红石导体 |
| `X through a conductive block`（经导电方块） | 该**导电方块被充能**后激活 X | 此语境"充能"正确 |
| `powered block` | **充能方块** | 导体被供能后的称呼 |

- **社区口语**中"充能"常被泛指"通电"，但本稿按 wiki 严格用法处理：导体→充能；非导体→供能/激活
- 字幕里若同一句同时含"直接供能"与"经导电方块"，应分别用**供能**与**充能**，不可统一成一个词

## 备注

### 实例（ZXGpmaIcMMo PRR 5）

原文（00:12:01 `if you provide Redstone power to a hopper whether directly or just activating it through a conductive block`）：

- 直接 → **供能**漏斗（漏斗是非红石导体，不能"充能"）
- 经导电方块 → 导电方块被**充能**，继而激活漏斗

本稿译作"给漏斗直接通红石能量 / 通过导电方块激活它"——口语可读，未误用"充能"。

### 来源与关联

- 来源：wiki `红石电路/充能与激活`（2026-08-29 版）+ 用户裁定（2026-09-13，ZXGpmaIcMMo PRR 5 审核）
- 关联：`.github/experience/trap_words.md`（mechanical 分类）、`.github/experience/source_experience.md`、`knowledge/01_terminology/redstone_concepts.csv`
