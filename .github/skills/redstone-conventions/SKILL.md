---
name: redstone-conventions
description: 红石字幕工作流通用规则
---

# 红石字幕工作流通用规则（redstone-conventions）

> 定位：红石字幕工作流各阶段共用的通用规则。工作流特有规则（时间边界、产物契约、审核对象）见各自主 skill。


## 禁止自动删除

- 清理文件/目录遵循 `AGENTS.md` 核心原则 #6，提示用户手动执行，Agent 不得主动删除

## Wiki 抓取与兜底

Wiki 页面获取降级链、缓存保真阶梯、缓存读取、**过期判定与主动刷新**、抓取注意事项、社区资料检索**全部见 [wiki-tools](../wiki-tools/SKILL.md)（权威）**；缓存文件格式见 `docs/WIKI_CACHE_FORMAT.md`。MCP 配置见 `.vscode/mcp.json`，部署见 `docs/SETUP.md`。

- **翻译过程中任何需请求 Wiki 的场合**（不止阶段一集中补齐）：命中缓存后**必先判定过期，过期则主动刷新再读**——不得静默复用过期缓存（静默错误来源）
  - 判定：`python scripts/refresh_cache.py --check-page "<页面名>"`（退出码 1 = 有需处理项）
  - 刷新：`python scripts/fetch_wiki.py --refresh "<页面名>"`（wikitext/lossless 直连，保真度不降）
- **抓取/长内容阅读一律派 `wiki-researcher`**（研究型 agent，任务文件 `wiki-tools/task-wiki-query.md`），主会话不读页面全文；浏览器兜底档由主会话执行

## 工作区隔离

- 临时产物 / **临时脚本**一律放 `_work/<视频名>/`，**禁止写入 `scripts/`**（只维护正式工具，见 `scripts/README.md`）；**也不得散落到 `_work/` 根目录或其它视频目录**——隔离以视频为单位，`_work/` 根只放各视频子目录、非临时文件堆放区
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
- **恢复只读产物，禁读对话记录（transcript）**
  - 中间结果丢失 → 从 `_work/` 产物续（见 [PRODUCT_FORMATS](../../../docs/PRODUCT_FORMATS.md)）
  - **绝不读会话 transcript 找中间结果**——transcript 是历史档案，单个会话数百 KB~数 MB（≈数百 k~M token），读入即爆窗口
- **数据禁散落临时脚本**（`_work/` 一次性脚本只放逻辑、不放数据）
  - 禁：把数据本体硬编码进临时脚本——大脚本承载数据会脱离产物契约、会话反复读写膨胀（如把整段译文塞进 `_translate_data.py`）
  - 不禁（逻辑脚本，正常允许）：追加词汇表 / CSV 处理等——数据在 CSV/02_terms 等文件里，脚本只做「读 → 处理 → 写回」

## 语言顺序与输出变体

- 固定 `en-zh`（英文行在前、中文行在后），输出/构建/校验脚本一律遵守，不得产出后再手动重排
- 双语相关脚本统一用 `--order en-zh|zh-en` 显式指定（默认 en-zh）
- **输出变体**（translate / reflow 两工作流统一）：`bilingual`（默认，en-zh 双语）· `zh-only`（仅目标语言）· `annotated`（双语 + 术语来源注释）

## 时间纪律（通用部分）

