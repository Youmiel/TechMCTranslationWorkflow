---
name: task-punctuate
description: 补标点任务（reflow2）——合并字幕块 cue 文本为整段英文并补标点（仅加标点、不改措辞、空隙强制断句），输出整段文字到 r01_results/chunk_<k>.txt。
---

# 补标点任务

你是字幕标点编辑。把 `## 本块数据` 注明的输入文件（`## OWNED` 区）的 cue 文本合并成一段连续英文并补充标点，写入指定输出文件。

## 任务规则

1. **仅加标点、不改措辞**：只允许**插入**标点符号，**任何单词一律不得改动**。
   - 补哪些标点：单一事实源 = `scripts/shared/srt_common.py` 的 `PUNCT_ROLE_CHARS`（勿凭记忆列举字符集）
   - 不删词、不加词、不换词、不调语序、不改时态 / 单复数 / 拼写
   - OWNED 文本的字符序列只可能因插入标点而变长，绝无其他变化
   - 原词有疑（如 ASR 残词）按 `[待审核: 原词]` 兜底标记，**不改写**
   - **破折号 / 冒号不得越权**：破折号 `—` 只用于真插入语 / 语义转折，冒号 `:` 只用于真引出列举 / 定义——**不得**用它们连接独立句、顶替逗号 / 句号；判据 = 删掉后句子是否缺成分
2. **空隙强制断句**：`## 先验知识` 给出的空隙标记 `【强制断句】` 处按复核方式强制断句，**不跨空隙合句**
3. **块内不按句分行**：OWNED 已由归一化脚本合并为一段连续英文，直接在其上补标点。
   - 不按 cue 分行
   - 不按句分行
   - 不带 `c<idx>\t时间码\t` 前缀
4. **跨块句补全（唯一允许的承接）**：OWNED 首 / 末句若被**片边界**切断，用 CONTEXT 判断并补全为完整句。
   - **片边界强制自检（产出前必做）**：片边界是本任务**最易误断处**（归一化在此截断、你的产出也在此收尾）。
     取 OWNED **最后 3 词**与**最初 3 词**，逐词过规则 7 的悬空成分清单：
     - OWNED 末尾命中悬空成分 → 读 AFTER 找补足 → 补全为完整句、行首标记 `【延伸句】`
     - OWNED 开头是 BEFORE 末尾的补足 → 补全为完整句、行首标记 `【承接句】`
     **“看起来像句末”不等于句末**——未过此检查，不得在片边界处落下句末标点
   - **首句承接前块**（BEFORE 末尾句未结束、OWNED 首句是其延续）→ 本块补全完整句，行首标记 `【承接句】`
   - **末句延伸后块**（OWNED 末尾无句末标点、AFTER 开头是其延续）→ 本块补全完整句，行首标记 `【延伸句】`
   - 相邻两块对同一跨块句**都补全**（块 k `【延伸句】` ≡ 块 k+1 `【承接句】`）
   - **空隙边界不承接**：空隙处句子必断，BEFORE/AFTER 仅作语境，字符不并入输出
5. **格式标记不得改写**：输入中的 `## BEFORE` / `## OWNED` / `## AFTER` 分区标记与输出中的 `【承接句】` / `【延伸句】` 标记——不得删除、不得改字、不得改变位置或写法
6. **说话人话轮处断句（`## 先验知识` 的参考提示，**非硬约束**）**：转写文本里的说话人标签（形如 `Name:`）常标记话轮切换。
   - **为何要提示**：归一化把块内 cue 合并成连续文本、抹平 cue 边界；标签处原本无句末标点时，你无从判断句界，
     会把两次回答并成一句 → E 句被并大 → 下游英文行把两个话轮挤在同一行、与中文拆段错位。
   - `## 先验知识` 的 `## 参考断句点（说话人话轮）` 节列出“前 cue 末尾无句末标点 **且** 涉及说话人标签”的 cue 边界
     （来自**原字幕行结构**，不是语义判断）。
   - **必须结合语义判断，不得机械遵循**：
     - 确为**话轮切换**（换人说话 / 一问一答）→ 在标签前补句末标点（`. ` 或 `? `）
     - 只是**同一说话人的长话**被字幕行切断、语义与前后连贯 → **不要断**
   - 示例：`... oftentimes unintuitive, jazziRed: would you say it's hard to learn redstone? CraftyMasterman: (thinking) CraftyMasterman: yes but let's see if we can change that.`
     → `... oftentimes unintuitive. jazziRed: would you say it's hard to learn redstone? CraftyMasterman: (thinking). CraftyMasterman: yes. but let's see if we can change that.`
   - **只补句末标点**：不改词、不改大小写（`yes. but` 的小写由 r02 翻译承担）
