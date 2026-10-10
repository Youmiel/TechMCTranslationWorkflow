---
name: vocalign
description: 红石技术视频字幕工作流——音频强制对齐取得词级真实时轴与自带标点，脚本据此构建“长句 / 子句 / 词”三层骨架；文本经 LLM 定稿后整段自由翻译，中文按阅读节奏分段、英文按语义候选点与语音停顿证据切分，时间取语音实测值。产出双语交付稿与告警。
---

# 红石字幕语音对齐（vocalign）

时轴与断句从同一来源（音频强制对齐）取得；中文整段自由翻译不吃时间，英文片由语义候选点与语音停顿证据切分。

## 输入 / 输出

### 输入

- **音频或视频文件**（`_Release/` 或 `_input/` 同名；mp4/mkv 可直接解码）——唯一的时轴来源
- 油管**原始自动字幕**（可选，如 `<工作目录>/01_subtitle_asr.srt`）——仅作文本交叉比对的参照，**未做 ASR 修复、未补标点**；有则参与仲裁与注释检测，无则跳过

> ⚠️ 无音频 = 无法执行，回退 reflow2（见「特有规则」的缺口门禁）。

### 输出

- `<工作目录>/../_output/<文件名>.vocalign.srt`，默认双语 zh-en

### 中间产物与断点恢复

产物统一在 `<工作目录>/vocalign/`：

| 产物 | 生成者 | 说明 |
|---|---|---|
| `words.json` / `segments.srt` | `vocalign_collect.py` | 词级时轴（未对齐词保留占位，时间 null）/ 段级转写 |
| `segments_patched.srt` / `patch_report.md` / `patch_decisions.tsv` | `vocalign_collect.py`（`--patch-pad` 启用时） | **可疑点重识别拼接稿**（可疑点 ±N 秒单独重识别后与全片稿拼接，消前文污染幻觉）/ 逐窗口**差异清单**与自检 / 人工**裁决表**（回退指定窗口） |
| `segments.suspect.md` | `vocalign_collect.py` | 转写可疑段（重复幻觉 / n-gram 循环 / 语速异常）——**只报不改**，交 agent 或人工决策 |
| `skeleton.json` / `skeleton.txt` / `boundaries.txt` / `stitches.txt` | `vocalign_skeleton.py` | 三层骨架（长句 / 子句 / 词）、判据明细、**碎片归位明细**（源段边界落在句中的合并记录） |
| `long_lines.srt` | `vocalign_skeleton.py` | 长句 SRT 载体（初版，供分块） |
| `e0/long_lines.md` / `long_lines.srt` | `vocalign_text.py apply` | 定稿文本与其 SRT 载体 |
| `e0/en_timeline/chunk_<k>.txt` | `vocalign_text.py apply` | S 长句与实测时间（供对齐） |
| `e0/_request/` `reply/` `_items.json` `_changes.tsv` | `vocalign_text.py` / 定稿子 agent | 定稿待办、机器锚点与**改动审计** |
| `chunks/` | `text_chunk.py` | 分块（翻译单元） |
| `consistency/chunk_<k>.txt` | 复核子 agent | 机制断言疑点清单（阶段五裁决） |
| `r01_normalized/chunk_<k>.txt` | `srt_reflow_normalize.py` | 块内 cue 合并成整段 |
| `r02_results/chunk_<k>.txt` | 翻译子 agent | 整段中文译文 |
| `zh_sentences/chunk_<k>.txt` · `align/chunk_<k>.txt` | `srt_reflow2_zsent.py` / 对齐子 agent | Z 句列表 / `Z<n> = S<m>` |
| `candidates/_request/` `reply/` `chunk_<k>.tsv` | `vocalign_candidates.py` / 候选点子 agent | 候选点清单 / 作答 / 全局词号（**按合译组派发**：合译的多个长句共用一行 `S10+S11`） |
| `r04_draft.srt` / `r04_bilingual.srt` / `r04_alerts.md` | `vocalign_backfill.py` | 交付稿与告警（含超宽片清单） |
| `<名>.filled.srt` | `srt_fill_gaps.py` | **空隙填充**后的交付稿（相邻段间隙 < 1s 时前段 end 延到后段 start，消闪烁） |
| `vocalign/_fix_splits.tsv`（可选） | 人工 / agent 写 | **定点修复**切点（处置超宽英文片：`<S号>\t<左词> \| <右词>`） |
| `vocalign/_fix_splits.draft.md` | `vocalign_backfill.py` | **超宽片定点修复待裁决草稿**（成因分类 + 片内切点模拟效果与推荐；裁决后抄进 `_fix_splits.tsv`） |

