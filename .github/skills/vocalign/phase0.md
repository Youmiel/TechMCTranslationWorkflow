# vocalign 阶段〇执行细节（音频采集与文本定稿）

> 本文件 = 阶段〇的**完整执行指令**（按角色名组织）。**仅进入阶段〇时读取**——阶段路由 / 产物链 / 中断恢复见 [SKILL.md](SKILL.md#中间产物与断点恢复)。

> **派发边界**：文本定稿**一律派 subagent**（任务 = `task-e0`，渲染时 `--skill vocalign`），无需报告策略——见 [subagent-dispatch#派发边界](../subagent-dispatch/SKILL.md#派发边界)。
> **执行型纪律与模型**：纪律母版「一、执行型定位」内联执行型纪律；派发入口 / 运行模型名不在 skill 硬编码——见 [EDITOR_COMPAT#各编辑器派发 subagent 命令表](../../../docs/EDITOR_COMPAT.md)（模型名读 `configs/subagent_model.yaml`）。

> **缺口门禁（进入本阶段前的第一件事）**：缺音频源 / 无 GPU / 未装 venv / ffmpeg 缺失时 → **暂停（退出码非 0）+ 一次性列出缺口**，等用户决策（补缺口后重跑，或显式确认回退 reflow2）。**不得自行判定跳过**。

---

## 阶段〇：音频采集与文本定稿

### 语音采集

1. **采集**：`.venv\Scripts\python.exe scripts\vocalign_collect.py "<音频>" -o "<W>\vocalign" --patch-pad 20 --hf-endpoint https://hf-mirror.com`
   - 音频取自 `<工作目录>/../_Release/` 或 `../_input/` 的同名文件（mp4/mkv 可直接解码）
   - **必须用 venv 解释器**（依赖 torch / faster-whisper / whisperx，不在主 requirements）——解释器固定 `.venv\Scripts\python.exe`，venv 位置与创建见 [SETUP#语音对齐虚拟环境](../../../docs/SETUP.md#语音对齐虚拟环境vocalign)；缺失 → 按缺口门禁暂停
   - **两步分两进程**（`whisperx` 与 `ctranslate2` 同进程触发 cuDNN 冲突，脚本内已分进程）：
     - 段级转写 → `segments.srt`
     - 强制对齐 → `words.json`
   - **建议加 `--patch-pad 20`**（可疑点重识别，与转写同进程；**默认即 ±20s**，`--patch-pad 0` 关闭）：先转写，再探测可疑段，对每个可疑点取 ±20s 单独重识别（块内保留前文、消除前文污染），最后与全片稿拼接
     - 产出 `segments_patched.srt`（拼接稿）+ `patch_report.md` + `patch_decisions.tsv`（裁决表）+ `patch_windows/`（转写缓存）；`--stage align` 会自动优先取拼接稿
     - 实测（PRR2，772.6s）：可疑段由 8 降到 1、耗 22s（仅重识别约 13% 音频）、S 编号 151 变 153
     - ⚠️ **并非万灵药**：窗口内是全新解码，**可能在非可疑处引入新错**（实测 `Copper bulbs` 被改成 `Lava bulbs`）
   - **门禁：必须停下等裁决**（四个动作，不得静默跳过）：
     1. **探测 + 整理**（脚本自动）：`patch_report.md` 的**差异清单**只列两版文本不同处（已归一分词与数字写法：`right-clicking` = `right clicking`、`two` = `2`），**未列出的内容两版一致**，不必核对；标 `〔接缝〕` 者为拼接副作用（去重 / 边界不重合），非内容改动
     2. **上报 + 停下**：把差异清单**摘要表报用户**（每窗口一行：差异数 + 前两条摘要），**停下等裁决**——不要让用户读两版全文
     3. **落地**：把要回退为全片版的窗口写进 `patch_decisions.tsv`（`<窗口号>\trevert`；未列默认 keep），带 `--patch-decisions` 重跑 `--stage patch`（转写有缓存，**秒级**），再跑 `--stage align`
     4. **复核**：差异大且不像重复幻觉时，**人工核对音频**后再定（脚本只能报，不能判对话与错）
   - 已有可信文本时 `--stage align --text-srt <srt>` 跳过转写，只做对齐

**验收要点**：

- **产物存在**（收信号即验，用目录列举而非读取——产物可能超长单行）
- **未对齐词占比**：`words.json` 的 `meta.n_unaligned` / `n_words` ≈ 2.6%（下一角色的骨架脚本会在 >10% 时退出码 1）
- **抽查标点质量**：`segments.srt`（人工，看标点是否成句、有无退化）
- **处置转写可疑段**（`segments.suspect.md`，脚本**只报不改**）：优先看 `patch_report.md`（`--patch-pad` 已自动修好大部分）；剩余逐条手动处置——
  - **重复型**（段首重复前段末）：删去重复片段（内容无损失）
  - **循环型**（n-gram 跑飞）：该区间真实内容**已被循环挤掉**，删重复无法恢复 → 取该时间区间**重跑识别**
  - **语速异常型**：多为上述两者的伴随症状；单独出现时核对音频
  - 处置后**必须重跑对齐与骨架**（时间变则切分变）；**不得凭该报告判丢句**（它判的是跑飞）
- **复核拼接稿**（启用 `--patch-pad` 时）：先看 `patch_report.md` 的**差异清单摘要表**（每窗口：差异数 / 状态 / 摘要）与自检告警（时间倒挂 / 接缝重复 / 兜底边界）；差异明细按 `删 / 增 / 改` 三态给出，需逐条判断改动是否成立（**重点看“改”**：可能是修正，也可能是补丁改错）
  - 回退了的窗口，状态列会标“已回退全片版”；复核后把结果同步到 `patch_decisions.tsv`，重跑 `--stage patch` + `--stage align`
- **对照原始字幕核验**（有油管原始字幕时）：仅作**参照**（未修复、未补标点），用于核对可疑段处是否有内容缺失
- ⚠️ **未对齐词不得手工清理**：时间 `null` 是空洞标记（见 [SKILL.md#特有规则](SKILL.md#特有规则)）

### 骨架构建

1. **骨架构建**：`python scripts\vocalign_skeleton.py --words "<W>\vocalign\words.json" -o "<W>\vocalign" --expand`
   - 输入 `vocalign/words.json`；判据：净停顿 = 词间间隙 − 40ms 伪间隙 baseline；≥500ms 判句界，≥250ms 判子句界
   - 未对齐词按前后锚点插值（**抑制空洞伪边界的关键**）
   - **碎片归位**（默认开，`--no-stitch` 关）：whisper 是**段级**输出，段边界不保证与句界一致——断言末尾无句末标点 + 后句首字母小写 → 合并（判据同 reflow2 的源切分缺陷），否则长句会被切碎
   - 产出 `skeleton.json` / `skeleton.txt` / `boundaries.txt` / `stitches.txt` / **`long_lines.srt`（初版 SRT 载体）**

**验收要点**：

- **退出码 1 = 未对齐词超过 10%** → 复核采集结果（对齐模型 / 语言设置），勿静默继续
- **人工抽查** `skeleton.txt`（长句 / 子句 / 词三层是否合理）
- **复核碎片归位**（`stitches.txt`）：源段边界落在句中时（前句末尾无句末标点 + 后句首字母小写）已自动合并——确认无“合法无标点结尾 + 后句大写”的真句界被误合（有误合用 `--no-stitch` 全关或人工修）
- **复核低置信边界清单**（`--expand` 展开）：无标点且短停顿的边界真伪混杂，脚本**只标注不降级**，须人工或定稿环节裁决

### 分块：清单分批

1. **定容量**：`python scripts/context_estimate.py "<W>\vocalign\long_lines.srt" --no-amplification`（输出 `--owned` 建议值）
2. **分块**：`python scripts\text_chunk.py "<W>\vocalign\long_lines.srt" --type srt --owned <N> --ctx 10 --out "<W>\vocalign\chunks"`

> 输入 `vocalign/long_lines.srt`（初版载体）；本步只为**定稿清单分批**（清单按块派发），块内容会在阶段三被覆盖——分块只需“长句边界 + 时间”，与文本内容无关。
> **为何先分块再定稿**：定稿清单要按块派发，而分块又需要载体 → 循环。解法是骨架先产**初版载体**。
> 骨架判据决定块边界必然落在长句边界，故 **vocalign 不存在跨块句**（对照 reflow2 需“衔接归位”机制）。

### 文本定稿

##### 归一化

1. 无——直接使用 `vocalign/skeleton.json` + `vocalign/boundaries.txt` + `vocalign/chunks/`（可选油管**原始自动字幕**作交叉比对参照，**未修复、未补标点**）

##### 处理

1. **导出清单（脚本）**：
   ```powershell
   python scripts\vocalign_text.py emit --skeleton "<W>\vocalign" --e0 "<W>\vocalign\e0" `
       --srt "<W>\01_subtitle_asr.srt" --chunks "<W>\vocalign\chunks"
   ```
   - 未给 `--srt` → 跳过仲裁与注释检测（**全新视频的常态**，流程照常）
   - `--chunks` 未给会自动探测 `<W>\vocalign\chunks`；探测不到则 `en_timeline` 只出单块（阶段三对齐会缺块）
   - 产出 `e0/_request/chunk_<k>.md`（人读清单）+ `e0/_items.json`（**机器锚点**，apply 依赖它，**清单与锚点分工：清单给人看、锚点给脚本用**）
2. **定稿（逐块派 subagent）**：渲染命令 `python scripts\render_subagent_prompt.py task-e0 --skill vocalign --video "<W>" [--chunk <k> | --all]`
   - 派发引用 prompt（见 [subagent-dispatch#派发引用-prompt](../subagent-dispatch/SKILL.md#派发引用-prompt)）——渲染即存档，先存后发
   - 产物：`e0/reply/chunk_<k>.txt`（每行 `<key> = <值>`）
   - 收信号即验（目录列举确认产物存在）
3. **作答校验（脚本）**：`python scripts\vocalign_text.py check --skeleton "<W>\vocalign" --e0 "<W>\vocalign\e0"`
4. **应用（脚本，唯一写入定稿的动作）**：`python scripts\vocalign_text.py apply --skeleton "<W>\vocalign" --e0 "<W>\vocalign\e0"`
   - 产出 `e0/long_lines.md` + **`e0/long_lines.srt`（定稿载体）** + `e0/en_timeline/`

##### 校验

**任务**：主会话统一跑；问题走定点修复（B 档 `task-fix`，见 [subagent-dispatch#定点修正](../subagent-dispatch/SKILL.md#定点修正校验打回先小规模修不整块重派)）。

1. **作答校验**：`check` 退出码 0（失败行不静默采信——该 S 号保持默认：仲裁不动、标点不补、注释丢弃）
   - 含**仲裁标点守恒**：A 段新文本不得比 whisper 侧少句读标点（选项 01 而词应取 01 侧时，**标点仍应保 whisper 侧** → 写自定文本如 `comparison,`）
     - 为何：仲裁只该改**词**、不该动**句读**。实测丢一个列表逗号 → 中文顿号无处对应、回填失去一个标点证据
2. **人工复核** `e0/_check_report.md` 的失败明细（失败行是否需重派该块）
3. **改动审计**：`e0/_changes.tsv`（逐条列出定稿相对骨架原文的改动：S 号 / 改动类型 / 原文 / 定稿）——对比 reflow2 的措辞校验：本工作流**允许**改词（仲裁是核心功能），故不做“措辞必须一致”硬校验，改为**逐条可核**
4. **超长句告警**：`e0/report.md` 的告警节（逗号 >10 或字符 >600 的长句 = **该断未断**的信号，即 B 类判“无”过多的后果，应回看该项作答）
5. **抽检定稿文本** `e0/long_lines.md`：仲裁修正是否合理、**非口播注释并入位置是否正确**（头部注明注释数）、文本是否为**转写原样**（形态归一只用于算差异，写进定稿即失真）

> **⚠️ apply 后必须重跑分块**（阶段三 [分块：正式分块](phase3.md#分块正式分块)）——否则下游读到**未定稿**文本（与定稿不一致）。这是链路唯一的人工顺序约束。
