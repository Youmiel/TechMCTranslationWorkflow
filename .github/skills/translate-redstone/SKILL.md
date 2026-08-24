---
name: translate-redstone
description: 用于Minecraft红石技术视频字幕的精细翻译。每次处理一个视频，先扫描术语并补齐知识，翻译后进入人工审核循环。
---

# 红石技术字幕翻译官

> 定位：Minecraft 红石技术视频字幕的精细翻译——先扫描术语补齐知识，翻译后进入人工审核循环。

## 适用范围

- **一次一个视频**，精细翻译，不批量处理
- **纯文本翻译**，不依赖视频画面或音频（成本/渠道限制）
- 输入以 SRT 为主，YouTube transcript（无时间码纯文本）为次

## 输入 / 输出

### 工作目录

| 目录 | 角色 | 读写 |
|------|------|------|
| `_input/` | 待翻译字幕入口 | 只读输入 |
| `_output/` | 最终交付输出 | 写正式稿 |
| `_work/<视频名>/` | 中间产物 + 断点恢复 + 临时脚本 | 只读写**当前视频**子目录 |

> 工作区隔离（临时脚本禁写 `scripts/`、禁止参考其它视频等）见 [redstone-conventions#工作区隔离](../redstone-conventions/SKILL.md#工作区隔离)。

### 输入

用户将待翻译文件放入 `_input/`。Agent 自动检测：

| 格式 | 特征 | 处理方式 |
|------|------|----------|
| **SRT** | 有时间码，逐句分段 | 首选格式，保留时间码输出到 `_output/` |
| **YouTube transcript** | 无时间码，纯文本段落 | 先按句分割，输出到 `_output/` 不保留时间码 |

### 输出

翻译结果写入 `_output/`，文件名同输入。默认输出**双语对照**（原文 + 中文翻译），输出变体见 [redstone-conventions#语言顺序与输出变体](../redstone-conventions/SKILL.md#语言顺序与输出变体)（`bilingual` 默认 / `zh-only` / `annotated`）。

> 语言顺序固定 `en-zh`、脚本 `--order` 约定见 [redstone-conventions#语言顺序与输出变体](../redstone-conventions/SKILL.md#语言顺序与输出变体)。

### 中间产物与断点恢复

**全流程各阶段（子 skill）的输入与产物**：

1. **阶段〇 领域预判与准备**（`redstone-preprocess`）——加载领域知识/预判，无落盘产物
2. **阶段一 术语扫描与知识补齐**（`redstone-preprocess`）
   - 输入：`_input/` 原始字幕
   - 产物：
     - §1.1 术语扫描 → `<工作目录>/01_subtitle_asr_fixed.srt`
     - §1.3 术语确认 → `<工作目录>/02_terms.md`
   - **阶段门禁**：`01`/`02` 交用户确认，**确认后才进阶段二**（阶段间确认是本工作流的流程控制，Agent 不得擅自跨阶段）
3. **阶段二 正式翻译**（本工作流）
   - 输入：`01_subtitle_asr_fixed.srt` + `02_terms.md`
   - **执行一律 subagent**（块数由骨架决定，无需报告用/不用），块级产物 + 合并稿：
     - 分块 → `<工作目录>/chunks/`（01 `text_chunk.py --type srt` 分块骨架）
     - 合并断句 → `<工作目录>/_merge_results/chunk_<k>.txt` → `text_merge.py` 合并 → `<工作目录>/s03_plan.md`
     - 逐段翻译 → `<工作目录>/_trans_results/chunk_<k>.txt` → `text_merge.py` 合并 → `<工作目录>/s04_draft.srt`（标准 SRT 双语）
   - 校验（机械，硬闸门）：断句措辞一致性（`srt_check_plan_words.py`）/ 术语全量核对（`srt_check_terms.py`）/ 行宽（`srt_check_width.py` >26 打回）
4. **阶段二+ 去翻译腔**（`humanizer-zh`，可选）
   - 输入：`s04_draft.srt` 全稿
   - 产物：修订稿（回写 `s04`）
5. **阶段二½ 人工审核**（`redstone-review`）
   - 输入：待审方案 + 翻译结果（`s03` / `s04`）
   - 产物：用户确认（无新落盘）
6. **阶段三 数据源总结**（`redstone-finalize`）
   - 输入：确认后的完整成果
   - 产物：`.github/experience/` 追加（coverage_log / source_experience）

**中断恢复路由**：检查 `_work/<视频名>/` 最完整产物，**从产出该产物的阶段开头继续**（假设该阶段异常中断、产物可能不完整）：

1. 无任何产物 → 从头开始（阶段〇）
2. 仅 `01_subtitle_asr_fixed.srt` → 阶段一 §1.1 开头（重新第一次遍历，确保 01 完整；有 `_en_chunks/` + 部分 `_en_results/` → 步骤 2 补派缺失块后 `srt_join_parts.py` 合并）
3. 有 `02_terms.md` → 阶段一 §1.3 开头（重新术语确认；§1.4 入库照做）
4. 有 `chunks/`（01 分块骨架，无 `_merge_results/`）→ 阶段二 合并断句派发开头（逐块派发 `task-merge`）
5. 有 `_merge_results/` 部分 → 补派缺失断句块后 `text_merge.py` 合并 → `s03_plan.md`（断句措辞/时间校验通过后进翻译）
6. 有 `s03_plan.md`（无 `_trans_results/`）→ 阶段二 翻译派发开头（逐块派发 `task-translate`）
7. 有 `_trans_results/` 部分 → 断点续译（补派缺失翻译块后 `text_merge.py` 合并 → `s04_draft.srt`）
8. 有 `s04_draft.srt` → 阶段二½ 人工审核（或阶段二+ 去翻译腔）

> 各阶段结束**立即落盘**（conventions「断点恢复」）；中间产物是工作底稿，**禁止自动删除**（AGENTS.md #6），清理提示用户手动执行。

## 依赖（扩展 Skill 地图）

| 话题 | 权威 Skill |
|------|-----------|
| 通用规则（环境/工作区/分块/门禁等） | `redstone-conventions` |
| 翻译前置（阶段〇/一） | `redstone-preprocess` |
| 人工审核（阶段二½）+ 输出门禁 | `redstone-review` |
| 数据源总结（阶段三） | `redstone-finalize` |
| 断句/合并/行宽 | `segment-subtitles` |
| subagent 派发 | `subagent-dispatch` |
| 术语表加载/四级查找 | `use-glossary` |
| 术语扫描机制（ASR 解码/scan 覆盖网） | `term-scan` |
| 术语登记 | `term-registration` |
| CSV 读写/表头 | `csv-rules` |
| Wiki 抓取/兜底 | `wiki-tools` |
| 去翻译腔 | `humanizer-zh` |
| 知识/索引维护 | `maintain-knowledge` |

## 注意事项

### 通用规则

见 [redstone-conventions](../redstone-conventions/SKILL.md)（环境 / 工作区隔离 / 断点恢复 / en-zh / 时间纪律 / 长视频分块 / 输出门禁 / 禁删）+ [AGENTS.md](../../../AGENTS.md)（项目原则）。

### 特有规则

#### 时间戳
- 输出 SRT 的所有时间边界**必须 ⊆ 原字幕边界集合**（不允许新造时间点）——**本工作流特有**（reflow 允许预测点）
- **01 生成后立即校验时间轴对齐**：`python scripts/srt_check_segments.py 01_subtitle_asr_fixed.srt --orig <原始ASR.srt> --cue-exact`——01 只改文本、保留原时间码、不增删 cue；错位须在断句前发现（否则一路传 s03/s04，表现为"字幕比语音快/慢"）
- 合并/断句后每段时间码 = 覆盖原字幕片段**首段 start → 末段 end**；共享 cue 整条归属/中间断句估算见 [segment-subtitles#共享 cue 与整条归属（时间不重叠）](../segment-subtitles/SKILL.md#共享-cue与整条归属时间不重叠)
- （时间不重叠 + 每步即时校验为通用规则，见 conventions「时间纪律」）

#### 断句（合并与分割）

断句规则**全部见 [segment-subtitles](../segment-subtitles/SKILL.md)（权威）**——语义合并判据（不以标点为准）、英文预整理（游离单词归位）、两遍式、对白拆分、分割超长句、语义锚点、行宽，均以该 Skill 为准，本段不再重复。分块是通用机制，见 [redstone-conventions#长视频分块](../redstone-conventions/SKILL.md#长视频分块全流程通用机制)。

> **必须使用工具**：合并/断句一律按 [segment-subtitles](../segment-subtitles/SKILL.md) 执行；长视频（cue 数超出单次上下文）**必须先分块**（见 [redstone-conventions#长视频分块](../redstone-conventions/SKILL.md#长视频分块全流程通用机制)），禁止整条字幕一次性合并/翻译。


## 固定工作流指令

本工作流包含四个阶段 + 一个人工审核循环。

---

### 阶段〇：领域预判与准备（翻译前，轻量扫描）

按 [redstone-preprocess#阶段〇领域预判与准备](../redstone-preprocess/SKILL.md#阶段〇领域预判与准备) 原样执行（刷新缓存 / 类别预判 / 红石补充加载 / 知识地图 / SOURCE_COVERAGE / asr_fixes）。

---

### 阶段一：术语扫描与知识补齐

按 [redstone-preprocess#阶段一术语扫描与知识补齐](../redstone-preprocess/SKILL.md#阶段一术语扫描与知识补齐) 原样执行（§1.1 扫描 / §1.2 补齐 / §1.3 确认 / §1.4 入库），产物 `01_subtitle_asr_fixed.srt` + `02_terms.md` 见 [redstone-preprocess#产物契约](../redstone-preprocess/SKILL.md#产物契约本阶段落盘见各工作流目录约定)。

---

### 阶段二：正式翻译

> **执行一律 subagent（无需报告）**：合并断句 / 翻译**逐块派 subagent**（块数由分块骨架决定，无需报告“用/不用”）——统一路径，见 [subagent-dispatch#派发边界](../subagent-dispatch/SKILL.md#派发边界哪些派-subagent--哪些主会话)。主会话只做：分块 → 渲染 → 派发 → 合并 → 校验 → 定点修复派发。

**产物契约（本阶段输入 / 输出）**：
- 输入：`01_subtitle_asr_fixed.srt` + `02_terms.md`（preprocess 产物）
- 输出（块级 subagent 产物 + 合并稿）：
  - `chunks/`（01 分块骨架，从 01 `text_chunk.py --type srt` 分块）
  - `_merge_results/chunk_<k>.txt`（断句块）→ `text_merge.py` 合并 → `s03_plan.md`（断句定稿，交用户审核前落盘）
  - `_trans_results/chunk_<k>.txt`（翻译块）→ `text_merge.py` 合并 → `s04_draft.srt`（标准 SRT 双语 en-zh，逐段翻译落盘）
- 各产物结构/分隔符/标记约定（单一权威）见 [PRODUCT_FORMATS](../../../docs/PRODUCT_FORMATS.md)，处理前先查对应节

**翻译风格**：翻译前读 `ref_translations/` 参考译例（如有），模仿其**语气 / 句长偏好 / 术语偏好 / 注释风格**。

所有术语译名已就绪，零网络等待。**先定段落，再逐句翻译**。

#### 合并与断句（翻译前先定段落）

1. **分块**：`python scripts/text_chunk.py 01_subtitle_asr_fixed.srt --type srt --owned <N> --ctx <M> --out chunks/`（N 按 [redstone-conventions#长视频分块](../redstone-conventions/SKILL.md#长视频分块全流程通用机制) 用 `context_estimate.py` 定；N=1 单块亦分，产物契约一致）
2. **渲染**：`python scripts/render_subagent_prompt.py task-merge --video <工作目录> --all --chunks-dir <工作目录>/chunks`
3. **逐块派发** `task-merge`（断句 subagent；规则见 [segment-subtitles](../segment-subtitles/SKILL.md) 权威 + 任务文件 [task-merge.md](task-merge.md)）→ `_merge_results/chunk_<k>.txt`；每收一个 `已写入` 立即验证真实性（[subagent-dispatch#收信号即验](../subagent-dispatch/SKILL.md#收信号即验已写入-真实性门禁拦截假完成)）
4. **合并**：`python scripts/text_merge.py chunks/ _merge_results/ --out s03_plan.md [--report <报告>]`（异常只读报告，见 [subagent-dispatch#合并](../subagent-dispatch/SKILL.md#合并text_mergepy-全自动--异常清单替代主-agent-手工读头尾)）
5. **校验（硬闸门，全量）**：
   - 断句措辞一致性（断句只合并/分割、不改措辞）：`python scripts/srt_check_plan_words.py 01_subtitle_asr_fixed.srt s03_plan.md --asr-fixes 02_terms.md`
   - 时间边界：`python scripts/srt_check_segments.py s03_plan.md --orig 01_subtitle_asr_fixed.srt`
   - 打回 → B 档定点修复派发（见下「校验打回」）；**通过才进翻译**
6. **ASR 修正应用在组装期**：`02_terms.md` 已确认的 ASR 修正（如 word tear、the end dimension）在组装 `s03_plan.md` 时直接替换文本，勿留待翻译期
7. **分段方案先交用户审核**（阶段二½），确认后再定稿翻译

#### 正式翻译

1. **渲染**：`python scripts/render_subagent_prompt.py task-translate --skill translate-redstone --video <工作目录> --all --chunks-dir <工作目录>/chunks`
2. **逐块派发** `task-translate`（翻译 subagent，任务文件 [task-translate.md](task-translate.md)）→ `_trans_results/chunk_<k>.txt`
3. **合并**：`python scripts/text_merge.py chunks/ _trans_results/ --out <中间稿> [--report <报告>]` → 主会话转 `s04_draft.srt`（标准 SRT 双语 en-zh；**逐段落盘**，中断可从未完成段继续）
4. **校验（硬闸门，全量）**：
   - 术语全量核对：`python scripts/srt_check_terms.py 01_subtitle_asr_fixed.srt 02_terms.md <_trans_results/> --chunks <chunks/>`（分块时）或 `... s04_draft.srt --plan s03_plan.md`（合并后）
   - 行宽：`python scripts/srt_check_width.py s04_draft.srt --order en-zh`（>26 硬打回退出码 1、>22 软告警）
   - 时间边界：`python scripts/srt_check_segments.py s04_draft.srt --orig 01_subtitle_asr_fixed.srt`
5. **校验打回 → 定点修复（B 档）**：收集**全部错误清单**一次派发 `task-fix`（[task-fix.md](task-fix.md)，见 [subagent-dispatch#定点修正](../subagent-dispatch/SKILL.md#定点修正surgical-fix校验打回先小规模修不整块重派)）——断句措辞按 01 改回、译文改措辞/术语漂移/行宽（**translate 修复就是改译文本身**，无 reflow「r03 只许切不许译」约束）；修正后复验（重跑触发它的校验），仍有残留 → 第二轮只派增量清单；多轮仍失败 → C 档整块重派（mv 清理 + 重派）

#### 输出约束（审核口径，与 [task-translate.md](task-translate.md) 任务规则同源，不重复定义）

- 禁止直译红石术语（Comparator 必须为“比较器”）；禁止使用未在阶段一确认的译名
- 结论附上来源（`knowledge/` 或 `.cache/` 中的引用路径）

---

### 阶段二+：去翻译腔（可选，独立上下文）

初步翻译完成后，消除译文中的“翻译腔”和 AI 味——规则见 [humanizer-zh](../humanizer-zh/SKILL.md)（24 种 AI 写作模式 + 改写原则）。**仅当用户明确要求“去除翻译腔”或译文 AI 味明显时才执行；字幕本身偏口语时可跳过。**

> **独立上下文执行**（原隐含在主会话顺带做，现按 `docs/PIPELINE_ISOLATION.md` 隔离）：本步骤作为**独立一遍**运行——只读 `s04_draft.srt` 全稿，独立窗口产出修订稿，不在翻译会话里顺带改。全稿超长时可先分块、各块独立跑（块间用同一规则模板约束，保持风格一致）。

- **整稿（不分块）**：主会话独立一遍，按 `humanizer-zh` 规则扫描修订，回写 `s04_draft.srt`
- **长稿分块**：先把 `s04_draft.srt` 按段分块到 `_work/<视频名>/_humanize_chunks/`（每块含该块译文段），再逐块派 subagent——`python scripts/render_subagent_prompt.py task-humanize --video <工作目录> --all --chunks-dir <工作目录>/_humanize_chunks`，任务文件 [task-humanize.md](task-humanize.md)（字幕场景去翻译腔规则 / 改写原则的 subagent 版，**主 skill 不重复**）；结果写 `_work/<视频名>/_humanize_results/chunk_<k>.txt`：每行 `段号|修订后译文`（可附改动点说明）

---

### 阶段二½：人工审核循环

按 [redstone-review](../redstone-review/SKILL.md) 执行（循环机制 + 输出门禁）。**审核对象：分段方案 + 翻译结果**（`s03_plan.md` + `s04_draft.srt`）。

---

### 阶段三：数据源效果总结

按 [redstone-finalize](../redstone-finalize/SKILL.md) 原样执行（coverage_log 流水 + source_experience 经验提炼）。
