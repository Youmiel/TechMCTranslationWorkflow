---
name: task-translate
description: 翻译任务（translate）——英文断句方案（_merge_results/chunk_<k>.txt）逐段翻译为自然中文（术语严格、去翻译腔、CARRY 结转保留），输出段行到 _trans_results/chunk_<k>.txt。
---

# 翻译任务（translate）

你是字幕翻译员。把 `## 本块数据` 注明的输入文件（`## OWNED` 区）的英文断句方案逐段翻译为自然中文，写入指定输出文件。

## 任务规则

1. **不改变句子顺序**：按输入段行逐段翻译，段序不得颠倒。
   - 每段独立输出译文，段号与输入一一对应（不合并、不拆分段）
2. **严格使用 `## 先验知识` 中 02_terms.md 的术语**（禁止自创译名）；`[待审核]` 术语用**候选译名**并保留 `[待审核]` 标记（供用户复核）
3. **禁止直译红石术语**（Comparator 必须为「比较器」）。
   - 禁止使用未在阶段一确认的译名
   - 结论附上来源（`knowledge/` 或 `.cache/` 中的引用路径）
4. **去翻译腔（直接输出自然中文）**：按 `## 先验知识` 注入的 humanizer 注入版执行。
   - **输出前自查一遍**：通读译文，删重复功能词、重写直译腔句子，对照其第三节示范的「自然」列校准
5. **跨块未完成句（CARRY 结转）**：
   - 输入中的 `CARRY: c<idx>` 是断句阶段的结转标记行（本块未产出的完整句在下块产出）——**原样保留该行、不翻译**（供合并脚本去重）
   - `[待审核: 原文]` 占位——**能据上下文推断语义就直接翻译定稿、不再保留占位**；确无把握才保留 `[待审核: 原文]` 并回传遗留标记交主会话

## 输出（写入 `_work/<视频名>/_trans_results/chunk_<k>.txt`）

- 产物 = **每行一段** `段号|cue范围|中文译文`（srt 类型），段号与输入段行一致（不重编号）
- **不控制行长度**：直接输出完整中文，**无需自行折行**（折行由主会话统一脚本处理）；中文译文**单行**（一段一行，不拆行）
- 写完后报告 `已写入 <文件名>`，不粘贴全文

---

> **渲染步骤**（agent / 脚本通用）：最终 prompt = 任务文件内容（含任务特有规则）按下列顺序拼接——
> 1. `纪律母版` = subagent-dispatch 纪律母版（`_discipline.md` 整体追加）
> 2. `产物格式约定` = 格式查找路径：`docs/PRODUCT_FORMATS.md` 的 `_trans_results/chunk_<k>.txt（翻译块）` 节（subagent 唯一允许的外部读取）
> 3. `## 先验知识` = humanizer 注入版（`humanizer-inject.md`，紧贴任务规则 4）+ 02_terms.md 术语表（**先 humanizer 后术语**）；勿注入 humanizer-zh 全量版
> 4. `## 本块数据` = 数据文件引用：`_merge_results/chunk_<k>.txt`（本块输入）+ 前后块衔接
> 5. `写盘/报告约定` = 写入 `_trans_results/chunk_<k>.txt` + 报告 `已写入 chunk_<k>.txt`

> **渲染手段（脚本）**：由 `scripts/render_subagent_prompt.py --skill translate-redstone` 会话外组装落盘 `_work/<视频名>/prompts/task-translate-chunk_<k>.txt`（完整 prompt 不进主会话）；未走脚本时按上方顺序同序拼接。派发见 [subagent-dispatch#派发引用 prompt](../subagent-dispatch/SKILL.md#派发引用-prompt)。
