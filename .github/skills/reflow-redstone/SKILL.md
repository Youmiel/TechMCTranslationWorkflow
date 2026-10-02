---
name: reflow-redstone
description: Minecraft 红石技术视频字幕的语义回填（reflow）工作流——以原字幕时间轴为骨架，合并全文补标点、整段翻译、分句建立"整句↔译文单元"、脚本化回填重排时间轴。共享 translate-redstone 的阶段〇–阶段二（redstone-preprocess）、审核（redstone-review）、收尾（redstone-finalize），核心差异在阶段三。
---

# 红石字幕语义回填（reflow-redstone）

> 定位：以原字幕时间轴为骨架的**语义回填**（reflow）——合并全文补标点、整段翻译、翻译后分句建立"整句 ↔ 译文单元"、**脚本化回填重排时间轴**（碎片合并 / 整句锚定 / 单元级分配 / 预测切分点）。与 translate 的区别在阶段三；阶段〇–阶段二、阶段五–阶段六 共享。

## 适用范围

- **一次一个视频**，精细处理，不批量
- **输入无关**：优质人工字幕 / ASR 碎片字幕统一处理（不做质量判定、不分支）——两条路径由同一"合并补标点 → 分句对应 → 回填"机制覆盖
- **阅读舒适优先**：单条字幕以"读得舒服"为准（≤22 字、语义完整、节奏自然）；原轴只是时间骨架 + 真实 cue 边界参考，不因"尊重原轴"保留超长句
- 不检测 / 不处理"ASR 相对音频的时间偏移"（需画面/音频，超出纯文本范围）
- 纯文本翻译，不依赖视频画面/音频

## 输入 / 输出

### 工作目录

| 目录 | 角色 | 读写 |
|------|------|------|
| `_input/` | 待处理字幕入口 | 只读输入 |
| `_output/` | 最终交付输出 | 写正式稿 |
| `_work/<视频名>/` | 中间产物 + 断点恢复 + 临时脚本 | 只读写**当前视频**子目录 |