- 相邻段时间**不得重叠**：`end_i ≤ start_{i+1}`（允许相接不允许交叉）
- 每次分句/合并后**立即校验**，不要最后抽查：时间/重叠/逆序用 `srt_check_segments.py`，行宽用 `srt_check_width.py`（校验脚本默认只给问题数，`--expand` 看明细）
- **时间边界规则差异**（工作流特有，见各自主 skill）：translate 输出边界**必须 ⊆ 原字幕边界集合**；reflow 允许预测点（100ms 取整、不入原边界集）
- **时间引用格式统一（agent 手写 / 反馈）**：agent 手写产物与向用户反馈（术语表 `02_terms.md`、ASR 修正、审核意见、r03 注释等）一律用**时间戳 `HH:MM:SS`**（无毫秒）。
  - **cue 编号（`c<idx>`）只存在于脚本生成 / 解析产物**（`s03` 的 `cstart-cend`、chunks 骨架、`r03_anchored.jsonl`），agent 手写**不写 cue 编号**
  - 时间戳须从字幕时间码**精确读取**（SRT 时间码 `HH:MM:SS,mmm` 去毫秒即得），**禁止凭记忆推算或按 cue 号换算**

## 长视频分块（全流程通用机制）

> 超长上下文任务（术语扫描、补标点、翻译、分句、去翻译腔、批量校验等）都可用本机制控制上下文，**不限于断句**。

> **执行一律 subagent；`context_estimate.py` 只定容量（`--owned`，每块 cue 数）**。核心原则：
> - **一律 subagent**：任务本身无论分不分块都派 subagent（独立窗口，可用上下文远大于承载全部 skill 指令的主会话；主会话只做调度/组装/校验）
> - **同一套处理逻辑、同一套产物契约**：分块与不分块只差块数，不分块 = 只有一块的特例；产物形态一致（块级产物见 §3 / §4）
> - **`--owned` 是每块容量（每块负责的 cue 数），不是块数**；块数由分块模式决定
> - **单块即小规模测试**：用极小输入（`--owned` 足够大）即可验证分块流程逻辑

### 1. 前置判断（读前必做，脚本确定性判定）

