---
name: subagent-dispatch
description: 派发 subagent 处理长视频分块任务的模板与纪律。约束 subagent 不过度思考、不逐句确认、只报结构化结果，并在 prompt 中显式注入先验知识（知识卡）。长视频分块合并/翻译、批量校验等需要拆给 subagent 的任务使用。
---

# subagent 派发模板

## 背景：subagent 是无状态的

每次派发的 subagent 都是**全新上下文**，看不到主会话已加载的术语/陷阱词/ASR 修正。因此**先验知识必须显式写进 subagent 的 prompt**，不能指望"主流程加载过一次就延续"。

## 派发前主 Agent 准备

1. 生成/读取该视频的**知识卡**（`02_terms.md`：已确认术语 + 陷阱词命中项 + ASR 修正映射）
2. 用 `scripts/srt_chunk.py` 分块（见 [segment-subtitles](../segment-subtitles/SKILL.md)）
3. 为每块组装 prompt（模板见下），一次派发一批

## 每块 prompt 模板

```
任务：对以下第 <k>/<N> 块字幕做 <合并|翻译>。

## 先验知识（必须遵守）
<知识卡：可整卡或按本块命中词过滤，至少含已确认术语、scan 命中项（按本块 cue 过滤）、陷阱词命中项、ASR 修正映射>

## 本块数据（OWNED=负责产出；CONTEXT=只读衔接，见 segment-subtitles）
<chunk_k.txt 内容>

## 纪律
- 直接执行，不要向用户确认任何步骤；不要复述计划或询问"是否继续"
- 有歧义时按默认规则处理并在结果里标注，不阻塞
- 只输出结构化结果（见下），不要描述推理过程

## 输出（写文件，勿返回全文）
- 将结果写入 `_work/<视频名>/<任务目录>/chunk_<k>.txt`（任务目录：merge→`_merge_results/`、translate→`_trans_results/`、term→`_term_results/`、humanize→`_humanize_results/`）
- 格式：每行 `段号|cue范围|<文本>`（utf-8，覆盖写本块文件，勿追加、勿碰其它文件）
- 写完后报告 `已写入 <文件名>（N 行）`，不要粘贴结果全文
```

## 任务变体（各隔离步骤的输出格式）

| 任务 | 输入 | 输出文件（`_work/<视频名>/`，每行一条） |
|------|------|----------------------|
| 合并 | OWNED cue + CONTEXT | `_merge_results/chunk_<k>.txt`：`段号\|cue范围\|合并后文本`（含 `CARRY: c<idx>` 结转标记） |
| 翻译 | OWNED 段 + 知识卡 | `_trans_results/chunk_<k>.txt`：`段号\|cue范围\|译文`（双语：英文行+中文行） |
| 术语扫描 | OWNED cue + scan 命中项（按块过滤）+ 术语/陷阱词知识卡 | `_term_results/chunk_<k>.txt`：`term_en\|译名\|来源\|ASR修正\|[待查/待审核]`（决策行附首次时间戳） |
| 去翻译腔 | 04 全稿/分块 + humanizer 规则 | `_humanize_results/chunk_<k>.txt`：`段号\|修订后译文`（可附改动点说明） |

## subagent 纪律（生成 prompt 时必须包含）

1. **不过度思考**：不要输出大量分析、备选方案、风险清单；只做被要求的事
2. **不逐句确认**：不要每步问"这样可以吗""需要我继续吗"；有歧义默认处理 + 标注，交由主 Agent 汇总时统一确认
3. **只报结果**：结果写入指定分块文件后，回传 `已写入 <文件名>（N 行）` + 遗留标记（如 `CARRY`/`[待审核]`）；**勿在回复中粘贴结果全文**，不描述推理过程
4. **按规则兜底**：术语按知识卡；知识卡没有的按 `[待审核: 原词]` 标记，不阻塞任务
5. **不翻阅其它视频历史文件**：只用 prompt 提供的数据与知识卡，不自行读取 `_work/`、`_output/` 下其它视频的文件作参考（见 `translate-redstone`「目录约定」）

## 组装（agent 读头尾衔接 + 校验脚本兜底）

主 Agent 组装（数字步骤）：
1. 按 subagent 报告的 `已写入` 确认各块文件齐全
2. **只读每块头尾衔接窗口**（read_file 行范围，如每块前 2-3 行 + 后 2-3 行），按块序处理跨块衔接，**不读中间**（中间由 subagent 产出，全量正确性交校验脚本兜底）：
   - **重叠**：上一块末段与下一块首段 cue 范围交叉 → 重复，保留更完整版本（默认 start 最早，见 [segment-subtitles#跨块未完成句](../segment-subtitles/SKILL.md#跨块未完成句结转规则)）
   - **gap**：两块 cue 号不连续 → 查 SRT 确认 gap 处是否空 cue（[Music] 等），是则并入相邻段、否则标记重译
   - **结转**：`CARRY: c<idx>` 对应产出段，确认未重复未遗漏
   - 已确认的 ASR 修正（`02_terms.md`）在组装期应用
3. 落盘 `03_segments.md` / `04_translation_draft.srt`
4. **全量机械校验交脚本**（覆盖完整/不重叠/边界⊆原集/格式）-> [segment-subtitles#输出与校验](../segment-subtitles/SKILL.md#输出与校验)；校验报错即回到对应块修复
5. 阶段二½ 交用户审核