断点恢复（取最完整产物为恢复点）：

- 无 `words.json` → 语音采集
- 无 `skeleton.json` 或 `long_lines.srt` → 骨架构建
- 无 `e0/long_lines.md` → 文本定稿
- 无 `02_terms.md` → 术语扫描
- 无 `consistency/chunk_<k>.txt` → 一致性复核
- 无 `r02_results/` → 翻译
- 无 `align/` → 对齐
- 无 `candidates/chunk_<k>.tsv` → 候选点
- 无 `r04_draft.srt` → 回填组装

## 依赖

| 话题 | 权威 Skill |
|------|-----------|
| 通用规则（环境 / 工作区 / 分块 / 门禁） | `redstone-conventions` |
| 术语扫描环节 | `redstone-preprocess` |
| 人工审核与输出门禁 | `redstone-review` |
| 数据源总结 | `redstone-finalize` |
| subagent 派发 | `subagent-dispatch` |
| Wiki / 去翻译腔 | `wiki-tools` / `humanizer-zh` |

## 注意事项

### 特有规则

- **时轴源头 = 语音实测**：`words.json` 的时间是唯一真值来源，agent 不得手写时间戳或编号（时间运算全脚本化）
- **文本源一次定死**：定稿生成后全程只认 `S` 号，不得混入 `01` 的 cue 号（两套编号混用会静默错配）
- **缺口门禁**：无音频 / 无 GPU / 未装 venv / ffmpeg 缺失时暂停（退出码非 0）并一次性列出缺口，等用户决策；语音采集用 `.venv\Scripts\python.exe`（位置与创建见 [SETUP#语音对齐虚拟环境](../../../docs/SETUP.md#语音对齐虚拟环境vocalign)），agent 不得自行判定跳过
- **未对齐词占位是数据契约**：`words.json` 中时间 null 的词是空洞标记，删除会让骨架在空洞处产生伪边界
- **低置信边界需复核**：无标点加短停顿的边界真伪混杂，脚本只标注不降级，须人工或 LLM 裁决
- **中文段数由中文阅读节奏定**：不可用英文子句数强制决定中文段数
- **观感例外（唯一）**：交付前跑 `srt_fill_gaps.py` —— 相邻段间隙 < 1s 时把前段 `end` 延到后段 `start`（消闪烁）。这**主动偏离语音实测时间**（多出的是静默段），故独立成脚本、默认不原地覆盖，且只填小于阈值的间隙（≥ 阈值的间隙是真实停顿/剪辑，保留）
- **定稿后必须重跑分块**：分块分两次（清单分批用初版载体、正式分块用定稿载体），第二次不可省

### 与 reflow2 的取舍

| 项 | reflow2 | vocalign |
|---|---|---|
| 时轴 | 字符比例插值加吸附 | 语音实测（词级） |
| 文本源 | 自动字幕经 SRT 前置链 | 音频转写加 LLM 定稿 |
| 英文切点 | 全部词边界挑（可切在词中） | 候选点加语音停顿证据 |
| 中文段与英文片对应 | 按文本源顺序加 task-match | 自产 `Z<n> = S<m>` 对齐 |
| 补标点 | LLM 补整段 | 只补可疑停顿 |
| 跨块句 | 需衔接归位（块按 cue 等分，常落在句中） | 不存在（块必落在长句边界） |
| 依赖 | 纯文本可跑 | 需音频加 torch/whisper |

## 固定工作流指令

本工作流包含阶段〇–阶段三、阶段五–阶段六（音频驱动，无阶段四）。命令根 = `Project_Main/`。

### 阶段〇：音频采集与文本定稿

进入本阶段加载 [phase0.md](phase0.md) 执行——完整指令按角色名逐序组织（语音采集、骨架构建、分块：清单分批、文本定稿）。

### 阶段一：加载集判定与准备

1. **加载集判定**：`python scripts/glossary_load_plan.py "<W>\vocalign\e0\long_lines.srt"`
   - 输入 `vocalign/e0/long_lines.srt`（定稿载体）
   - 扫全片命中已收录术语 → 出常驻表与候选表（按命中数阈值）；实际常驻表用 `--list-resident` 查
   - 两产物随载体落 `e0/`（脚本按输入目录定位，`--out` 只改报告路径）：`glossary_load_plan.md`（报告）、`glossary_gate_log.md`（门禁日志）
2. **门禁：必须停下等裁决**：把报告报用户确认，**停下等用户判定**（剔除非必要表），裁决后跑 `--record "<剔除的表>"`（候选全保留亦需 `--record`）
   - 门禁日志为追加式（探测范围 → 用户决策，供调阈值）；**不得静默跳过门禁**；阈值含义与记录格式见 [redstone-preprocess#阶段一加载集判定与准备](../redstone-preprocess/SKILL.md#阶段一加载集判定与准备)

### 阶段二：术语扫描与知识补齐

1. **术语命中扫描**：`python scripts/glossary_lookup.py scan "<W>\vocalign\e0\long_lines.srt" --out "<W>\scan_terms.txt"`
2. **术语识别分块**（与翻译块不同量级，可单独 `--owned`）：
   `python scripts/text_chunk.py "<W>\vocalign\e0\long_lines.srt" --type srt --owned 300 --ctx 6 --out "<W>\_term_chunks"`
3. **术语识别（逐块派 subagent）**：
   ```powershell
   python scripts/render_preprocess_prompt.py task-term-recognition --video "<W>" --all `
       --chunks-dir "<W>\_term_chunks" --scan "<W>\scan_terms.txt" --glossary .cache/glossary/general.csv
   ```
   - 产物：`_term_results/chunk_<k>.txt`
4. **集中补齐与门禁：必须停下等裁决**：L3 查证后报用户确认待查 / 待定术语，**停下等用户裁决**，再写 `02_terms.md`（翻译的术语依据）
   - **不得静默跳过门禁**；流程见 [redstone-preprocess#阶段二术语扫描与知识补齐](../redstone-preprocess/SKILL.md#阶段二术语扫描与知识补齐)
   - 术语首次时间戳精度为**长句级**（`S` 号，非 cue 级）
   - **不启用 `asr_trigger.py scan`**：其映射表按旧文本源的误听形态积累，用于音频转写文本时误报率高；误听修正由定稿的文本仲裁承担
5. **术语核对**（翻译后执行，需译文对照）：见 [phase3.md](phase3.md#翻译) 校验段

### 阶段三：工作流核心

进入本阶段加载 [phase3.md](phase3.md) 执行——完整指令按角色名逐序组织（分块：正式分块、一致性复核、翻译、对齐、候选点、回填）。

### 阶段五：人工审核循环

按 [redstone-review](../redstone-review/SKILL.md) 执行。**审核对象：机制断言疑点清单（`consistency/`）+ `align/` 的 Z 与 S 语义对应 + `r04_bilingual.srt` 阅读节奏 + `r04_alerts.md` 的无证据切点**。审核中发现 AI 味或翻译腔回译文改整句；裁定改英文侧回文本定稿重跑下游。

### 阶段六：数据源效果总结

按 [redstone-finalize](../redstone-finalize/SKILL.md) 原样执行。
