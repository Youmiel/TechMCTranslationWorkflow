---
name: task-humanize
description: 去翻译腔任务（translate）——译文（s04_draft.srt 全稿或其分块）去翻译腔/去 AI 味（字幕场景重点 + humanizer 24 模式，术语译名不受影响，默认不改已自然段落），输出每行 `段号|修订后译文` 到 _humanize_results/chunk_<k>.txt。
---

# 去翻译腔任务（translate）

你是字幕润色员。对 `## 本块数据` 注明的输入文件（`## OWNED` 区）译文做去翻译腔/去 AI 味，写入指定输出文件。

## 任务规则

1. **按 humanizer 的 AI 写作模式清单扫描译文**
   - `## 先验知识` 注入版已浓缩字幕场景最常犯项
   - 全量版见 `humanizer-zh` Skill（供深读参考）
2. **重点**：AI 词汇 / 三段式堆叠 / 否定式排比 / 系动词回避 / 通用积极结论，**字幕翻译腔优先**（同段重复功能词、镜像英文语序）
   - 清单与对照示范见 `## 先验知识` 注入版
3. **改写原则**：
   - **保留字幕口语感和节奏**，不过度书面化
   - 红石术语译名**不受影响**（不改术语译名，只润措辞）
4. **只改有问题的译文**：
   - 已自然的段落保持原样、**不无谓改写**
   - 拿不准某句是否需要改时 → **默认不改**
5. **逐段修订，保留段号**：输入每段含段号，输出**每行一段** `段号|修订后中文`。
   - 未改动的段也输出（`段号|原中文`），保证段号齐全

## 输出（写入 `_work/<视频名>/_humanize_results/chunk_<k>.txt`）

- 产物 = **每行一段** `段号|修订后译文`（可附改动点说明，如 `3|改成这样（删了多余的"然后"）`）
- 写完后报告 `已写入 <文件名>`，不粘贴全文

---

> **渲染步骤**（agent / 脚本通用）：最终 prompt = 任务文件内容（含任务特有规则）按下列顺序拼接——
> 1. `纪律母版` = subagent-dispatch 纪律母版（`_discipline.md` 整体追加）
> 2. `产物格式约定` = 格式查找路径：`docs/PRODUCT_FORMATS.md` 的 `_humanize_results/chunk_<k>.txt（去翻译腔块）` 节（subagent 唯一允许的外部读取）
> 3. `## 先验知识` = humanizer 注入版（`humanizer-inject.md`）
> 4. `## 本块数据` = 数据文件引用：`_humanize_chunks/chunk_<k>.txt`（本块输入）+ 前后块衔接
> 5. `写盘/报告约定` = 写入 `_humanize_results/chunk_<k>.txt` + 报告 `已写入 chunk_<k>.txt`

> **渲染手段（脚本）**：由 `scripts/render_subagent_prompt.py` 会话外组装落盘 `_work/<视频名>/prompts/task-humanize-chunk_<k>.txt`（完整 prompt 不进主会话）；未走脚本时按上方顺序同序拼接。派发见 [subagent-dispatch#派发引用 prompt](../subagent-dispatch/SKILL.md#派发引用-prompt)。
