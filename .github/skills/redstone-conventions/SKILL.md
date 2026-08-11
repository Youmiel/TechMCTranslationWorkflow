---
name: redstone-conventions
description: 红石字幕工作流通用规则
---

# 红石字幕工作流通用规则（redstone-conventions）

> 定位：红石字幕工作流各阶段共用的通用规则。工作流特有规则（时间边界、产物契约、审核对象）见各自主 skill。


## 禁止自动删除

- 清理文件/目录遵循 `AGENTS.md` 核心原则 #6，提示用户手动执行，Agent 不得主动删除

## Wiki 抓取与兜底

Wiki 页面获取降级链、缓存保真阶梯、缓存读取、抓取注意事项、社区资料检索**全部见 [wiki-tools](../wiki-tools/SKILL.md)（权威）**；缓存文件格式见 `docs/WIKI_CACHE_FORMAT.md`。MCP 配置见 `.vscode/mcp.json`，部署见 `docs/MCP_DEPLOYMENT.md`。

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
- 产物契约表（共享前置 `01/02`；translate 阶段二 `s03/s04`；reflow 阶段二 `r00–r04`）见各工作流主 skill

## 语言顺序与输出变体

- 固定 `en-zh`（英文行在前、中文行在后），输出/构建/校验脚本一律遵守，不得产出后再手动重排
- 双语相关脚本统一用 `--order en-zh|zh-en` 显式指定（默认 en-zh）
- **输出变体**（translate / reflow 两工作流统一）：`bilingual`（默认，en-zh 双语）· `zh-only`（仅目标语言）· `annotated`（双语 + 术语来源注释）

## 时间纪律（通用部分）

- 相邻段时间**不得重叠**：`end_i ≤ start_{i+1}`（允许相接不允许交叉）
- 每次分句/合并后**立即校验**，不要最后抽查：时间/重叠/逆序用 `srt_check_segments.py`，行宽用 `srt_check_width.py`
- **时间边界规则差异**（工作流特有，见各自主 skill）：translate 输出边界**必须 ⊆ 原字幕边界集合**；reflow 允许预测点（100ms 取整、不入原边界集）

## 长视频分块（全流程通用机制）

> 超长上下文任务（术语扫描、合并/断句、翻译、去翻译腔、批量校验等）都可用本机制控制上下文，**不限于断句**。凡 cue/段数超出单次上下文，必须先分块再逐块交给 subagent。

### 1. 前置判断（读前必做，脚本确定性判定）

- 读取全文前先跑 `python scripts/context_estimate.py <输入> --window <窗口> --ratio <比例>`——脚本确定性输出 类型（SRT cue 数 / 非 SRT 全文）/ 字符数 / 估算 token / 当前占窗口比例 / 是否超阈值，**替代人工估算**（"cue 数 × 词数 × 比例"心算易错，被幻觉误导会导致误判是否分块）；`<输入>` 支持 SRT 与 reflow 非 SRT 产物（`r01_merged_en.txt`/`r02_translation_zh.txt`/`r03_plan.md` 等 txt/md/json）
- **`--window` = 模型最大窗口（部署配置）**：agent 知道自己所用模型的窗口规格（如 128k / 200k），作为固定配置传入（脚本默认 / `configs/` 设一次），**不是当前剩余窗口**（剩余受会话历史/压缩影响，agent 无法精确感知）；仅在不确定所用模型规格时请求用户确认**一次**（部署时，非每视频）
- **预算语义 = 单步读入 × 每步单独判定**：阈值（窗口 × 50%）是**"单步读入预算"**——一次读**一个产物** + 该步 prompt 不超窗口一半，**不是整个阶段所有读取之和**；阶段内多次处理（读 01、读 r01、读 r02…）是**先后不是同时**（产物落盘衔接，不把前步全文留在会话）——**每读一个新产物前单独跑一次判定**，不一次判定管全程
- **主会话连续处理时更保守**：历史对话会占窗口 → 单步读入预算降到 `--ratio 0.3~0.4`；依赖全貌、不适合分块的步骤（如 reflow 分句对应）靠**其他步骤隔离**腾出窗口，不压缩该步内容。字幕翻译**不接受上下文压缩**（压缩→失真），宁低勿高
- **超阈值即分块**，不得靠规模直觉直接读（"恰好没超"是运气不是流程保证）

### 2. 分块执行（srt_chunk.py）

- **工具**：`python scripts/srt_chunk.py <srt> --out <dir> --owned N --ctx M [--order en-zh|zh-en]`（默认 N=100、M=6；输出 OWNED=本块负责 / CONTEXT=前后只读衔接 两分区；边界不切开任何 cue）
- **输入**：merge 阶段用 `01_subtitle_asr_fixed.srt`（单语 cue 流）；translate 阶段用合并后的段 SRT（双语，附带知识卡）
- **非 SRT 文本（reflow `r01`/`r02`/`r03` 等 txt/md/json）**：无 cue 边界，**不适用 `srt_chunk.py`**（按 cue 分块）；超阈值时按各自**语义单位**分块（r01 按空隙语义段、r02 按句、r03 按整句组），块间独立落盘衔接、逐块交 subagent（prompt 模板同用）——无 cue 级 OWNED/CONTEXT 与 `CARRY` 结转，块边界取语义完整处

### 3. 逐块派发与组装（subagent）

- **每块 prompt**：见 [subagent-dispatch#每块 prompt 模板](../subagent-dispatch/SKILL.md#每块-prompt-模板)
- **跨块未完成句（结转规则）**：每块只产出语义完整句且其 start cue 落在 OWNED 区；负责区末尾句在可见上下文（OWNED+CONTEXT）内仍不完整则标记 `CARRY: c<起始idx>` 结转、不产出；下一块在 CONTEXT 看到该句开头则正常产出（start 落 CONTEXT 的结转句允许产出）；主 Agent 组装时对结转句只采用 start 最早的版本
- **每块结果由 subagent 直接写独立文件**：subagent 把结果写入 `_work/<视频名>/<任务目录>/chunk_<k>.txt`（merge→`_merge_results/`、translate→`_trans_results/`、term→`_term_results/`、humanize→`_humanize_results/`），写后报告文件名+行数、**不返回全文给主会话**；主 Agent 组装时**只读每块头尾衔接窗口**、不读中间，全量校验交脚本（见 subagent-dispatch「组装」），勿只存会话（压缩后恢复极耗时）
