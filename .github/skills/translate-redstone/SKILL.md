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

翻译结果写入 `_output/`，文件名同输入。默认输出**双语对照**（原文 + 中文翻译），用户可要求以下变体：

| 选项 | 说明 |
|------|------|
| `bilingual`（默认） | 英文行在前、中文行在后（en-zh），保留时间码 |
| `zh-only` | 仅中文，保留时间码 |
| `annotated` | 双语 + 术语来源注释 |

> 语言顺序固定 `en-zh`、脚本 `--order` 约定见 [redstone-conventions#语言顺序](../redstone-conventions/SKILL.md#语言顺序)。

### 中间产物与断点恢复

**全流程各阶段（子 skill）的输入与产物**：

1. **阶段〇 领域预判与准备**（`redstone-preprocess`）——加载领域知识/预判，无落盘产物
2. **阶段一 术语扫描与知识补齐**（`redstone-preprocess`）
   - 输入：`_input/` 原始字幕
   - 产物：
     - §1.1 术语扫描 → `<工作目录>/01_subtitle_asr_fixed.srt`
     - §1.3 术语确认 → `<工作目录>/02_terms.md`
3. **阶段二 正式翻译**（本工作流）
   - 输入：`01_subtitle_asr_fixed.srt` + `02_terms.md`
   - 产物：
     - 合并断句 → `<工作目录>/s03_segments.md`
     - 逐段翻译 → `<工作目录>/s04_translation_draft.srt`
4. **阶段二+ 去翻译腔**（`humanizer-zh`，可选）
   - 输入：`s04_translation_draft.srt` 全稿
   - 产物：修订稿（回写 `s04`）
5. **阶段二½ 人工审核**（`redstone-review`）
   - 输入：待审方案 + 翻译结果（`s03` / `s04`）
   - 产物：用户确认（无新落盘）
6. **阶段三 数据源总结**（`redstone-finalize`）
   - 输入：确认后的完整成果
   - 产物：`.github/experience/` 追加（coverage_log / source_experience）

**中断恢复路由**：检查 `_work/<视频名>/` 最完整产物，**从产出该产物的阶段开头继续**（假设该阶段异常中断、产物可能不完整）：

1. 无任何产物 → 从头开始（阶段〇）
2. 仅 `01_subtitle_asr_fixed.srt` → 阶段一 §1.1 开头（重新第一次遍历，确保 01 完整）
3. 有 `02_terms.md` → 阶段一 §1.3 开头（重新术语确认；§1.4 入库照做）
4. 有 `s03_segments.md`（无草稿）→ 阶段二 合并断句开头（重新断句）
5. 有 `s04_translation_draft.srt` → 阶段二 逐段翻译开头（断点续译：确认已译段、补译未译段）

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

见 [redstone-conventions](../redstone-conventions/SKILL.md)（环境 / 工作区隔离 / 断点恢复 / en-zh / 时间纪律 / 长视频分块 / 输出门禁 / 禁删）+ [AGENTS.md](../../AGENTS.md)（项目原则）。

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

**产物契约（本阶段输入 / 输出）**：
- 输入：`01_subtitle_asr_fixed.srt` + `02_terms.md`（preprocess 产物）
- 输出：`s03_segments.md`（断句定稿，交用户审核前落盘）、`s04_translation_draft.srt`（逐段翻译落盘，中断从未完成段继续）

**翻译风格**：翻译前读 `ref_translations/` 参考译例（如有），模仿其**语气 / 句长偏好 / 术语偏好 / 注释风格**。

所有术语译名已就绪，零网络等待。**先定段落，再逐句翻译**。

#### 合并与断句（翻译前先定段落）
- 合并/断句规则 -> [segment-subtitles#工作流程](../segment-subtitles/SKILL.md#工作流程处理顺序)，按数字步骤执行：
  1. 英文预整理（游离单词归位）-> [segment-subtitles#英文预整理](../segment-subtitles/SKILL.md#英文预整理游离单词归位)
  2. 第 1 遍英文侧初步分组 -> [segment-subtitles#合并判据](../segment-subtitles/SKILL.md#合并判据语义完整性不以标点为准)
  3. 第 2 遍中文侧最终定段 -> [segment-subtitles#分割超长句](../segment-subtitles/SKILL.md#分割超长句)
- **落盘**：断句定稿后写 `s03_segments.md` 再交用户审核（本阶段产物契约，见上方）
- **ASR 修正应用在组装期**：`02_terms.md` 已确认的 ASR 修正（如 word tear、the end dimension）在组装 `s03_segments.md` 时直接替换文本，勿留待翻译期
- **分段方案先交用户审核**（阶段二½），确认后再定稿翻译

#### 正式翻译
- 严格使用阶段一确认的译名；`[待审核]` 术语用**候选译名**并保留 `[待审核]` 标记（供用户复核）
- 默认输出双语对照格式
- **逐段落盘**：每译完一段立即追加到 `s04_translation_draft.srt`（本阶段产物契约，见上方），中断后可从未完成段继续

#### 输出约束
- 禁止直译红石术语（Comparator 必须为"比较器"）
- 禁止使用未在阶段一确认的译名
- 结论附上来源（`knowledge/` 或 `.cache/` 中的引用路径）

---

### 阶段二+：去翻译腔（可选，独立上下文）

初步翻译完成后，用 [humanizer-zh](../humanizer-zh/SKILL.md) 检查并消除译文中的"翻译腔"和 AI 味。

> **独立上下文执行**（原隐含在主会话顺带做，现按 `docs/PIPELINE_ISOLATION.md` 隔离）：本步骤作为**独立一遍**运行——只读 `s04_translation_draft.srt` 全稿 + `humanizer-zh` 规则，独立窗口产出修订稿，不在翻译会话里顺带改。全稿超长时可先分块、各块独立跑（块间用同一规则模板约束，保持风格一致）。

1. 加载 `humanizer-zh` Skill（`.github/skills/humanizer-zh/SKILL.md`），按其 24 种 AI 写作模式清单扫描译文
2. 重点关注字幕场景常见的：
   - **AI 词汇**：此外、至关重要、深入探讨、增强等
   - **三段式法则**："无缝、直观、强大"类堆叠
   - **否定式排比**："不仅是……更是……"
   - **系动词回避 / 刻意换词**
   - **通用积极结论**：空洞的收尾句
3. 改写原则：**保留字幕口语感和节奏**，不过度书面化；红石术语译名不受影响
4. 仅当用户明确要求"去除翻译腔"或译文 AI 味明显时才执行；字幕本身偏口语时可跳过

---

### 阶段二½：人工审核循环

按 [redstone-review](../redstone-review/SKILL.md) 执行（循环机制 + 输出门禁）。**审核对象：分段方案 + 翻译结果**（`s03_segments.md` + `s04_translation_draft.srt`）。

---

### 阶段三：数据源效果总结

按 [redstone-finalize](../redstone-finalize/SKILL.md) 原样执行（coverage_log 流水 + source_experience 经验提炼）。

## Wiki 抓取与兜底

Wiki 页面获取降级链、缓存保真阶梯、缓存读取、抓取注意事项、社区资料检索**全部见 [wiki-tools](../wiki-tools/SKILL.md)（权威）**；缓存文件格式见 `docs/WIKI_CACHE_FORMAT.md`。MCP 配置见 `.vscode/mcp.json`，部署见 `docs/MCP_DEPLOYMENT.md`。
