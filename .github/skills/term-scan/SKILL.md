---
name: term-scan
description: 阶段一术语扫描（redstone-preprocess §1.1/§1.2）的机制权威：子任务拆法（任务文件导航）、ASR 语义解码、机械查找、术语识别、集中补齐。做术语扫描时参考。
---

# 术语扫描（阶段一 §1.1/§1.2 机制）

> 编排步骤见 `redstone-preprocess §1.1/§1.2`；本 Skill 是机制权威，§1.1/§1.2 只留指针。

## 原则：语义联想为主，机械查找补漏

- ASR 误识别修正、术语语义/语境理解、相关性判断，靠 **Agent 自身的语义联想/推理**（注入领域术语集作上下文），**不用字符串相似度等算法**。"联想"指 Agent 自己的语言理解，**不是去编写/调用外部 LLM/API 程序**
- **机械查找**（`glossary_lookup.py scan`）是**术语扫描流程的一部分**（非独立阶段）：字面精确匹配，把"已登记词确实出现在字幕里"找全（治漏翻），产出素材供 Agent/subagent 使用，不做任何理解/判定

## 子任务拆法（与 reflow-redstone 一致）

> **任务规则内联于任务文件**（本目录），主 SKILL 只留调度线；执行型全局纪律单一权威 = [subagent-dispatch/_discipline.md](../subagent-dispatch/_discipline.md)（渲染脚本自动追加），研究型纪律 = `term-researcher` agent 正文。

| 任务 | 任务文件 | 派发 | 产物（`_work/<视频名>/`） |
|------|----------|------|------|
| 第一次遍历（ASR 修正 + 游离单词归位） | `task-en-preprocess.md` | `render_preprocess_prompt.py task-en-preprocess` → 块级派发 | `_en_results/chunk_<k>.srt` + `chunk_<k>.asr.tsv` |
| 术语识别 | `task-term-recognition.md` | `render_preprocess_prompt.py task-term-recognition` → 块级派发 | `_term_results/chunk_<k>.txt` |
| L3 术语查证（§1.2） | `task-term-resolve.md` | **任务文件即完整 prompt**，双引用派发 `term-researcher` | `term_resolve.md` |

## ASR 语义解码（第一次遍历）

> subagent 侧任务规则/时间戳纪律/输出契约见 `task-en-preprocess.md`（注入素材：asr_fixes 全局+局部 + 领域术语集，由渲染脚本按任务注入）；主会话编排见 redstone-preprocess §1.1 步骤 2（分块 → 渲染 → 派发 → `srt_join_parts.py` 合并 → `srt_check_segments --cue-exact` → 汇总）。

- **ASR 分层登记**（subagent 只产出 `.asr.tsv` 清单，登记由主会话/确认后）：跨视频通用→全局表；视频专属→`_work/<视频名>/asr_fixes.md`（必要时入术语库）——规则见 [term-registration#ASR 映射登记](../term-registration/SKILL.md#asr-映射登记翻译工作流专用)

## 机械查找（补充机制，主会话跑）

命令见 redstone-preprocess §1.1 步骤 3；要点：

- 输出：`cue|时间戳|词|译名|来源|层级`
- `--categories`：**按文件名过滤 L2**（`.cache/glossary/<文件名>.csv`），由 Agent 按阶段〇**语义判断**给出（可跨多个分类），非机械单一输出
- **词汇表命名互不对应**：L2 文件名 / `glossary_categories.yaml` 分类 / L1 文件名 / L1.5 命名各一套（L1 始终全量；L1.5 默认不扫，需显式 `--levels L1,L1.5,L2`）
- 参数/格式细节以 `scripts/glossary_lookup.py` docstring 为准（唯一权威）

## 术语识别

> 任务规则见 `task-term-recognition.md`（命中项强制查词 / trap_words / ASR 推测 / 补变体 / 排误报 / L3 标记）；prompt 由 `render_preprocess_prompt.py task-term-recognition` 渲染（自动注入 scan 命中项按 OWNED cue 过滤 + 领域术语集 + ASR 修正映射），派发见 redstone-preprocess §1.1 步骤 4（先验知识注入顺序见 [subagent-dispatch#派发配方](../subagent-dispatch/SKILL.md#派发配方)）。

## 集中补齐（§1.2 查证）

> 待查 L3 术语译名查证**由 `term-researcher`（研究型 agent）单次派发**，**任务文件即完整 prompt**（`task-term-resolve.md`），派发时「任务文件 + term_pending.md」双引用（见 redstone-preprocess §1.2）——主会话只写待查列表 + 派发 + 读结果，**不读 wiki 页面全文**。查证链/抓取纪律见 [wiki-tools](../wiki-tools/SKILL.md)（权威）+ `task-term-resolve.md`；产物契约（`term_pending.md` / `term_resolve.md`）见 [PRODUCT_FORMATS](../../../docs/PRODUCT_FORMATS.md)。
