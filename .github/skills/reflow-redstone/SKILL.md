---
name: reflow-redstone
description: Minecraft 红石技术视频字幕的语义回填（reflow）工作流——以原字幕时间轴为骨架，合并全文补标点、整段翻译、分句建立"整句↔译文单元"、脚本化回填重排时间轴。共享 translate-redstone 的阶段〇/一（redstone-preprocess）、审核（redstone-review）、收尾（redstone-finalize），核心差异在阶段二。
---

# 红石字幕语义回填（reflow-redstone）

> 定位：以原字幕时间轴为骨架的**语义回填**（reflow）——合并全文补标点、整段翻译、翻译后分句建立"整句 ↔ 译文单元"、**脚本化回填重排时间轴**（碎片合并 / 整句锚定 / 单元级分配 / 预测切分点）。与 translate 的区别在阶段二；阶段〇/一/二½/三 共享。

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

- `<工作目录>/../_output/<文件名>.reflow.srt`，默认双语 en-zh（英文行 = 分句原文，中文行 = 对应译文），时间轴 = 以原轴为基础局部合并/切分
- 输出变体（`bilingual` 默认 / `zh-only` / `annotated`）见 [redstone-conventions#语言顺序与输出变体](../redstone-conventions/SKILL.md#语言顺序与输出变体)

### 中间产物与断点恢复

**全流程各阶段（子 skill）的输入与产物**：

1. **阶段〇/一 领域预判与术语补齐**（`redstone-preprocess`）——输入 `_input/` 原始字幕 → 产物 `<工作目录>/01_subtitle_asr_fixed.srt`、`<工作目录>/02_terms.md`
2. **阶段二 语义回填**（本工作流，产物在 `<工作目录>/reflow/`）
   - 输入：`01` + `02`
   - **`context_estimate.py` 只定 `--owned`（每块 cue 数）；执行一律 subagent**（块数由空隙组 × 组内分片决定，见 conventions「长视频分块」）。产物统一块级，按序：
     - 步骤 1 空隙探测 + 硬性断句 → `r00_gaps.md`、`r01_breaks.md`
     - 步骤 2 确定块大小 + 分块 → `chunks/`（从 01 `--gaps` 分块：空隙点强制切块，块数下限 = 空隙点数+1）
     - 步骤 3 归一化 → `r01_normalized/chunk_<k>.txt`
     - 步骤 3 处理（补标点）→ `r01_results/chunk_<k>.txt`
     - 步骤 4 处理（翻译 + 术语核对）→ `r02_results/chunk_<k>.txt`
     - 步骤 5 归一化（预分句 + ZH 机械化断句）→ `r03_normalized_1/chunk_<k>.txt`（EN 预分句 E 号）+ `r03_normalized_2/chunk_<k>.txt`（ZH r03 模板骨架：Z 句 + 子句段预填）
     - 步骤 5 处理（分句，5-1/5-2 二选一）→ **5-1 LLM 语义分句**（老，现状）：`task-split` 直接写；**5-2 脚本断句**（新，省 token）：`r03_matches/chunk_<k>.txt`（匹配文件，LLM 只做句子匹配）→ `build-r03` 机械填回——两路径产物 `r03_results/chunk_<k>.txt`（S 号块内从 1 连续编号；**回填输入 = 目录直读**，`parse_r03_dir` 按块序解析 + 全局重编号，零拼接）——`r03_plan.md` 仅审核/审计时 `join-r03` 按需生成
     - 步骤 6 处理（回填）→ `r04_draft.srt`（预览，止步 `_work/`）、`r03_anchored.jsonl`（锚定明细，JSONL 每行一整句：锚定状态 + 单元 cue 命中）
     - 步骤 7 处理（组装）→ `r04_bilingual.srt`（双语预览 en-zh）

> **产物格式/分隔符/标记约定（单一权威）**：各产物结构（r00–r04、r03_anchored.jsonl）见 [PRODUCT_FORMATS](../../../docs/PRODUCT_FORMATS.md)——处理前先查对应节，勿现查代码猜格式；块间分隔一律空行、手写标记仅限跨块句补全的 `【承接句】`/`【延伸句】`（`【强制断句】` 为空隙标记、非产物文本，经复核注入补标点先验知识）。
3. **阶段二½ 人工审核**（`redstone-review`）——输入 `r03` + `r04` → 用户确认（无新落盘）
4. **阶段三 数据源总结**（`redstone-finalize`）——`.github/experience/` 追加

**中断恢复路由**：检查 `_work/<视频名>/` 最完整产物，**从产出该产物的阶段/步骤开头继续**（假设该阶段异常中断、产物可能不完整）：

1. 无任何产物 → 从头开始（阶段〇）
2. 仅 `01_subtitle_asr_fixed.srt` → preprocess §1.1 开头（有 `_en_chunks/` + 部分 `_en_results/` → §1.1 步骤 2 补派缺失块后 `srt_join_parts.py` 合并）
3. 有 `02_terms.md` → preprocess §1.3 开头（§1.4 入库照做）
4. 有 `r00_gaps.md`/`r01_breaks.md`（断句骨架）→ 步骤 2 开头（从确定块大小 + 分块续）
5. 有 `reflow/chunks/`（01 分块骨架）→ 步骤 3 归一化（跑 `srt_reflow_normalize.py` → `r01_normalized/`）
6. 有 `reflow/r01_normalized/`（归一化输入）→ 步骤 3 逐块补标点续
7. 有 `reflow/r01_results/`（逐块中间产物）→ 步骤 3 校验（从补标点校验续）
8. 有 `reflow/r02_results/`（逐块中间产物）→ 步骤 4 第 1 步（从逐块翻译续）
9. 有 `reflow/r03_normalized_1/` + `reflow/r03_normalized_2/`（EN 预分句 + ZH r03 模板骨架）→ 步骤 5（归一化已完成，从 5-1 / 5-2 选择续）
9.5. 有 `reflow/r03_matches/`（匹配文件，5-2）→ 步骤 5-2 步骤 2（从 `build-r03` 机械填回续）
10. 有 `reflow/r03_results/`（逐块中间产物）→ 步骤 5-1 第 1 步（从分句续；5-2 产物亦可直接回填；回填直读 r03_results/，无需拼接）
11. 有 `r03_plan.md`（仅审核/审计产物，非回填输入）→ 不设独立恢复点，回填以 r03_results/ 为准
12. 有 `r04_draft.srt` → 步骤 6 开头（重新回填）

> 各阶段结束**立即落盘**（conventions「断点恢复」）；中间产物是工作底稿，**禁止自动删除**（AGENTS.md #6）。

## 依赖

| 话题 | 权威 Skill |
|------|-----------|
| 通用规则（环境/工作区/分块/门禁等） | `redstone-conventions` |
| 翻译前置（阶段〇/一） | `redstone-preprocess` |
| 人工审核（阶段二½）+ 输出门禁 | `redstone-review` |
| 数据源总结（阶段三） | `redstone-finalize` |
| 去翻译腔 | `humanizer-zh` |
| 行宽/时间不重叠机制（同源出处声明，规则已内联语义回填文件，不加载） | `segment-subtitles` |
| subagent 派发（派发配方/纪律母版/任务导航） | `subagent-dispatch` |

## 注意事项

### 通用规则

见 [redstone-conventions](../redstone-conventions/SKILL.md) + [AGENTS.md](../../../AGENTS.md)（项目原则）。

### 特有规则

- **输出门禁**：`_output/` 只收阶段二½ 用户确认后的正式稿（见 `redstone-review`）
- **定点修复（校验打回统一处置）**：硬违规先定点修正（`task-fix` 整批派发，见 [subagent-dispatch#定点修正](../subagent-dispatch/SKILL.md#定点修正surgical-fix校验打回先小规模修不整块重派)）；多轮尝试或违规严重、定点修不了才打回「处理」重跑（重跑前先 mv 清理已存在结果）；勿在主会话进行全量校对

## 固定工作流指令

本工作流四个阶段 + 一个人工审核循环。

---

### 阶段〇 / 阶段一：领域预判 + 术语补齐

按 [redstone-preprocess](../redstone-preprocess/SKILL.md) 原样执行（阶段〇 预判 / §1.1 扫描 → `01_subtitle_asr_fixed.srt` / §1.2 补齐 / §1.3 确认 → `02_terms.md` / §1.4 入库）。`--cue-exact` 校验保留（保护原轴骨架）。**阶段门禁：`01`/`02` 交用户确认后才进入阶段二，不得擅自跨阶段**（阶段间确认是本工作流的流程控制）。

> **实践建议**（补丁，机制设计不变）：阶段〇/一 分块（preprocess §1.1 第一次遍历 `_en_chunks/`）`--owned` 按 **≤300 cue** 封顶——实践得出；封顶只在取值时做，`context_estimate.py --no-amplification` 定 N 与分块机制不变

---

### 阶段二：语义回填

> 语义工作（合并补标点 / 翻译 / 分句对应 / 回填判断）由 Agent 承担；确定性时间运算由 `scripts/srt_reflow*.py` 承担。**进入本阶段时加载 [semantic-reflow.md](semantic-reflow.md) 执行**——步骤 1-7 完整指令（空隙探测 → 分块 → 补标点 → 翻译 → 分句 → 回填 → 组装，各步按「归一化 → 处理 → 校验」三段组织，含派发边界 / 执行型纪律 / 行文结构）。

- 本阶段产物链（`r00_gaps.md` → `chunks/` → `r01_normalized/` → `r01_results/` → `r02_results/` → `r03_normalized_1/2` → `r03_results/` → `r04_draft.srt` → `r04_bilingual.srt`）与中断恢复路由见上方「中间产物与断点恢复」+ [PRODUCT_FORMATS](../../../docs/PRODUCT_FORMATS.md)
- **步骤 5 路径选择（必须询问用户，不得默认）**：5-1 LLM 语义分句 / 5-2 脚本断句——差异与执行见 semantic-reflow.md

---

### 阶段二½：人工审核循环

按 [redstone-review](../redstone-review/SKILL.md) 执行（循环机制 + 输出门禁）。**审核对象：回填方案 + 最终 SRT**（r03 = `r03_results/` 目录直读，或 `join-r03` 生成的 `r03_plan.md` 完整稿 + `r04_draft.srt`），重点核对语义对应是否判对（拆/合关系、切分位置）。**审核中发现 AI 味 / 翻译腔 → 回 r02 改整句、r03 同步**（受忠实铁律约束，不得在 r04 单侧改写），红石术语译名不受影响。

### 阶段三：数据源效果总结

按 [redstone-finalize](../redstone-finalize/SKILL.md) 原样执行（coverage_log 流水 + source_experience 经验提炼）。
