---
name: redstone-preprocess
description: 红石字幕翻译前置——阶段〇（领域预判与准备）+ 阶段一（术语扫描与知识补齐），产出 ASR 修正字幕（01）与确认术语表（02）。
---

# 红石字幕翻译前置（redstone-preprocess）

> 定位：翻译前的**领域预判 + 术语补齐**（阶段〇 + 阶段一），产出 ASR 修正字幕与确认术语表，供翻译阶段使用。

## 输入 / 输出（产物契约）

| 产物 | 时机 | 内容 | 恢复价值 |
|------|------|------|----------|
| `<工作目录>/01_subtitle_asr_fixed.srt` | §1.1 第一次遍历后 | ASR 修正 + 游离单词归位的英文字幕（保留原时间码、不增删 cue） | 避免重复 ASR 解码 |
| `<工作目录>/02_terms.md` | §1.3 用户确认后 | 确认后的术语映射表（时间戳/原文/译名/来源/ASR 修正） | 翻译唯一译名依据，跳过整个阶段一 |

> 产物结构/格式/标记约定（单一权威）见 [PRODUCT_FORMATS](../../../docs/PRODUCT_FORMATS.md)；处理前先查对应节，勿现查代码猜格式。

## 依赖

`use-glossary` · `term-scan` · `term-registration` · `subagent-dispatch` · `csv-rules` · `wiki-tools` · `segment-subtitles` · `redstone-conventions` · `maintain-knowledge`

## 注意事项