7. **句界判据 = 语法语义完整性（**大小写与切行零证据**）**：判句界**只允许**靠语法与语义，**不得**把大小写或行结构当作依据。
   - **为何**：ASR 自动加的大小写与切行**会出错**。实证（ZXGpmaIcMMo c400/c401）：原句 `... and an output from below.` 被 ASR 切成
     `... and an output From` + `Below Hoppers can also input items...`——介词 `from` 被写成大写 `From`、宾语 `below`
     被写成大写并另起一行。**这类切分错误处“双大写”是常态，不构成句界信号**（纯属语言模型对句界的误判痕迹）；
     反之，误切处也可能**两侧全小写**（同视频 c200/c201：`... pick up and transfer` + `items the shape...`）。
     （全 5 个视频实测：cue 末尾无句末标点占 93%、cue 首字母大写仅 18%——大小写与真实句界无稳定关系）
   - **判据 A · 悬空成分**（候选断点**前**的词）：以下列成分收尾 → 该处**必然未完成，不得断句**：
     - 介词：from, to, of, in, on, at, with, for, by, into, about, above, below, over, under, between, through, against, without, than, as
     - 冠词 / 限定词：the, a, an, this, that, these, those, my, your, its, their, our, some, any, no, each, every
     - 助动词 / 情态：is, are, was, were, be, been, being, do, does, did, can, could, will, would, shall, should, may, might, must, has, have, had
     - 从属连词：that, which, who, whom, whose, because, if, when, while, since, although, unless, until, whether
     - 并列连词：for（作并列连词罕见，一律按悬空处理）；**`and` / `but` / `or` / `nor` / `yet` / `so` 不属此类**——它们连接的是成分还是分句按判据 C 判，**不得一律当悬空成分**
     - 及物动词（宾语缺失）：transfer, pull, push, put, take, give, send, make, place, detect, use, see, know, say, tell, show, find, get, need, want, support, accept, power, activate
   - **判据 B · 补足成分**（候选断点**后**的词）：紧接的词若正好补全上述悬空（名词短语补介词 / 宾语补动词 / 从句补连词）→ **依附前句，不得在此断**。
   - **判据 C · 独立主谓（该断就断）**：一处出现**第二个能单独成句的主谓结构** → 必须在其边界补句末标点。
     - 判法（不计数）：**这段能拆成两句、各自都成立吗？能 → 拆。**
     - 常见形态：并列连词（`and` / `but` / `or` / `nor` / `yet` / `so`）后紧跟**自己的主语 + 谓语**，而前半已有完整主谓
     - **为何必须主动断**：下游按中文行宽把英文句切成 1–2 段——**英文句太长，就会被切在句子中间**（半句一行）
   - **判据 D · 反向保护（别切过头）**：不得为拆句而切断**同一主谓结构**——一个主谓未说完（宾语 / 补语 / 从句尚未交代）时，句号不得落下。
   - **实例（本项目实测）**：
     - ❌ `... an output from. Below Hoppers can also input items...`　✅ `... an output from below. Hoppers can also input items...`
       （`from` 悬空 + `below` 是其宾语；勿被 `From`/`Below` 双大写误导）
     - ❌ `... can pick up and transfer. Items the shape...`　✅ `... can pick up and transfer items. The shape...`
       （`transfer` 及物动词缺宾语 + `items` 是宾语；**两侧全小写**，误断与大小写无关）
     - ❌ `... another comparator or redstone dust, but if you place a repeater ...`（**该断未断**：`but` 后是独立主谓，应在 `but` 前补句号）
     - ✅ `... an input side on the back, an output side in the front, and two side inputs ...`（`and` 连接并列宾语 → 依附前句，正确）
   - **产出前自检（全篇，与规则 4 的片边界自检同一次完成）**：回扫全篇，找**能拆成两句、各自都成立**而未见句末标点的地方，补上句号。
     - **不计数**：不数词、不估字数（长度由主会话脚本校验，思考中不做手算）

## 输出

- 产物 = **整段文字**（一段连续英文，块内不按句分行）
- **不控制行长度**：直接输出完整连续文本，**无需自行折行**——折行由主会话统一脚本处理（`auto_wrap_file` 就地折行）
- **跨块句标记**：
  - 本块首句承接前块 → 行首 `【承接句】<完整句>`
  - 本块末句延伸后块 → 行首 `【延伸句】<完整句>`
- 写完后报告 `已写入 <文件名>`，不粘贴全文

---

> **渲染步骤**（agent / 脚本通用）：最终 prompt = 任务文件内容（含任务特有规则）按下列顺序拼接——
> 1. `纪律母版` = subagent-dispatch 纪律母版（`_discipline.md` 整体追加）
> 2. `产物格式约定` = 格式查找路径：`docs/PRODUCT_FORMATS_REFLOW.md` 的 `r01_results/chunk_<k>.txt（补标点块）` 节（subagent 唯一允许的外部读取）
> 3. `## 先验知识` = 空隙断句标记（`r01_breaks.md` 复核结果，紧贴任务规则 2）+ 参考断句点（说话人话轮，非硬约束，见任务规则 6）
> 4. `## 本块数据` = 数据文件引用：`reflow2/r01_normalized/chunk_<k>.txt`（本块输入）+ 前后块衔接
> 5. `写盘/报告约定` = 写入 `reflow2/r01_results/chunk_<k>.txt` + 报告 `已写入 chunk_<k>.txt`
> **渲染手段（脚本）**：由 `scripts/render_subagent_prompt.py --skill reflow2` 会话外组装落盘 `_work/<视频名>/prompts/task-punctuate-chunk_<k>.txt`（完整 prompt 不进主会话）；未走脚本时按上方顺序同序拼接。派发见 [subagent-dispatch#派发引用 prompt](../subagent-dispatch/SKILL.md#派发引用-prompt)。
