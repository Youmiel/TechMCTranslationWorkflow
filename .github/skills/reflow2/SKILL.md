---
name: reflow2
description: Minecraft 红石技术视频字幕的「时间轴源头固化」工作流——英文句时间在源头脚本固化（en_timeline 只读真值锚），整段翻译不吃时间，翻译后中文句通过对齐继承英文固化时间。与 reflow-redstone 的区别在时间轴重建机制；共享阶段〇/一（redstone-preprocess）、审核（redstone-review）、收尾（redstone-finalize）。
---

# 红石字幕时间轴源头固化（reflow2）

> 定位：以原字幕时间轴为骨架的**源头固化**工作流——英文句（E）时间在源头由脚本精确固化（char→cue 映射，en_timeline 只读真值锚），整段自由翻译完全不吃时间（保留 reflow 的质量/token 优势），翻译后中文句（Z）通过纯号对齐**继承**英文固化时间。根治 reflow「整段翻译丢失时间轴 → 后期靠猜重建」的病根。与 translate 的区别：中文仍是整段自由翻译（非逐句被英文框住）、时间/序号运算全脚本化（agent 一个数字不碰）。

## 输入 / 输出

### 工作目录

| 目录 | 角色 | 读写 |
|------|------|------|
| `_input/` | 待处理字幕入口 | 只读输入 |
| `_output/` | 最终交付输出 | 写正式稿 |
| `_work/<视频名>/` | 中间产物 + 断点恢复 + 临时脚本 | 只读写**当前视频**子目录 |

> 工作区隔离见 [redstone-conventions#工作区隔离](../redstone-conventions/SKILL.md#工作区隔离)。

### 输入

- `<工作目录>/../_input/<文件名>.srt`（带时间码）——必须有原轴可固化
- YouTube transcript（无时间码）**不适用**本工作流，走 translate

### 输出

- `<工作目录>/../_output/<文件名>.reflow.srt`，默认双语 en-zh（英文行 = E 句/片段原文，中文行 = 继承时间后的译文），时间轴 = 源头固化（贴原 cue，局部按中文阅读舒适拆/合）
- 输出变体见 [redstone-conventions#语言顺序与输出变体](../redstone-conventions/SKILL.md#语言顺序与输出变体)

### 中间产物与断点恢复

**产物统一块级**（块数 = 空隙组数 × 组内片数），阶段二产物在 `<工作目录>/reflow2/`：

1. **阶段〇/一 领域预判与术语补齐**（`redstone-preprocess`）→ `<工作目录>/01_subtitle_asr_fixed.srt`、`02_terms.md`
2. **阶段二 源头固化 + 继承回填**（本工作流）：
   - 步骤 1 空隙探测 + 硬性断句 → `reflow2/r00_gaps.md`、`r01_breaks.md`
   - 步骤 2 定容量 + 分块 → `reflow2/chunks/`
   - 步骤 3 归一化 + 补标点 → `r01_normalized/`、`r01_results/`
   - 步骤 4 **源头固化** → `en_timeline/`（★E 句 + 固化时间，只读真值锚）
   - 步骤 5 翻译 → `r02_results/`
   - 步骤 6 切 Z + 对齐 → `zh_sentences/`、`align/`
   - 步骤 7 继承回填 → `r04_draft.srt`、`r04_bilingual.srt`、`r04_alerts.md`
3. **阶段二½ 人工审核**（`redstone-review`）→ 用户确认
4. **阶段三 数据源总结**（`redstone-finalize`）

**中断恢复路由**：检查 `<工作目录>/` 最完整产物，从产出该产物的步骤开头继续：

1. 无任何产物 → 从头（阶段〇）
2. 仅 `01_subtitle_asr_fixed.srt` → preprocess §1.1
3. 有 `02_terms.md` → preprocess §1.3
4. 有 `reflow2/r00_gaps.md`/`r01_breaks.md` → 步骤 2
5. 有 `reflow2/chunks/` → 步骤 3 归一化
6. 有 `reflow2/r01_normalized/` → 步骤 3 补标点
7. 有 `reflow2/r01_results/` → 步骤 3 校验（补标点后校验）
8. 有 `reflow2/en_timeline/` → 步骤 4 校验
9. 有 `reflow2/r02_results/` → 步骤 6
10. 有 `reflow2/zh_sentences/` + `reflow2/align/` → 步骤 7
11. 有 `reflow2/r04_draft.srt` → 步骤 7（重新回填）

## 依赖

| 话题 | 权威 Skill |
|------|-----------|
| 通用规则（环境/工作区/分块/门禁等） | `redstone-conventions` |
| 翻译前置（阶段〇/一） | `redstone-preprocess` |
| 人工审核（阶段二½）+ 输出门禁 | `redstone-review` |
| 数据源总结（阶段三） | `redstone-finalize` |
| 去翻译腔 | `humanizer-zh` |
| subagent 派发 | `subagent-dispatch` |

## 注意事项

### 特有规则

- **时间轴源头固化（本工作流核心）**：E 句时间由脚本在源头固化（`en_timeline`），Z 句通过对齐继承——**任何环节不允许 agent 手写时间戳/句号编号/数列**（时间/序号运算全脚本化，translate 教训）；翻译 agent 输入输出均不带时间
- **E = 只读真值、Z = 每次重算**：E 句由脚本从 01 固化、永不重编号（免疫人工编辑偏移）；Z 每次从 r02 重切（删句/改句后重切重对齐，不依赖记忆编号）
- **r02 定稿即自然译文**：翻译后脚本切 Z、继承时间，**无二次创作**（不做 agent 分句/断句）
- **输出门禁**：`_output/` 只收阶段二½ 用户确认后的正式稿

## 固定工作流指令

### 阶段〇 / 阶段一：领域预判 + 术语补齐

按 [redstone-preprocess](../redstone-preprocess/SKILL.md) 原样执行（阶段〇 / §1.1 扫描 → `01_subtitle_asr_fixed.srt` / §1.2 补齐 / §1.3 确认 → `02_terms.md` / §1.4 入库）。`--cue-exact` 校验保留（保护原轴骨架）。**阶段门禁：`01`/`02` 交用户确认后才进入阶段二，不得擅自跨阶段**。

> **实践建议**（机制设计不变）：阶段〇/一 分块 `--owned` ≤300 cue 封顶（见 reflow-redstone SKILL 实践建议，同机制）

### 阶段二：源头固化 + 继承回填

> 进入本阶段加载 [phase2.md](phase2.md) 执行——步骤 1-7 完整指令（空隙探测 → 分块 → 补标点 → 源头固化 → 翻译 → 切 Z+对齐 → 继承回填，各步按「归一化 → 处理 → 校验」三段组织）。

### 阶段二½：人工审核循环

按 [redstone-review](../redstone-review/SKILL.md) 执行。**审核对象：对齐方案 + 最终 SRT**——重点核对 `align/` 的 Z↔E 语义对应是否判对（继承时间正确性的根基）+ `r04_draft.srt` 阅读节奏。**审核中发现 AI 味 / 翻译腔 → 回 r02 改整句**（脚本重切 Z、重对齐、重继承），红石术语译名不受影响。

### 阶段三：数据源效果总结

按 [redstone-finalize](../redstone-finalize/SKILL.md) 原样执行。