> 工作区隔离（临时脚本禁写 `scripts/`、禁止参考其它视频等）见 [redstone-conventions#工作区隔离](../redstone-conventions/SKILL.md#工作区隔离)。

### 输入

- `<工作目录>/../_input/<文件名>.srt`（带时间码）——必须有原轴可回填
- YouTube transcript（无时间码）**不适用**本工作流，走 translate

### 输出

- `<工作目录>/../_output/<文件名>.reflow.srt`，默认双语 zh-en（中文行 = 对应译文，英文行 = 分句原文），时间轴 = 以原轴为基础局部合并/切分
- 输出变体（`bilingual` 默认 / `zh-only` / `annotated`）见 [redstone-conventions#语言顺序与输出变体](../redstone-conventions/SKILL.md#语言顺序与输出变体)

### 中间产物与断点恢复

**全流程各阶段（子 skill）的输入与产物**：

1. **阶段〇 字幕机械修复**（`redstone-preprocess`）——纯脚本、零知识 → `<工作目录>/00_subtitle_snapped.srt`（时间轴新基准）
2. **阶段一 领域预判与准备 + 阶段二 术语补齐**（`redstone-preprocess`）——输入 `<工作目录>/00_subtitle_snapped.srt` → 产物 `<工作目录>/01_subtitle_asr_fixed.srt`、`<工作目录>/02_terms.md`
3. **阶段三 语义回填**（本工作流，产物在 `<工作目录>/reflow/`）
   - 输入：`01` + `02`
   - **`context_estimate.py` 只定 `--owned`（每块 cue 数）；执行一律 subagent**（块数由空隙组 × 组内分片决定，见 「redstone-conventions#长视频分块」）。产物统一块级，按角色名序：
     - 空隙探测 + 硬性断句 → `r00_gaps.md`（人读报告）、`r00_gaps_active.tsv`（生效空隙点集）、`r01_breaks.md`
     - 分块 → `chunks/`（从 01 `--gaps-file` 分块：生效空隙点强制切块，块数下限 = 生效空隙点数+1）
     - 补标点：归一化 → `r01_normalized/chunk_<k>.txt`；处理 → `r01_results/chunk_<k>.txt`
     - 翻译 + 术语核对 → `r02_results/chunk_<k>.txt`
   - 分句（预分句 + ZH 机械化断句）→ 三个产物：
     - `r03_normalized_1/chunk_<k>.txt`（EN 预分句 E 号）
     - `r03_normalized_2/chunk_<k>.txt`（ZH r03 模板骨架：Z 句 + 子句段预填）
     - `r03_zslim/chunk_<k>.txt`（**独立产物**：ZH 整句级精简列表，`--zh-list-out` 生成，仅句子匹配输入，见 PRODUCT_FORMATS_REFLOW）
   - 分句处理（[语义分句（LLM）](semantic-reflow.md#语义分句) / [脚本断句（机械）](semantic-reflow.md#脚本断句) 二选一）：
     - **语义分句（LLM，老，现状）**：`task-split` 直接写
     - **脚本断句（机械，新，省 token）**：`r03_matches/chunk_<k>.txt`（匹配文件，LLM 只做句子匹配），`build-r03` 机械填回
     - 两路径产物均为 `r03_results/chunk_<k>.txt`（S 号块内从 1 连续编号；**回填输入 = 目录直读**，`parse_r03_dir` 按块序解析 + 全局重编号，零拼接）
     - `r03_plan.md` 仅审核 / 审计时 `join-r03` 按需生成
   - 回填 → `r04_draft.srt`（预览，止步 `_work/`）、`r03_anchored.jsonl`（锚定明细，JSONL 每行一整句：锚定状态 + 单元 cue 命中）
   - 组装 → `r04_bilingual.srt`（双语预览 zh-en）

> **产物格式 / 分隔符 / 标记约定（单一权威）**：各产物结构（r00–r04、r03_anchored.jsonl）见 [PRODUCT_FORMATS_REFLOW](../../../docs/PRODUCT_FORMATS_REFLOW.md)——处理前先查对应节，勿现查代码猜格式。
> - 块间分隔一律空行
> - 手写标记仅限跨块句补全的 `【承接句】` / `【延伸句】`
> - `【强制断句】` 为空隙标记、非产物文本，经复核注入补标点先验知识
3. **阶段五 人工审核**（`redstone-review`）——输入 `r03` + `r04` → 用户确认（无新落盘）
4. **阶段六 数据源总结**（`redstone-finalize`）——`.github/experience/` 追加

**中断恢复路由**：检查 `_work/<视频名>/` 最完整产物，**从产出该产物的阶段/角色名继续**（假设该阶段异常中断、产物可能不完整）：

- 无任何产物 → 从头开始（[阶段〇](../redstone-preprocess/SKILL.md#阶段〇字幕机械修复)）
- 仅 `01_subtitle_asr_fixed.srt` → [阶段二术语扫描](../redstone-preprocess/SKILL.md#21-术语扫描) 开头
  - 有 `_en_chunks/` + 部分 `_en_results/` → 补派缺失块，`srt_join_parts.py` 合并
- 有 `02_terms.md` → [阶段二术语确认](../redstone-preprocess/SKILL.md#23-术语确认) 开头（[术语入库](../redstone-preprocess/SKILL.md#24-术语入库) 照做）
- 有 `r00_gaps.md`/`r01_breaks.md`（断句骨架）→ 分块 开头（从确定块大小 + 分块续）
- 有 `reflow/chunks/`（01 分块骨架）→ 补标点 归一化（跑 `srt_reflow_normalize.py` → `r01_normalized/`）
- 有 `reflow/r01_normalized/`（归一化输入）→ 补标点 逐块续
- 有 `reflow/r01_results/`（逐块中间产物）→ 补标点 校验续
- 有 `reflow/r02_results/`（逐块中间产物）→ 翻译 开头（从逐块翻译续）
- 有 `reflow/r03_normalized_1/` + `reflow/r03_normalized_2/`（EN 预分句 + ZH r03 模板骨架）→ 分句（归一化已完成，从两种路径选择续）
- 有 `reflow/r03_matches/`（匹配文件，脚本断句路径）→ [脚本断句（机械）](semantic-reflow.md#脚本断句) 的机械填回续
- 有 `reflow/r03_results/`（逐块中间产物）→ [语义分句（LLM）](semantic-reflow.md#语义分句) 开头（从分句续；脚本断句产物亦可直接回填；回填直读 r03_results/，无需拼接）
- 有 `r03_plan.md`（仅审核/审计产物，非回填输入）→ 不设独立恢复点，回填以 r03_results/ 为准
- 有 `r04_draft.srt` → 回填 开头（重新回填）

> 各阶段结束**立即落盘**（「redstone-conventions#断点恢复」）；中间产物是工作底稿，**禁止自动删除**（AGENTS.md #6）。

## 依赖

| 话题 | 权威 Skill |
|------|-----------|
| 通用规则（环境/工作区/分块/门禁等） | `redstone-conventions` |
| 翻译前置（阶段〇–阶段二） | `redstone-preprocess` |
| 人工审核（阶段五）+ 输出门禁 | `redstone-review` |
| 数据源总结（阶段六） | `redstone-finalize` |
| Wiki 抓取/兜底/按需刷新 | `wiki-tools` |
| 去翻译腔 | `humanizer-zh` |
| 行宽/时间不重叠机制（同源出处声明，规则已内联语义回填文件，不加载） | `segment-subtitles` |
| subagent 派发（派发配方/纪律母版/任务导航） | `subagent-dispatch` |

## 注意事项

### 通用规则

见 [redstone-conventions](../redstone-conventions/SKILL.md) + [AGENTS.md](../../../AGENTS.md)（项目原则）。

### 特有规则

- **输出门禁**：`_output/` 只收阶段五 用户确认后的正式稿（见 `redstone-review`）
- **定点修复（校验打回统一处置）**：硬违规先定点修正（`task-fix` 整批派发，见 [subagent-dispatch#定点修正](../subagent-dispatch/SKILL.md#定点修正校验打回先小规模修不整块重派)）；多轮尝试或违规严重、定点修不了才打回「semantic-reflow.md#处理」重跑（重跑前先 mv 清理已存在结果）；勿在主会话进行全量校对

## 固定工作流指令

本工作流包含阶段〇–阶段三、阶段五–阶段六（**无阶段四**——去翻译腔不适用本工作流）+ 一个人工审核循环。

---

### 阶段〇：字幕机械修复

按 [redstone-preprocess#阶段〇字幕机械修复](../redstone-preprocess/SKILL.md#阶段〇字幕机械修复) 原样执行（结构清理 + 时间轴吸附 → `00_subtitle_snapped.srt`）。

### 阶段一：领域预判与准备

按 [redstone-preprocess#阶段一领域预判与准备](../redstone-preprocess/SKILL.md#阶段一领域预判与准备) 原样执行。

### 阶段二：术语扫描与知识补齐

按 [redstone-preprocess#阶段二术语扫描与知识补齐](../redstone-preprocess/SKILL.md#阶段二术语扫描与知识补齐) 原样执行（[术语扫描](../redstone-preprocess/SKILL.md#21-术语扫描) → `01_subtitle_asr_fixed.srt` / [集中补齐](../redstone-preprocess/SKILL.md#22-集中补齐) / [术语确认](../redstone-preprocess/SKILL.md#23-术语确认) → `02_terms.md` / [术语入库](../redstone-preprocess/SKILL.md#24-术语入库)）。`--cue-exact` 校验保留（基准 = `00_subtitle_snapped.srt`）。**阶段门禁：`01`/`02` 交用户确认后才进入阶段三，不得擅自跨阶段**（阶段间确认是本工作流的流程控制）。

> **实践建议**（补丁，机制设计不变）：阶段二 分块（[术语扫描](../redstone-preprocess/SKILL.md#21-术语扫描) 第一次遍历 `_en_chunks/`）`--owned` 按 **≤300 cue** 封顶——实践得出；封顶只在取值时做，`context_estimate.py --no-amplification` 定 N 与分块机制不变

---

### 阶段三：语义回填

> 语义工作（合并补标点 / 翻译 / 分句对应 / 回填判断）由 Agent 承担；确定性时间运算由 `scripts/srt_reflow*.py` 承担。
>
> **进入本阶段时加载 [semantic-reflow.md](semantic-reflow.md) 执行**——完整指令按主 skill 的角色名逐序组织（各角色按“归一化 → 处理 → 校验”三段组织，含派发边界 / 执行型纪律 / 行文结构）：
> - 空隙探测
> - 分块
> - 补标点
> - 翻译
> - 分句
> - 回填
> - 组装

- 本阶段产物链与中断恢复路由见上方「中间产物与断点恢复」+ [PRODUCT_FORMATS_REFLOW](../../../docs/PRODUCT_FORMATS_REFLOW.md)。产物顺序：
  1. `r00_gaps.md`
  2. `chunks/`
  3. `r01_normalized/`
  4. `r01_results/`
  5. `r02_results/`
  6. `r03_normalized_1/2`
  7. `r03_results/`
  8. `r04_draft.srt`
  9. `r04_bilingual.srt`
- **分句路径选择（必须询问用户，不得默认）**：[语义分句（LLM）](semantic-reflow.md#语义分句) / [脚本断句（机械）](semantic-reflow.md#脚本断句)——差异与执行见 semantic-reflow.md

---

### 阶段五：人工审核循环

按 [redstone-review](../redstone-review/SKILL.md) 执行（循环机制 + 输出门禁）。

- **审核对象：回填方案 + 最终 SRT**
  - r03 = `r03_results/` 目录直读，或 `join-r03` 生成的 `r03_plan.md` 完整稿
  - `r04_draft.srt`
- **重点核对语义对应是否判对**（拆 / 合关系、切分位置）
- **审核中发现 AI 味 / 翻译腔 → 回 r02 改整句、r03 同步**（受忠实铁律约束，不得在 r04 单侧改写）；红石术语译名不受影响

### 阶段六：数据源效果总结

按 [redstone-finalize](../redstone-finalize/SKILL.md) 原样执行（coverage_log 流水 + source_experience 经验提炼）。
