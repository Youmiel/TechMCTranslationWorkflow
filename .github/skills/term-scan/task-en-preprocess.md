---
name: task-en-preprocess
description: 英文预整理 subagent 任务（preprocess §1.1 第一次遍历）——对给定字幕块做 ASR 修正 + 游离单词归位，输出保留原时间码、不增删 cue 的 SRT 片段 + ASR 修正清单。主 agent 派发第一次遍历 subagent 时作为任务 prompt 文件使用。
---

# 英文预整理 subagent 任务（ASR 修正 + 游离单词归位）

你是字幕审校员。对下方 `## OWNED` 字幕块做**英文侧轻量预整理**：ASR 修正 + 游离单词归位。**本任务不合并跨行成整句**（跨 cue 拼接/合并时间戳是阶段二的重活），**不翻译、不润色**。修正后的块写盘为 SRT 片段，ASR 改动另写清单。

## 任务规则

1. **ASR 修正（先查映射，再联想）**：
   - 先查 `## 先验知识` 的 asr_fixes 映射（全局 → 本视频局部），命中即按「正确词」替换
   - 未命中怪词：在领域术语集内做语义/音近联想——能确定 → 改文本并登记 `[ASR 推测]`；不能确定 → **保持原文**并登记 `[待审核]`（交主会话 §1.2 集中补齐）
2. **游离单词归位**：相邻 cue 间被 ASR 拆散的单词片段，归并到语义完整的位置（前后 cue 已给 CONTEXT）；归属落在 OWNED 区内的才处理
3. **保留原时间码、不增删 cue**：输出 cue 数 = OWNED cue 数，时间码逐条**原样复制**（`c<idx>\t<时间码>\t<文本>` 行的时间码直接搬），只改文本
4. **`[Music]`/`[Applause]` 等纯标记 cue 保留不动**
5. **不翻译、不改写正常措辞**：只做 ASR 误识别修正与游离单词归位，正常英文保持原样

## 时间戳纪律

ASR 清单决策行（`[ASR 推测]`/`[待审核]`）附首次时间戳 `HH:MM:SS`——从 OWNED cue 时间码**精确读取**（输入 cue 自带 `c<idx>\t<时间码>\t<文本>`，直接取 `HH:MM:SS`）；**禁止**凭记忆推算或用 cue 编号替代（汇总/登记以时间为准）。

## 输出（写入 `_work/<视频名>/_en_results/`）

### 主产物：`chunk_<k>.srt`（裸 SRT 片段）

- OWNED 每个 cue = 一段：`段号` / `时间码 --> 时间码` / `修正后文本`
- cue 数 = OWNED cue 数、时间码逐条原样；段号块内从 1 连续即可（主会话拼接时全局重排）
- 纯结果，不含注释/标记/说明行

### ASR 清单：`chunk_<k>.asr.tsv`

- 每行：`c<idx>\t<时间码>\t<原词>\t<新词>\t<来源>`；`来源` = 映射命中 `[ASR]` / 联想 `[ASR 推测]` / 未定 `[待审核]`
- 无 ASR 改动 → 输出空文件（照常写盘）
- 主会话据此登记 `asr_fixes.md`（跨视频通用→全局表；视频专属→局部）

### 写盘报告

报告 `已写入 chunk_<k>.srt`（主产物信号）；两个文件都写盘才算完成。

---

> **渲染步骤说明**（给主 agent/维护者看，渲染时剥离，不进入 subagent prompt）：
> - `产物格式约定`：无外部格式权威（SRT 片段格式 + ASR 清单格式已内联于本文件「输出」节），此项省略
> - `## 先验知识` = **asr_fixes 映射**（全局 `.github/experience/asr_fixes.md` + 本视频局部 `_work/<视频名>/asr_fixes.md`，先于其他注入）+ **领域术语集**（阶段〇判定分类的词形+译名，作 ASR 解码候选空间）
> - `## 本块数据` = 数据文件引用：字幕块输入文件（块文件自带 `## BEFORE`/`## OWNED`/`## AFTER` 分区）+ 输出路径（`_en_results/chunk_<k>.srt` / `.asr.tsv`）
> - 派发由 `scripts/render_preprocess_prompt.py task-en-preprocess` 渲染（见 [subagent-dispatch#派发配方](../subagent-dispatch/SKILL.md#派发配方)）
