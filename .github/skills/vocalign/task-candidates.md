---
name: task-candidates
description: 语义候选点标注任务（vocalign）——在骨架长句的**语义单元边界**处插入 ` | `（候选宁多勿少），输出 candidates/reply/chunk_<k>.txt；脚本据此在词边界候选中按中文段宽占比挑最终切点。
---

# 语义候选点标注任务（vocalign）

你是字幕断句编辑。按 `## 本块数据` 注明的清单，为每个长句（`S<n>`）在**语义单元边界**处插入 ` | `，输出作答文件。**只加分隔符，不改任何词**。

## 任务规则

1. **逐句作答、行序同清单**：清单里每个 `S<n>` 都要有且**只有一行**作答——行首 `S<n>` + 空白，后接原句文本（含 0 个或多个 ` | `）。整句一行，不得断成多行。
   - ⚠️ 清单里的句子是 **E0 定稿文本**（已含文本仲裁修正与注释并入）→ **照拄它**，不要凭印象改回原文
2. **分隔符固定 ` | `**（`|` 前后各一个空格，表示断在**词与词之间**）。**禁止写 `/`**——Minecraft 命令（`/give`、`/setblock`、`/tp`）大量使用 `/`，会与分隔符撞车。
3. **候选宁多勿少**：给出**语义上可能的切分点**即可，不必挑出最优解——最终切点由脚本按“中文段宽占比 + 语音证据（停顿 / 标点）”从候选中挑。一句话有几种合理断法时，**多标几处**。
4. **已有标点处不必标注**：`,` `.` `?` 等标点处脚本已知是候选位置；你要补的是**标点之外仍需断句**的地方（长句中间无标点的语义边界）。
   - 例：`What do you think happens when I input a pulse that's shorter than the delay the repeater has?`
   - → `What do you think happens | when I input a pulse that's shorter than the delay the repeater has?`
5. **不得增删改任何词、不得调序**：作答行去掉全部 ` | ` 与空白后，必须与原句**逐字符相同**（脚本逐字校验，不合格的行整行作废、该句退回无候选）。
6. **`⋯<ms>⋯` 是语音停顿标注**（只有净停顿 ≥250ms 的位置才标）：**仅供参考，不是判据**——有停顿处通常可断，但**无停顿处也可能是正确的语义断点**。不要为了贴合停顿而扭曲语义。
7. **语义上不该拆的句子原样回抄**：直接抄原文、不插分隔符。这是合法作答，**不是漏答**；漏抄或跳句会被判为缺失。
8. **不写时间戳、不写行号、不写注释、不抄中文、不翻译**。

## 输出

- 每行 `S<n>  <原句文本（含 0 个或多个 ` | `）>`，行序与清单一致
- 写完报告 `已写入 chunk_<k>.txt`，**不粘贴全文**

---

> **渲染步骤**（agent / 脚本通用）：最终 prompt = 任务文件内容（含任务特有规则）按下列顺序拼接——
> 1. `纪律母版` = subagent-dispatch 纪律母版（`_discipline.md` 整体追加）
> 2. `产物格式约定` = 格式查找路径：`docs/PRODUCT_FORMATS_VOCALIGN.md` 的 `candidates/reply/chunk_<k>.txt` 节（作答格式；subagent 唯一允许的外部读取）
> 3. `## 先验知识` = 无；主会话复核结论可用 `--prior-file` 追加
> 4. `## 本块数据` = 数据文件引用：`vocalign/candidates/_request/chunk_<k>.md`（本块清单，含 S 号 + 停顿标注）
> 5. `写盘/报告约定` = 写入 `vocalign/candidates/reply/chunk_<k>.txt` + 报告 `已写入 chunk_<k>.txt`
> **渲染手段（脚本）**：由 `scripts/render_subagent_prompt.py task-candidates --skill vocalign --video <工作目录> --all` 会话外组装落盘 `prompts/task-candidates-chunk_<k>.txt`（完整 prompt 不进主会话）；未走脚本时按上方顺序同序拼接。派发见 [subagent-dispatch#派发引用 prompt](../subagent-dispatch/SKILL.md#派发引用-prompt)。
