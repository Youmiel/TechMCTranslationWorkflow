---
name: redstone-conventions
description: 红石字幕工作流通用规则
---

# 红石字幕工作流通用规则（redstone-conventions）

> 定位：红石字幕工作流各阶段共用的通用规则。工作流特有规则（时间边界、产物契约、审核对象）见各自主 skill。


## 禁止自动删除

- 清理文件/目录遵循 `AGENTS.md` 核心原则 #6，提示用户手动执行，Agent 不得主动删除

## 工作区隔离

- 临时产物 / **临时脚本**一律放 `_work/<视频名>/`，**禁止写入 `scripts/`**（只维护正式工具，见 `scripts/README.md`）
- **禁止参考其它视频的历史文件**（`_work/`、`_output/` 下其它视频的格式/术语/风格都不是权威）；参考只用 `ref_translations/`、`knowledge/`、`.cache/`、当前视频自身 `_work/<当前视频名>/`
- 每次视频启动先确认「当前视频名」，所有读写限定在 `_work/<当前视频名>/`

## 环境

- 本机**无 venv**，直接用 `python`（`venv\Scripts\Activate.ps1` 存在才激活）
- PowerShell 中带 `[` 的文件路径用 `-LiteralPath`（否则被当通配符，Get-Content/Get-FileHash 失败）

## 输出门禁

- `_output/` **只收用户确认后的正式稿**；未经确认，产物止步 `_work/<视频名>/`（标注"待用户确认"），禁止写入 `_output/`
- 循环机制与审核对象见 [redstone-review](../redstone-review/SKILL.md)

## 断点恢复

- 各阶段结束**立即落盘**；恢复时按**最完整产物**跳步
- 产物契约表（translate `01–04` / reflow `r00–r04`）见各工作流主 skill

## 语言顺序

- 固定 `en-zh`（英文行在前、中文行在后），输出/构建/校验脚本一律遵守，不得产出后再手动重排
- 双语相关脚本统一用 `--order en-zh|zh-en` 显式指定（默认 en-zh）

## 时间纪律（通用部分）

- 相邻段时间**不得重叠**：`end_i ≤ start_{i+1}`（允许相接不允许交叉）
- 每次分句/合并后**立即校验**，不要最后抽查：时间/重叠/逆序用 `srt_check_segments.py`，行宽用 `srt_check_width.py`
- **时间边界规则差异**（工作流特有，见各自主 skill）：translate 输出边界**必须 ⊆ 原字幕边界集合**；reflow 允许预测点（100ms 取整、不入原边界集）

## 长视频分块（全流程通用机制）

> 超长上下文任务（术语扫描、合并/断句、翻译、去翻译腔、批量校验等）都可用本机制控制上下文，**不限于断句**。凡 cue/段数超出单次上下文，必须先分块再逐块交给 subagent。

- **工具**：`python scripts/srt_chunk.py <srt> --out <dir> --owned N --ctx M [--order en-zh|zh-en]`（默认 N=100、M=6；输出 OWNED=本块负责 / CONTEXT=前后只读衔接 两分区；边界不切开任何 cue）
- **输入**：merge 阶段用 `01_subtitle_asr_fixed.srt`（单语 cue 流）；translate 阶段用合并后的段 SRT（双语，附带知识卡）
- **每块 prompt**：见 [subagent-dispatch#每块 prompt 模板](../subagent-dispatch/SKILL.md#每块-prompt-模板)
- **跨块未完成句（结转规则）**：每块只产出语义完整句且其 start cue 落在 OWNED 区；负责区末尾句在可见上下文（OWNED+CONTEXT）内仍不完整则标记 `CARRY: c<起始idx>` 结转、不产出；下一块在 CONTEXT 看到该句开头则正常产出（start 落 CONTEXT 的结转句允许产出）；主 Agent 组装时对结转句只采用 start 最早的版本
- **每块结果由 subagent 直接写独立文件**：subagent 把结果写入 `_work/<视频名>/<任务目录>/chunk_<k>.txt`（merge→`_merge_results/`、translate→`_trans_results/`、term→`_term_results/`、humanize→`_humanize_results/`），写后报告文件名+行数、**不返回全文给主会话**；主 Agent 组装时**只读每块头尾衔接窗口**、不读中间，全量校验交脚本（见 subagent-dispatch「组装」），勿只存会话（压缩后恢复极耗时）
