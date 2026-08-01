# 通用知识卡模板

> 用途：记录一条**词汇/概念/机制**的知识要点——定义、语境用法、翻译注意事项等。
> 每词/每概念一卡，文件命名 `<英文术语>.md`，按主题放对应分目录（`01_terminology/` 只存放术语表，不要添加知识卡）；
> 创建后同步更新 `indexes/knowledge/` 下对应索引。

## 模板

```markdown
---
term: <英文术语/概念名>
aliases: [<同义词/缩写>]
category: <分类，与 glossary_categories.yaml 一致>
source: <来源：视频标题 / 文档 / 人工审核>
version: [<适用版本>]
status: 待审核
---

# <术语名>

## 要点
<!-- 该词/概念的核心定义、特殊指代或机制要点 -->

## 翻译注意事项
<!-- 标准/语境译名 + 依据（查词表 / 上下文推断 / 用户确认） -->

## 备注
<!-- 来源、首次出现时间戳、关联词条等 -->
```

## 字段说明

| 字段 | 说明 |
|------|------|
| `term` | 英文标准术语/概念名 |
| `aliases` | 同义词/缩写 |
| `category` | 分类，与 `glossary_categories.yaml` 一致 |
| `source` | 来源：视频标题 / 文档 / 人工审核 |
| `version` | 适用版本，遵循 `indexing-rules` 版本标注（`[通用]`/`[1.21+]` 等） |
| `status` | `待审核`；用户确认后改 `已确认` |

## 示例

```markdown
---
term: main storage
aliases: [MS, main storage item sorter]
category: storage
source: Solving Minecraft's Storage Problem (cubicmetre)
version: [通用]
status: 已确认
---

# Main Storage（全物品仓库）

## 要点
存储科技术语：可分类并存储几乎所有可获得物品的巨型仓库；本视频特指 Wavetech 的全物品仓库，勿译"主存储"。

## 翻译注意事项
全物品仓库。依据：TechMC Glossary `storage` 分类 + 用户审计确认。

## 备注
- 首次出现：00:07:01（Wavetech's main storage item sorter）
- 关联：`storage.csv`、`.github/experience/trap_words.md`
```