- **环境**：见 [redstone-conventions#环境](../redstone-conventions/SKILL.md#环境)
- **CSV**：按 [csv-rules](../csv-rules/SKILL.md)（`utf-8-sig` 读 / `utf-8` 写、`csv` 模块解析、脚本勿 `python -c` 内联）
- **ASR**：YouTube 自动生成字幕可能不可靠，先解码再翻译；解码查全局 asr_fixes → 未命中查本视频局部；登记分层（通用→全局表，专属→局部）

## 阶段〇：领域预判与准备（翻译前，轻量扫描）

1. **刷新本地知识**：`python scripts/refresh_cache.py`（统一入口：Mojang/TechMC 自动刷新，**Wiki 只告警不自动抓取**——Wiki 刷新按需走 [wiki-tools](../wiki-tools/SKILL.md) 降级链；或按需 `glossary_split.py --check`、`glossary_fetch_mojang.py`）
2. **类别预判**：按 [use-glossary#类别预判](../use-glossary/SKILL.md#类别预判翻译前确定领域)——读 `.github/experience/glossary_categories.yaml`，扫描标题/简介 + 前 ~20 句关键词，命中 ≥2 次加载对应分类；**产出领域判断并向用户报告确认**；**无法确定/拿不准时必须列出候选请用户选择，不得静默跳过**（见 [use-glossary#无法判断时的处理](../use-glossary/SKILL.md#无法判断时的处理必须交互配置文件自维护入口)）；确认后如有该分类未收录的高频词，回填 yaml `keywords`
3. **红石专属补充加载**：`.cache/mojang/redstone.csv`（~100 条，全量）；`.cache/mojang/<类别>.csv`（非红石 ~1400 条不预加载，L1 未命中 grep 按需查）
4. **加载知识地图**：读 `indexes/knowledge/` + `indexes/repos/_manifest.md`（机制知识卡 `knowledge/02_mechanic/`、外部仓库经索引定位）
5. 读 `docs/SOURCE_COVERAGE.md`（各数据源擅长/不擅长）
6. 读全局 `.github/experience/asr_fixes.md` + 本视频局部 `_work/<视频名>/asr_fixes.md`（准备 ASR 解码）

## 阶段一：术语扫描与知识补齐

### 1.1 术语扫描
> 机制见 [term-scan](../term-scan/SKILL.md)（权威，含术语识别块输出格式）、[use-glossary#四级查找](../use-glossary/SKILL.md#四级查找)；长视频分块见 [redstone-conventions#长视频分块](../redstone-conventions/SKILL.md#长视频分块全流程通用机制)（通用机制）。

> **派发边界**：术语识别**一律派 subagent**（每块一个，块数由骨架决定），无需报告策略——见 [subagent-dispatch#派发边界](../subagent-dispatch/SKILL.md#派发边界哪些派-subagent--哪些主会话)。

1. **加载领域知识**：加载阶段〇判定的分类术语文件（L2 按文件名、L1 全量），建立术语映射表
2. **第一次遍历（英文侧轻量处理）** → 写 `01_subtitle_asr_fixed.srt`：
   - ASR 修正（注入 asr_fixes + 领域术语集）+ 游离单词归位（见 [segment-subtitles#英文预整理](../segment-subtitles/SKILL.md#英文预整理游离单词归位)）
   - **跨行合并成整句/合并时间戳是阶段二的重活，此处不做**（translate→两遍式断句；reflow→回填步骤 1 合并补标点）
   - **立即校验时间轴**：`python scripts/srt_check_segments.py 01_subtitle_asr_fixed.srt --orig <原始ASR.srt> --cue-exact`——01 只改文本、保留原时间码、不增删 cue；时间轴错位立即回本步修正（否则一路传最终稿）
3. **机械查找**：`python scripts/glossary_lookup.py scan <01> --categories <L2 集合> --levels L1,L2 --out scan_terms.txt`，命中项无论像不像术语一律按登记译名处理
4. **术语识别（派 subagent）**：每块派一个术语识别 subagent——prompt 按 [subagent-dispatch#派发配方](../subagent-dispatch/SKILL.md#派发配方任务文件--纪律母版--知识卡--块数据) 组装（任务文件 = `term-scan/task-term-recognition` + 纪律母版 + 知识卡 + 块数据），结果写 `_work/<视频名>/_term_results/chunk_<k>.txt`；N 由 `context_estimate.py` 定（执行一律 subagent，见 conventions「长视频分块」）
5. **主会话汇总**：按 `term_en` 合并去重；`[ASR 推测]`/`[推断]`/`[待审核]` 行保留**首次时间戳**（格式 `HH:MM:SS`，取字幕时间码精确值）；L3 未命中进 §1.2
6. **非预期命中记录**：scan 命中项/查词/知识卡若来自**未预判分类**的词汇表 → 记录该分类 + 命中词，阶段末回填 yaml `keywords`（见 [use-glossary#运行中反哺](../use-glossary/SKILL.md#运行中反哺非预期命中--回填-categories)）

> 术语识别 subagent 的任务规则见 `term-scan/task-term-recognition`（现成任务文件；派发配方见 [subagent-dispatch#派发配方](../subagent-dispatch/SKILL.md#派发配方任务文件--纪律母版--知识卡--块数据)）。

### 1.2 集中补齐（翻译前一次性完成所有网络请求）
> 缓存命中判定、`fidelity` 回源、降级链、请求频率、保真阶梯、缓存写入见 [wiki-tools](../wiki-tools/SKILL.md)（权威）；数据源选择参考 `docs/SOURCE_COVERAGE.md`。

1. "待查列表"去重，按数据源分组
2. **查缓存（第一道门）**：中文译名/候选命中 `.cache/wiki/<中文规范标题>.md` → 直接读、不再联网；缺失时 grep_search 搜正文兜底
3. 未命中判断数据源：Wiki 擅长类型（基础定义/合成配方）→ `mc-wiki-fetch-mcp` 的 `get_page`，不可用按可靠度降级（fetch_wiki.py → minecraft-wiki-mcp）；社区类型（高端技术/经验）→ 查 `indexes/repos/` 索引
4. 从返回内容/社区资料提取译名，补内存映射表
5. **上下文推断（降级）**：回原文搜首次出现前后 3-5 句，能推断则标 `[推断：原词 — 基于视频上下文]`；不足则给**候选译名 + 依据**标 `[待审核]`
6. 仍无法确定 → 最终标 `[待审核：原词 → 候选译名（依据）]`——**不得只留原文**，必须带候选

### 1.3 术语确认

输出术语清单供用户确认，**ASR 误识别单独一栏**集中批注。**决策行（`[ASR 推测]`/`[推断]`/`[待审核]`）必须附字幕时间戳**；普通行同样填写：

```
| 时间戳 | 原文 | 译名 | 来源 | ASR 修正 |
|---|---|---|---|---|
| 00:12:34 | Comparator | 比较器 | knowledge/ | — |
| 00:07:12 | sorder | 分类器 | [ASR 推测] | sorter |
| 00:09:20 | piston phase offset | 活塞相位偏移 | [推断：视频上下文] | — |
| 00:21:03 | Sub-tick | [待审核] 候选：亚刻（据 sub-tick 字面 + 游戏刻语境推测） | 未找到 | — |
```

- `[推断]`：Agent 从对白推测，用户重点确认；`[待审核]`：附候选 + 依据，确认或否决，不默认保留原文
- `ASR 修正` 列：列原始误识别词，可一次确认/纠正全部推测
- **时间戳列**：取首次出现处 `HH:MM:SS`（**从字幕时间码精确读取**，不是 cue 编号、不是凭记忆推算；SRT 时间码 `HH:MM:SS,mmm` 去毫秒即得），决策行缺失视为不完整输出
- **落盘**：确认后写 `02_terms.md`（§1.4 入库前）

### 1.4 术语入库

按 [term-registration#同步步骤](../term-registration/SKILL.md#同步步骤)：筛选已确认（排除 `[待审核]`）→ 写 `_uncategorized.csv`（查重不覆盖）→ ASR 映射登记 `asr_fixes.md`。
> `_uncategorized.csv` 变动不更新 `indexes/knowledge/`（纯静态索引，见 `indexing-rules`）
