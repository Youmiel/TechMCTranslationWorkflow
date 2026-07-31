---
name: glossary-usage
description: 项目术语表（Mojang/TechMC/项目自有）的使用规范、类别预判、加载策略和安全规则。翻译红石内容或检索术语时自动参考。
---

# 术语表使用规范

本项目涉及三个"词汇表"，容易混淆，必须先区分：

| 名称 | 位置 | 性质 | 说明 |
|------|------|------|------|
| **上游术语表** | `_repos/techmc-glossary/` | 第三类，只读 Submodule | TechMC-Glossary 社区维护的合并 CSV |
| **拆分术语缓存** | `.cache/glossary/` | 第二类，脚本生成 | 从上游按 Category 拆分的独立 CSV |
| **项目术语库** | `knowledge/01_terminology/` | 第一类，人工维护 | 本项目的译名标准、人物/组织名录等 |

**Agent 翻译时使用的术语来自拆分缓存 + 项目术语库，不是上游源文件。**

## 安全规则

- **禁止删除任何文件**。`.cache/glossary/` 需要清理时，提示用户手动执行。
- 拆分脚本只写入 `.cache/glossary/`（Git 忽略），不触碰项目其他目录。

## 核心规则

1. **禁止直接使用 `_repos/techmc-glossary/TechMC Glossary.csv`**（源文件是合并格式，且可能过时）
2. **必须使用 `.cache/glossary/` 下的拆分文件**（按类别独立，Agent 按需加载）
3. **使用前检查是否需要更新**

## 工作流程

### 翻译/检索前

```
1. 运行 python scripts/split_glossary.py --check
2. 若退出码 = 1（需要拆分）：运行 python scripts/split_glossary.py
3. 按下方"类别预判"规则确定领域 → 加载 .cache/glossary/<相关类别>.csv
```

### 类别预判（翻译前确定领域）

为节省上下文，不加载全部术语表。通过**视频标题/简介 + SRT 前 20 句**的关键词密度判断领域。

**规则定义在** `.github/experience/glossary_categories.yaml`。该文件由 Agent 协助维护（见下方"配置文件自维护"）。

预判流程：
1. 读 `.github/experience/glossary_categories.yaml`
2. 扫描视频元数据 + SRT 前 20 句，统计每个 `category` 下 `keywords` 的命中次数
3. 命中 ≥2 次的分类 → 加载对应 `.cache/glossary/<category>.csv` 和 `knowledge/01_terminology/<category>.csv`（如存在）
4. 始终加载 `always_load` 中列出的分类
5. 若所有分类命中均 <2 次 → 进入"无法判断"流程

### 无法判断时的处理（配置文件自维护入口）

当无分类命中 ≥2 次时：

1. 从 SRT 前 20 句中提取出现 ≥2 次的技术名词，列出清单给用户：
   ```
   无法自动判断视频领域。以下是在字幕开头高频出现的技术名词：
   - update suppression（3次）
   - CCE（2次）
   - light update（2次）
   
   请确认这些词属于哪个分类（可选多个），或输入自定义分类名：
   [mechanical / slimestone / tree_farm / mob_farm / storage / computational / contraptions / glitch / 1.12.2_magic]
   ```
2. 用户确认后，Agent 编辑 `.github/experience/glossary_categories.yaml`，将新关键词追加到对应分类的 `keywords` 列表中
3. 然后按确认的分类加载术语表，继续翻译流程
4. **注意**：Agent 只能追加关键词，不能修改分类结构或删除已有关键词

### 翻译日志 vs 配置文件自维护

两个机制各司其职，不可混淆：

| | `.github/experience/coverage_log.md` | `.github/experience/glossary_categories.yaml` |
|---|---|---|
| 记录什么 | 数据源检索效果（找到了/没找到） | 领域关键词→分类映射 |
| 维护者 | Agent 自动追加 | Agent 提案 + 用户确认后写入 |
| 触发时机 | 翻译后（阶段三） | 翻译前（阶段〇无法判断时） |
| 目的 | 优化"去哪找" | 优化"加载哪些术语表" |

### 术语对照规则

- CSV 中 `Chinese` 列为标准译名，`Description (Chinese)` 列为中文释义
- `English` 列为标准英文术语
- 若 CSV 中无对应术语，标记 `[待审核: English Term]`
- 严禁自创译名覆盖已有标准

### CSV 解析注意事项

- 术语表的 `definition`、`description` 等列常包含逗号（如"指一种比较器，当接收到方块或库存更新时会改变其信号"），**必须用 Python `csv` 模块解析**，不可用 `split(',')` 或 `grep_search` 按逗号分列
- 读取 CSV 时始终使用 `csv.DictReader`，它会正确处理引号内的逗号
- **编码**：读取 `.cache/glossary/` 和 `knowledge/` 下 CSV 用 `utf-8-sig`（可能带 BOM）
- Agent 用 `grep_search` 查找术语时可以模糊匹配内容，但提取译名时务必读取完整行通过 `csv` 模块解析

## 注意事项

- `.cache/glossary/` 是 Git 忽略的临时缓存，可随时删除后重跑脚本
- 上游术语表通过 `git submodule update --remote` 同步
- 如果 `--check` 报错（源文件缺失），可能是 submodule 未初始化，运行 `git submodule update --init`