- **预检（读前）**：确认 `configs/context_window.json` 存在。若缺失，则询问用户各项参数，并缺省信息填默认值，写入该文件（后续可直接读）。
- **判定工具**：读前先跑 `python scripts/context_estimate.py <输入> [--window <窗口>] [--split-ratio <比例>] [--no-amplification]`。
  - 确定性输出：类型（SRT cue 数 / 非 SRT 全文）、字符数、估算 token、当前占窗口比例、是否超阈值
  - `<输入>` 支持 SRT 与 reflow 非 SRT 产物（`r03_plan.md` 等 txt / md / json）
  - **CLI 参数 / 计算方式 / 算法解释见 [PRODUCT_FORMATS#configs/context_window.json](../../../docs/PRODUCT_FORMATS.md)**
- **判定时机**：**每阶段派发前跑一次 `context_estimate.py`，根据输出计算 `--owned` 参数数值**（材料不落主会话，无「前步全文残留」问题）；字幕翻译**不接受上下文压缩**（压缩→失真），宁低勿高
- **超阈值即拆片**（块数 >1），不得靠规模直觉直接定 `--owned`（"恰好没超"是运气不是流程保证）
- **大 JSONL 按行 grep、不整读**（`r03_anchored.jsonl` 等逐行审查型产物）
  - 审核时按行 grep 关注项（key / alloc / anchor 非唯一失败 / units 命中），只在需要时读个别行
  - 原因：整读抬高阈值——它本身 ~27k token，含它审核输入 ~46k vs 不含 ~19k；同类大 JSON/JSONL 明细一律如此

### 2. 分块工具与块格式（text_chunk.py，通用）

> 工具本身不绑工作流；translate 与 reflow 的分块用法见 §3 / §4。

- **工具**：`python scripts/text_chunk.py <输入> --out <dir> [--type srt|text] [--unit 段|句|整句组] [--owned <每块单位数>] [--ctx <衔接单位数>] [--max-chars <字符>] [--order en-zh|zh-en] [--gaps] [--gaps-file <tsv>]`
  - 默认自动判型：`.srt` 为 srt、否则 text
  - srt 默认 `--owned 100` / `--ctx 6`；text 默认 `--owned 1` / `--ctx 1`
  - 输出统一块格式见 [PRODUCT_FORMATS#通用文本分块](../../../docs/PRODUCT_FORMATS.md)
- **分块根基 = 01_subtitle_asr_fixed.srt（阶段一产物、阶段二入口）**——r01/r02/r03 都是 01 的派生，**从 01 分块**后所有阶段锚定同一套块（块 ↔ cue 区间天然存在），无需中间合并、无需继承边界。**禁止从 r01/r02/r03 文本分块**（那些文本本就需先合并才能切，是弯路）
- **srt 分块两种模式**：
  - **默认**：每 `--owned` 个 cue 一块，块边界 = 纯 cue 数切（translate 用，见 §3）
  - **`--gaps` / `--gaps-file`**：按空隙点分组成「空隙组」，组内按 `--owned` cue 分片；块标识「块G-片P」；同组片合并时无缝拼接（reflow 用——**空隙点强制切块、`--owned` 语义见 §4**）
    - **`--gaps-file <r00_gaps_active.tsv>`（推荐）**：读 `srt_reflow_gap_scan.py` 产出的**生效空隙点集**（人工可编辑 tsv），`status=excluded` 的项自动跳过——这是「排除误判空隙」的**正式通道**（取代旧 hack：去掉 `--gaps` 开关）
    - `--gaps`（旧）：脚本自行探测，不读人工裁决——仅在无 tsv 时兼容保留
- **非 SRT 文本（仅当需处理无 cue 边界的辅助文本）**：按**语义单位**分块（`--unit 段`=空行分隔 / `--unit 整句组`=r03 的 `## S<n>` / `--unit 句`=按标点）；超长单位自动细分（`--max-chars`）为「组-片」，**同组片合并时无缝拼接**
- **`--max-chars`（text 超长细分阈值）**：按 `context_estimate.py` 反推（单块目标字符 ≈ 阈值 token × 1.5 ÷ 安全系数），拿不准默认 6000
- **旧 `srt_chunk.py` 保留兼容**（历史产物/旧流程），**新任务一律用 `text_chunk.py`**

### 3. translate 工作流分块（默认 srt 模式）

> translate 阶段二（合并 / 断句，再翻译）：
> 1. 从 01 分块
> 2. 逐块派 subagent
> 3. `text_merge` 合并全文
> 4. **全局校验**（时间约束跨块，必须合并后验）

- **分块**：`python scripts/text_chunk.py <01.srt> --type srt --owned <N> --ctx <M> --out <任务chunks目录>`（默认模式，每 N cue 一块；N 按 `context_estimate.py` 反推，默认 100）
- **逐块派发**：每块 subagent 做合并/断句（`_merge_results/`）或翻译（`_trans_results/`），prompt 按 [subagent-dispatch#派发配方](../subagent-dispatch/SKILL.md#派发配方) 组装；CARRY 结转规则见 §5
- **合并**：`python scripts/text_merge.py <chunks目录> <结果目录> --out <合并产物>`（srt 类型：全局段号重排）→ `s03_plan.md` / `s04_draft.srt`
- **校验**：`srt_check_segments.py`（时间不重叠 / 边界⊆原集 / 覆盖完整）——**跨块约束，必须合并全文后跑**（translate 特有，见 [segment-subtitles#输出与校验](../segment-subtitles/SKILL.md#输出与校验)）
- **产物**：`s03_plan.md`（断句定稿）、`s04_draft.srt`（双语成稿）

### 4. reflow 工作流分块（--gaps 模式，块级流水线）

> reflow 阶段二（补标点 → 整段翻译 → 分句）：
> 1. 从 01 分块（空隙组优先）
> 2. 逐块独立处理，中间**不拼全文**
> 3. **校验逐块化**
> 4. 仅 r03 / r04 合并
>
> 目标：各子块独立处理、按块传递，减少「拼全文 → 整读 → 再分块」的往返开销。

- **空隙点强制切块（语义硬边界，与容量无关）**：`--gaps` 把 01 按空隙点切成「空隙组」，**每个空隙组至少一块**——块数下限 = 空隙点数+1；仅 01 无空隙点才 1 块
- **`--owned` 只控组内拆片（容量，非块数）**：
  - 空隙组 cue 数 > `--owned` 时组内再拆多片
  - 块数 = 空隙组数 × 组内片数
  - **`--owned` 按最重环节（分句）由 `context_estimate.py` 反推**（推导见 [PRODUCT_FORMATS#configs/context_window.json](../../../docs/PRODUCT_FORMATS.md)「算法解释·放大倍数」）
    - 反推公式：`--owned ≈ 单块容量上限 × 1.5 ÷ 每 cue 平均字符数`
      - 单块容量上限（token）= `context_estimate.py` 输出 = `min(输入预算, 输出预算÷amplification)`，**经 min 统一、已含分句放大**
      - ×1.5 = token→字符；再 ÷ 每 cue 平均字符数（拿不准用保守兜底，宁小勿大）
    - 各阶段共用同一套块（01 骨架），**块定即全局、无法在分句阶段中途改**，宁小勿大
- **分块前先验证 gap 准确性（必做）**：跑 `python scripts/srt_reflow_gap_scan.py <01> -o reflow/r00_gaps.md` 得到：
  - `reflow/r00_gaps.md`（人读报告）——长停顿 >5s / 剪辑跳转 >10s，**并单独分节报告「疑似源切分缺陷」**（判据：前 cue 末尾无句末标点 **且** 后 cue 首字母小写；此类空隙多因原字幕把同一句切成两条 cue，非真实停顿）
  - `reflow/r00_gaps_active.tsv`（**生效空隙点集 = 单一事实源，人工可编辑**）——列 `a_idx b_idx gap_ms kind status note`；`status` 取值 `active`（真实空隙）/ `suspect`（疑似源缺陷，**默认仍生效**，待人工裁决）/ `excluded`（已排除）
  - **脚本只报告不改行为**：确认是源缺陷后，把 tsv 该行 `status` 改为 `excluded` 即为正式排除（不分块 / 不断句 / 校验跳过）；**重跑 gap_scan 不覆盖人工决定**
  - **已有 tsv 则复用**，勿重复探测（以 tsv 的人工裁决为准）
- **一次分块**：`python scripts/text_chunk.py <01.srt> --type srt --gaps-file reflow/r00_gaps_active.tsv --owned <每块cue数> --ctx <衔接cue数> --out reflow/chunks/`——块 = 「空隙组-片」，块边界 = 明确 cue 区间；**`--ctx` 建议 10**（每侧衔接 cue 数）
- **各阶段共用同一套块**：：r01 合并文本读 `chunks/`、r01 补标点读 `r01_normalized/`、r02 翻译读 `r01_results/` 对应块、r03 分句读 `r01_results/` + `r02_results/` 对应块对照——**块边界始终来自 01 分块骨架，不做链式继承**
- **中间产物只落块级（产物单轨）**：`reflow/r01_results/`、`r02_results/`、`r03_results/`（每块独立文件，块数 = 空隙组数 × 组内片数），不再有 `r01_merged_en.txt`/`r02_translation_zh.txt` 完整文件形态——分块/不分块产物契约统一
- **校验逐块化**：`check_words` / `check_breaks` / `check-r03` 支持块级模式（传 `reflow/<阶段>_results/` + `--chunks reflow/chunks/` + `--gaps reflow/r00_gaps_active.tsv`），逐块校验 + 空隙点检查，**不需要先合并全文**。
  - `check_breaks --gaps` 现接受 **tsv**（生效集；`excluded` 项自动跳过）——传旧 `r00_gaps.md` 亦可（脚本自动找同目录 tsv），兼容历史命令
  - **全局校验（块级模式一次验全部块）由主会话在所有块 subagent 全部完成后统一执行一次**
  - subagent 不调用全局校验（见 [subagent-dispatch#纪律母版](../subagent-dispatch/SKILL.md#纪律母版派发时必须整体追加)「五、工作区与工具纪律」——避免每块 subagent 重复跑全量校对）
- **必须合并的**：`r03_plan.md`（`srt_reflow.py` 回填输入，各块 r03 方案按块序直接拼接）、`r04_draft.srt`（最终产物，由 `srt_reflow.py reflow` 生成）——这两个合并后走全局校验
- **约束（r01/r02/r03 块文件格式）**：reflow 补标点 / 翻译块（`r01_results/` / `r02_results/`）为**整段文字**，每块一个空隙组-片 = 一段连续文字。
  - 块内**不按 cue / 句分行、不带 cue 前缀**（逐句 / cue 分行会孤立 ASR 残片导致误译；校验脚本按整段解析）
  - **折行由脚本统一执行**（主会话产出后 `auto_wrap_file` 就地折行 / `text_merge --wrap`，subagent 输出不折行）——产物单行 ≤1000 字符（英文词边界不拆词），属**显示性换行、非语义分行**，校验按整段解析不受影响
  - 仅 r03 分句块（`r03_results/`）用整句分组格式（`## S<n>`）
  - 仅 translate 的 srt 类型结果保留 `段号|cue范围|` 前缀
  - 分句语义对应仍需全貌（块内保持整句 / 单元语义完整，不跨块拆句——空隙为硬边界）
- **旧 `--inherit` 已弃用（deprecated）**：仅兼容旧流程，新方案从 01 分块 + 块级独立流转，不再需要继承边界

### 5. 逐块派发与合并（两工作流共用）

- **每块 prompt（派发配方）**：任务文件 + 纪律母版 + 产物格式约定 + 知识卡 + 块数据，按 [subagent-dispatch#派发配方](../subagent-dispatch/SKILL.md#派发配方) 组装
- **跨块未完成句（结转规则，仅 translate/srt）**：
  - 每块只产出语义完整句且其 start cue 落在 OWNED 区
  - 负责区末尾句在可见上下文（OWNED + CONTEXT）内仍不完整则标记 `CARRY: c<起始idx>` 结转、不产出
  - 下一块在 CONTEXT 看到该句开头则正常产出（start 落 CONTEXT 的结转句允许产出）
  - 合并脚本对结转句只采用 start 最早的版本
- **每块结果由 subagent 直接写独立文件**：subagent 把结果写入 `_work/<视频名>/<任务目录>/chunk_<k>.txt`，写后报告文件名、**不返回全文给主会话**（勿只存会话，压缩后恢复极耗时）。任务目录：
  - translate → `_merge_results/` / `_trans_results/`
  - term → `_term_results/`
  - humanize → `_humanize_results/`
  - reflow → `reflow/r01_results/` / `r02_results/` / `r03_results/`
  - 报告时**不数行数**（行数 / 非空由主会话脚本统计）
- **合并用脚本（替代主 Agent 手工读头尾组装）**：`python scripts/text_merge.py <chunks_dir> <results_dir> --out <合并产物> [--report <报告>] [--window N]`
  - **默认全自动**：按块序读结果、归位拼接成完整产物，主 Agent **零读取**（text 同组无缝/组间空行；srt 全局段号重排）
  - **异常时**：脚本产出 `<merged>.report.md` 异常清单（缺块 / 行数不符 / 重复 / 片号不连续 / cue 重叠 / 缺口 / CARRY）+ **异常块头尾窗口**——主 Agent **只读报告**决策即可，不整读中间
  - 合并后仍跑各工作流校验脚本（translate 用 `srt_check_segments.py`、reflow 用块级/全局校验）全量兜底；异常块经 Agent 修复后重跑 `text_merge.py`（覆盖写合并产物）
- 术语/知识卡注入：全量术语表 + 按本块过滤命中（见 subagent-dispatch）
