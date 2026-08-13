---
name: term-scan
description: 阶段一术语扫描（translate-redstone §1.1）的机制细节：ASR 误识别的语义联想解码、机械查找（glossary_lookup.py scan）作术语扫描的一部分、术语识别。做术语扫描时参考。
---

# 术语扫描（阶段一 §1.1 机制）

> 编排步骤见 `translate-redstone §1.1`；本 Skill 是 §1.1 的机制权威，§1.1 只留指针。

## 原则：语义联想为主，机械查找补漏

- ASR 误识别修正、术语语义/语境理解、相关性判断，靠 **Agent 自身的语义联想/推理**（注入领域术语集作上下文），**不用字符串相似度等算法**。这里说的"联想"指 Agent 自己的语言理解，**不是去编写/调用外部 LLM/API 程序**
- **机械查找**（`glossary_lookup.py scan`）是**术语扫描流程的一部分**（非独立阶段）：字面精确匹配，把"已登记词确实出现在字幕里"找全（治漏翻），产出素材供 Agent/subagent 使用，不做任何理解/判定

## ASR 语义解码（主流程）

1. 注入素材：
   - `.github/experience/asr_fixes.md`（跨视频通用映射，按正确词聚合）
   - `_work/<视频名>/asr_fixes.md`（本视频已识别映射，如有）
   - 阶段〇语义判定的**领域术语集**（L1+L2 词形+译名，作解码候选空间）
2. 遇怪词，先查全局表 → 再查本视频局部表
3. 未命中，则在术语集内做**语义/音近联想**，标 `[ASR 推测]`（附首次时间戳，格式 `HH:MM:SS`——**从字幕/输入 cue 的时间码精确读取**，勿凭记忆推算、勿用 cue 编号）
4. 确认后按分层登记（规则见 `term-registration`「ASR 映射登记」）：跨视频通用→全局表；视频专属→`_work/<视频名>/asr_fixes.md`（必要时入术语库）
5. 完成后写 `01_subtitle_asr_fixed.srt`

## 机械查找（补充机制）

命令：`python scripts/glossary_lookup.py scan <01_subtitle_asr_fixed.srt> --categories <L2 文件集合，可多个> --levels L1,L2 --out scan_terms.txt`

- 输出：`cue|时间戳|词|译名|来源|层级`
- `--categories`：**按文件名过滤 L2**（`.cache/glossary/<文件名>.csv`），由 Agent 按阶段〇**语义判断**给出（可跨多个分类），非机械单一输出
- **三套词汇表 category 命名互不对应**：L2 文件名与 `glossary_categories.yaml` 分类部分重叠但不对应（L2 另有 `general/other/people`）；L1 文件分类（`common/game_system/...`）是另一套命名且**始终全量加载**；L1.5（`redstone/blocks/items/entities/misc`）又一套，默认不扫，需显式 `--levels L1,L1.5,L2`
- 参数/格式细节以 `scripts/glossary_lookup.py` docstring 为准（唯一权威）

## 术语识别（subagent）

- 每块注入：本块命中项（从 `scan_terms.txt` 按 OWNED cue 范围过滤）+ 术语/陷阱词知识卡
- subagent 职责：命中项强制查词确认、补词形变体（复数/跨行）、排除误报（普通词撞 Mojang 冷门条目）、识别真新词（L3）
- **时间戳**：决策行（`[ASR 推测]`/`[推断]`/`[待审核]`）附首次时间戳，格式统一 `HH:MM:SS`（不带毫秒）——**从输入 OWNED cue 的时间码精确读取**，输入 cue 自带 `c<idx>\t<时间码>\t<文本>`，直接取该 cue 的 `HH:MM:SS`；**禁止**凭记忆推算或用 cue 编号替代（汇总/确认以时间为准）
- **块输出格式**（写 `_work/<视频名>/_term_results/chunk_<k>.txt`，每行一条，UTF-8）：`term_en|译名|来源|ASR修正|[标记]`——`[标记]` = `[待查]`/`[待审核]`/`[ASR 推测]`/`[推断]`；决策行在行尾附首次时间戳（如 `@HH:MM:SS`）
- 派发模板见 [subagent-dispatch#每块 prompt 模板](../subagent-dispatch/SKILL.md#每块-prompt-模板)
