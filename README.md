# Minecraft 红石技术视频字幕翻译辅助工作流

基于渐进式轻量级方案的红石技术视频字幕翻译辅助工作流，用于将英文 Minecraft 红石技术视频字幕高质量翻译为简体中文。

接入工作流的 LLM 只需要文字能力，音频仅用于字幕转录，术语查证、翻译与审核等 LLM 环节全部是纯文本处理。

使用流程为：初始化环境 → 将字幕（`vocalign` 还可放音视频）放入 `_input/` → 由 Agent 选定工作流并执行 → 在 `_output/` 获取结果。术语查证、知识补齐与译名统一由 Skill 自动完成；用户仅在加载集确认、术语清单确认与翻译审核等门禁节点参与确认。

本项目遵循 [llm-wiki](https://gist.github.com/442a6bf555914893e9891c11519de94f) 的核心理念：由 Agent 增量构建并持续维护一个持久的知识库，而非在每次提问时从原始文档重新检索。知识在摄入时编译一次并持续更新，交叉引用与矛盾标记预先建立，知识库随使用不断累积。用户负责资料筛选与提问，Agent 负责归纳、交叉引用与记录维护。


## 初始化

```bash
# 安装依赖（Python 3.8+）
pip install -r requirements.txt

# 初始化 submodule（知识仓库 + humanizer-zh Skill）
git submodule update --init --recursive

# storage-archive（Storage-Catalog 存储科技术语词典）仅稀疏检出 dictionary/（体积大、含向量大文件）。
# 新 clone 后 sparse 配置不随仓库传播，需手动启用：
git -C _repos/storage-archive sparse-checkout init --no-cone
git -C _repos/storage-archive sparse-checkout set /dictionary/

# 编辑器适配（为 Claude Code 等编辑器创建 Skill 链接）
python scripts/setup_editors.py
```

配置项与部署步骤（请求身份 / subagent 模型 / 上下文窗口 / MCP Wiki 工具）见 [`docs/SETUP.md`](docs/SETUP.md)；编辑器差异见 [`docs/EDITOR_COMPAT.md`](docs/EDITOR_COMPAT.md)。

> `configs/` 下为**本地个性化配置**（不入库，因人而异），模板见 [`docs/examples/configs/`](docs/examples/configs/)。多数开箱即用；**派发 subagent 前需填 `configs/subagent_model.yaml`**。

## Skills 一览

以下为面向用户的 Skill（翻译与维护时由 Agent 自动加载，无需手动启用），工作流按推荐程度排序：

- `vocalign`: 语音对齐骨架驱动（首选，需音频 / 视频，可附带参考字幕，用于交叉修正转录结果）
- `reflow2`: 语义回填重排 v2
- `reflow-redstone`: 语义回填重排 v1
- `translate-redstone`: 逐句翻译
- `maintain-knowledge`: 维护知识库与术语
<br>
-  [`humanizer-zh`](./skills/humanizer-zh): 去除翻译腔 / AI 味（可选）

## 翻译视频字幕

1. 使用 **VS Code / Claude Code** 打开本项目目录
2. 将待翻译字幕放入 **`_input/`**
3. 向 Agent 发起翻译指令，如：*"翻译 `_input/<文件名>.srt`"*（或提供音视频文件）；拿不准用哪个工作流时，让 Agent 按输入类型推荐（见下"工作流选择"）

翻译流程由 Agent 驱动，大部分环节自动完成，**只在以下两处暂停并等待用户确认**（各工作流的额外门禁见下「工作流选择」）：

1. **翻译阶段前（01/02 确认）**：ASR 修正字幕 + 术语清单（无法确定的词条附候选译名、依据与字幕时间戳）交用户确认，确认后才进入翻译（Agent 不擅自跨阶段）
2. **翻译结果审核**：提交翻译结果，可多轮修改，确认后定稿；如需调整分段 / 回填方案，Agent 会同步征求你的意见

确认定稿后，结果写入 **`_output/`**，默认双语对照（原文一行 + 中文一行），文件名与输入一致。

> 可选：如需译文更自然，可要求 Agent 使用 `humanizer-zh` 去除翻译腔。
> 若流程中途中断（如会话关闭），重新发起即可；Agent 会从 `_work/<视频名>/` 的中间产物自动续跑。

## 工作流选择

四套工作流按推荐程度排序，共享同一条前置链（机械修复 → 领域预判 → 术语补齐）与阶段五审核、阶段六收尾；**共有的人工介入点 = 加载集确认、术语清单确认（`01` / `02`）、审核循环**，下列各条只再列各自特有的门禁。

### 1. vocalign：语音对齐骨架驱动

- **适用范围**：能提供视频或音频的场合（mp4 / mkv 可直接解码）；时轴与断句质量要求高时首选。
- **运作原理**：用 faster-whisper 转写并经 WhisperX（wav2vec2 音素级 CTC）强制对齐，取得词级真实时轴与自带标点；用净停顿阈值构建「长句 / 子句 / 词」三层骨架，英文片按全词边界候选 + 惩罚阶梯最小化代价切分；时间一律取语音实测值。
- **流程概述**：音频采集 → 骨架构建 → 文本定稿 → 分块 → 翻译 → 切 Z 句与对齐 → 候选点 → 回填 → 空隙填充。
- **特有门禁**：可疑段重识别后的差异裁决表（`patch_decisions.tsv`，决定回退哪些窗口）；超宽英文片的定点修复待裁决草稿（`_fix_splits.draft.md`）；无标点短停顿边界的低置信复核；音频 / GPU / venv / ffmpeg 缺口门禁。
- **输出**：`*.vocalign.srt`；无音频时回退 `reflow2`。

### 2. reflow2：语义回填重排 v2

- **适用范围**：只有带时间码的 SRT、拿不到音视频时（或刻意不采用音频驱动）。
- **运作原理**：用脚本按字符→cue 映射与顺序游标锚定，把英文句（E）时间固化在源头（`en_timeline` 只读真值锚）；用 LLM 判定 `Z<n> = E<m>` 语义对应，中文段时间按阅读权重比例分配后继承英文固化时间——整段自由翻译全程不吃时间。
- **流程概述**：空隙探测 → 分块 → 补标点 → 源头固化 → 一致性复核 → 翻译 → 切 Z 句与对齐 → 继承回填。
- **特有门禁**：`align/` 的 Z↔E 语义对应是否正确（继承时间正确性的根基）；机制断言疑点清单（需回看画面 / 音频裁决）。
- **输出**：`*.reflow.srt`。

### 3. reflow-redstone：语义回填重排 v1

- **适用范围**：只有带时间码的 SRT，且沿用「贴合原轴」的老流程。
- **运作原理**：用断点强度角色表 + 动态规划代价最小化（`pack_by_strength`）做断句与拼合；用 LLM 补标点、整段翻译并建立「整句 ↔ 译文单元」语义对应；再以原字幕时间轴为骨架脚本化回填重排（碎片合并 / 整句锚定 / 单元级分配）。
- **流程概述**：空隙探测 → 分块 → 补标点 → 翻译 → 分句对应 → 回填 → 组装。
- **特有门禁**：分句路径选择——语义分句（LLM）/ 脚本断句（机械），**必须询问用户**。
- **输出**：`*.reflow.srt`。

### 4. translate-redstone：逐句翻译

- **适用范围**：任意字幕，含无时间码的 YouTube transcript；要段落规整、逐句清晰时用。
- **运作原理**：用 LLM 断句并逐句翻译，辅以脚本按 token 阈值分块、按块序合并与行宽硬闸门校验；段落按中文语感重新划定。
- **流程概述**：分块 → 逐句翻译 → 合并 → 断句 / 行宽校验 → 组装。
- **特有门禁**：无（分段方案与翻译结果在通用审核循环内确认）。
- **输出**：`*.srt`。

一句话：**有音视频 → `vocalign`；只有带时间码字幕 → `reflow2`；沿用老流程 → `reflow-redstone`；无时间码或要逐句规整 → `translate-redstone`。** 拿不准就让 Agent 按输入类型推荐。

## 日常维护

翻译过程中，新术语的登记及其索引更新由 Agent 自动完成。日常维护仅需在以下场景偶尔执行：

- **分拣新术语**：翻译确认的新译名由 Agent 写入 `knowledge/01_terminology/_uncategorized.csv`，可定期手工分拣至对应分类 CSV
- **更新索引**：向 `_repos/` 新增仓库、或知识库与术语表内容发生较大变动时，`indexes/` 下的对应索引不会自动更新，需手动触发（请 Agent 重新生成 `indexes/repos/` 与 `indexes/knowledge/`）
- **同步上游知识**：当 `_repos/` 下的知识仓库有更新时，运行 `git submodule update --remote` 拉取
- **清理临时产物**：`.cache/`（爬取缓存）与 `_work/`（翻译中间产物）均为临时文件，如需清理可手动删除（项目禁止自动删除）

> 知识按来源分为三类：**人工维护知识库**（`knowledge/`，译名标准，Git 追踪）、**脚本生成与抓取缓存**（`.cache/`，含官方词汇表、Wiki 页面、社区资料）、**外部仓库**（`_repos/`，只读 submodule 引用）。翻译术语以 `knowledge/` 与 `.cache/` 为据，外部仓库内容经索引定位后参考。其中 **storage-archive**（`_repos/storage-archive/`）为 Storage-Catalog 社区的**存储科技**术语词典（sparse 检出 `dictionary/`，116 条术语含定义/缩写），用 `scripts/dictionary_lookup.py` 查询（`query`/`scan`/`list`），详见 `indexes/repos/storage-archive.md`。

## 相关文档

- [`docs/SETUP.md`](docs/SETUP.md) — 环境配置与部署（初始化 / 请求身份 / 模型 / 窗口 / MCP）
- [`docs/EDITOR_COMPAT.md`](docs/EDITOR_COMPAT.md) — 编辑器兼容性
- [`docs/SETUP.md`](docs/SETUP.md) — 环境配置与部署
- [`docs/SOURCE_COVERAGE.md`](docs/SOURCE_COVERAGE.md) — 数据源覆盖范围
- [`docs/WIKI_CACHE_FORMAT.md`](docs/WIKI_CACHE_FORMAT.md) — Wiki 缓存格式
- [`AGENTS.md`](AGENTS.md) — 项目级 Agent 指令

## 目录结构

各目录用途与产物归属约定见 [`docs/PROJECT_STRUCTURE.md`](docs/PROJECT_STRUCTURE.md)。

## 引用与致谢

本项目基于以下开源项目构建，在此向所有作者与维护者致谢：

### 知识源

- [techmc-wiki/articles](https://github.com/techmc-wiki/articles)
- [TechMC-Glossary/TechMC-Glossary](https://github.com/TechMC-Glossary/TechMC-Glossary)
- [lovexyn0827/Discovering-Minecraft](https://github.com/lovexyn0827/Discovering-Minecraft)
- [Youmiel/ArticlesAndDevNotes](https://github.com/Youmiel/ArticlesAndDevNotes)
- [TechMCDocs/pages](https://github.com/TechMCDocs/pages)
- [acaciachan/tree-hole](https://github.com/acaciachan/tree-hole)
- [Storage-Catalog/Archive](https://github.com/Storage-Catalog/Archive)

### 工具

- [op7418/Humanizer-zh](https://github.com/op7418/Humanizer-zh)
- [L3-N0X/Minecraft-Wiki-MCP](https://github.com/L3-N0X/Minecraft-Wiki-MCP)
- [rice-awa/mc-wiki-mcp-pypi](https://github.com/rice-awa/mc-wiki-mcp-pypi)

### 核心理念

- [llm-wiki](https://gist.github.com/442a6bf555914893e9891c11519de94f)
