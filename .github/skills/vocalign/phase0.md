# vocalign 阶段〇执行细节（音频采集与文本定稿）

> 本文件 = 阶段〇的**完整执行指令**（按角色名组织）。**仅进入阶段〇时读取**——阶段路由 / 产物链 / 中断恢复见 [SKILL.md](SKILL.md#中间产物与断点恢复)。

> **派发边界**：文本定稿**一律派 subagent**（任务 = `task-e0`，渲染时 `--skill vocalign`），无需报告策略——见 [subagent-dispatch#派发边界](../subagent-dispatch/SKILL.md#派发边界)。
> **执行型纪律与模型**：纪律母版「一、执行型定位」内联执行型纪律；派发入口 / 运行模型名不在 skill 硬编码——见 [EDITOR_COMPAT#各编辑器派发 subagent 命令表](../../../docs/EDITOR_COMPAT.md)（模型名读 `configs/subagent_model.yaml`）。

> **缺口门禁（进入本阶段前的第一件事）**：缺音频源 / 无 GPU / 未装 venv / ffmpeg 缺失时 → **暂停（退出码非 0）+ 一次性列出缺口**，等用户决策（补缺口后重跑，或显式确认回退 reflow2）。**不得自行判定跳过**。

---

## 阶段〇：音频采集与文本定稿

### 语音采集

1. **采集**：`.venv\Scripts\python.exe scripts\vocalign_collect.py "<音频>" -o "<W>\vocalign" --hf-endpoint https://hf-mirror.com`
   - 音频取自 `<工作目录>/../_Release/` 或 `../_input/` 的同名文件（mp4/mkv 可直接解码）
   - **必须用 venv 解释器**（依赖 torch / faster-whisper / whisperx，不在主 requirements）——解释器固定 `.venv\Scripts\python.exe`，venv 位置与创建见 [SETUP#语音对齐虚拟环境](../../../docs/SETUP.md#语音对齐虚拟环境vocalign)；缺失 → 按缺口门禁暂停
   - **两步分两进程**（`whisperx` 与 `ctranslate2` 同进程触发 cuDNN 冲突，脚本内已分进程）：
     - 段级转写 → `segments.srt`
     - 强制对齐 → `words.json`
   - 已有可信文本时 `--stage align --text-srt <srt>` 跳过转写，只做对齐

**验收要点**：

- **产物存在**（收信号即验，用目录列举而非读取——产物可能超长单行）
- **未对齐词占比**：`words.json` 的 `meta.n_unaligned` / `n_words` ≈ 2.6%（下一角色的骨架脚本会在 >10% 时退出码 1）
- **抽查标点质量**：`segments.srt`（人工，看标点是否成句、有无退化）
  - ⚠️ **未对齐词不得手工清理**：时间 `null` 是空洞标记（见 [SKILL.md#特有规则](SKILL.md#特有规则)）

### 骨架构建

1. **骨架构建**：`python scripts\vocalign_skeleton.py --words "<W>\vocalign\words.json" -o "<W>\vocalign" --expand`
   - 输入 `vocalign/words.json`；判据：净停顿 = 词间间隙 − 40ms 伪间隙 baseline；≥500ms 判句界，≥250ms 判子句界
   - 未对齐词按前后锚点插值（**抑制空洞伪边界的关键**）
   - 产出 `skeleton.json` / `skeleton.txt` / `boundaries.txt` / **`long_lines.srt`（初版 SRT 载体）**

**验收要点**：

- **退出码 1 = 未对齐词超过 10%** → 复核采集结果（对齐模型 / 语言设置），勿静默继续
- **人工抽查** `skeleton.txt`（长句 / 子句 / 词三层是否合理）
- **复核低置信边界清单**（`--expand` 展开）：无标点且短停顿的边界真伪混杂，脚本**只标注不降级**，须人工或定稿环节裁决

### 分块：清单分批

1. **定容量**：`python scripts/context_estimate.py "<W>\vocalign\long_lines.srt" --no-amplification`（输出 `--owned` 建议值）
2. **分块**：`python scripts\text_chunk.py "<W>\vocalign\long_lines.srt" --type srt --owned <N> --ctx 10 --out "<W>\vocalign\chunks"`

> 输入 `vocalign/long_lines.srt`（初版载体）；本步只为**定稿清单分批**（清单按块派发），块内容会在阶段三被覆盖——分块只需“长句边界 + 时间”，与文本内容无关。
> **为何先分块再定稿**：定稿清单要按块派发，而分块又需要载体 → 循环。解法是骨架先产**初版载体**。
> 骨架判据决定块边界必然落在长句边界，故 **vocalign 不存在跨块句**（对照 reflow2 需“衔接归位”机制）。

### 文本定稿

##### 归一化

1. 无——直接使用 `vocalign/skeleton.json` + `vocalign/boundaries.txt` + `vocalign/chunks/`（可选 `<W>/01_subtitle_asr_fixed.srt` 作交叉比对参照）

##### 处理

1. **导出清单（脚本）**：
   ```powershell
   python scripts\vocalign_text.py emit --skeleton "<W>\vocalign" --e0 "<W>\vocalign\e0" `
       --srt "<W>\01_subtitle_asr_fixed.srt" --chunks "<W>\vocalign\chunks"
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
2. **人工复核** `e0/_check_report.md` 的失败明细（失败行是否需重派该块）
3. **改动审计**：`e0/_changes.tsv`（逐条列出定稿相对骨架原文的改动：S 号 / 改动类型 / 原文 / 定稿）——对比 reflow2 的措辞校验：本工作流**允许**改词（仲裁是核心功能），故不做“措辞必须一致”硬校验，改为**逐条可核**
4. **超长句告警**：`e0/report.md` 的告警节（逗号 >10 或字符 >600 的长句 = **该断未断**的信号，即 B 类判“无”过多的后果，应回看该项作答）
5. **抽检定稿文本** `e0/long_lines.md`：仲裁修正是否合理、**非口播注释并入位置是否正确**（头部注明注释数）、文本是否为**转写原样**（形态归一只用于算差异，写进定稿即失真）

> **⚠️ apply 后必须重跑分块**（阶段三 [分块：正式分块](phase3.md#分块正式分块)）——否则下游读到**未定稿**文本（与定稿不一致）。这是链路唯一的人工顺序约束。
