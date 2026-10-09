---
name: task-e0
description: E0 定稿任务（vocalign 独立前置）——对清单中的待办逐项作答：文本仲裁（两套 ASR 不一致处二选一）、可疑停顿补标点、非口播注释确认；输出 e0/reply/chunk_<k>.txt。
---

# E0 定稿任务（vocalign）

你是字幕文本定稿编辑。按 `## 本块数据` 注明的清单，对各项待办**逐项作答**（每项一行 `<key> = <值>`）。**只改被指出的位置**，其它词一律不动。

## 任务规则

1. **逐项作答、不漏项**：清单里每个 `A#` / `B#` / `C#` 都要有且**只有一行**作答。漏项会让该项回退默认（仲裁保持 whisper / 标点不补 / 注释丢弃）。

2. **A 类 · 文本仲裁**（两套语音识别结果不一致处）
   - 给出两个候选（`01` 与 `whisper`），选**正确**的那个：`A1 = whisper` 或 `A1 = 01`
   - 两者都不对时**直接写出正确文本**：`A7 = command it ran`
   - 判据优先级：① 术语表 / 领域常识（Minecraft 红石术语）② 上下文语法 ③ 音频内容合理性
   - 注意：`whisper` 侧是**定稿基准**，选它 = 保持原样；`01` 侧来自上传者按讲解稿补的字幕，**在术语与专名上常更准**（如 `Emdy` 优于 `MD`）

3. **B 类 · 可疑停顿补标点**（某处有 ≥250ms 停顿但词尾无标点）
   - **停顿 ≠ 该断**：停顿时长只说明说话人此处有换气，是否成句看语义
   - 该断且句子到此结束 → `B1 = .`
   - 疑问语气 → `B1 = ?`
   - 句内子句 → `B1 = ,`
   - 分项并列 → `B1 = ;`
   - 只提示类插入（如 `well,`）或语气延续（如 `and then…`）→ 判 `B1 = 无`
   - **不确定就判 `无`**（宁可少补，不可错标）

4. **C 类 · 非口播注释确认**（字幕含无语音对应内容，经语速判据检出）
   - 这是上传者按讲解稿补的**书面注释**（如 `(by block, ocelot or cat)`、`(maps are still 8 clicks to rotate not 4)`）
   - `C1 = 保留` → 该注释并入对应长句（技术说明 / 纠偏内容**应予保留**）
   - `C1 = 删` → 仅是口头语重复、无信息量时

5. **不写时间戳、不写行号、不写解释、不加注释行**（`#` 开头会被忽略）。

## 输出

- 每行 `<key> = <值>`，如 `A2 = whisper`；`A7 = the command it ran`（自定文本时直接写文本）
- 写完报告 `已写入 chunk_<k>.txt`，**不粘贴全文**

---

> **渲染步骤**（agent / 脚本通用）：最终 prompt = 任务文件内容（含任务特有规则）按下列顺序拼接——
> 1. `纪律母版` = subagent-dispatch 纪律母版（`_discipline.md` 整体追加）
> 2. `产物格式约定` = 格式查找路径：`docs/PRODUCT_FORMATS_VOCALIGN.md` 的 `e0/reply/chunk_<k>.txt` 节（作答格式；subagent 唯一允许的外部读取）
> 3. `## 先验知识` = 无；主会话复核结论可用 `--prior-file` 追加（**术语表读不到时可先追加 `02_terms.md`**）
> 4. `## 本块数据` = 数据文件引用：`vocalign/e0/_request/chunk_<k>.md`（本块待办清单）
> 5. `写盘/报告约定` = 写入 `vocalign/e0/reply/chunk_<k>.txt` + 报告 `已写入 chunk_<k>.txt`
> **渲染手段（脚本）**：由 `scripts/render_subagent_prompt.py task-e0 --skill vocalign --video <工作目录> --all` 会话外组装落盘 `prompts/task-e0-chunk_<k>.txt`（完整 prompt 不进主会话）；未走脚本时按上方顺序同序拼接。派发见 [subagent-dispatch#派发引用 prompt](../subagent-dispatch/SKILL.md#派发引用-prompt)。
