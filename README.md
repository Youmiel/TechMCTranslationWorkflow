# Minecraft 红石技术视频字幕翻译辅助工作流

基于渐进式轻量级方案的红石技术视频字幕翻译辅助工作流，用于将英文 Minecraft 红石技术视频字幕高质量翻译为简体中文。

使用流程为：初始化环境 → 将字幕放入 `_input/` → 由 Agent 执行翻译 → 在 `_output/` 获取结果。术语查证、知识补齐与译名统一由 Skill 自动完成；用户仅在术语清单确认与翻译审核等关键节点参与确认。

本项目遵循 [llm-wiki](https://gist.github.com/442a6bf555914893e9891c11519de94f) 的核心理念：由 Agent 增量构建并持续维护一个持久的知识库，而非在每次提问时从原始文档重新检索。知识在摄入时编译一次并持续更新，交叉引用与矛盾标记预先建立，知识库随使用不断累积。用户负责资料筛选与提问，Agent 负责归纳、交叉引用与记录维护。


## 初始化

```bash
# 安装依赖
pip install -r requirements.txt

# 初始化 submodule（知识仓库 + humanizer-zh Skill）
git submodule update --init --recursive

# 编辑器适配（为 Claude Code 等编辑器创建 Skill 链接）
python scripts/setup_editors.py
```

- 编辑器兼容性见 [`docs/EDITOR_COMPAT.md`](docs/EDITOR_COMPAT.md)

### （可选）配置 MCP Wiki 工具

联网查证术语依赖 MCP Wiki 工具，部署步骤见 [`docs/MCP_DEPLOYMENT.md`](docs/MCP_DEPLOYMENT.md)。未配置时，Agent 将自动降级至脚本或浏览器方案，查证可靠度相对较低。

## Skills 一览

以下为面向用户的 Skill（翻译与维护时由 Agent 自动加载，无需手动启用）：

- `translate-redstone`: 方案一 - 逐句翻译视频字幕 
- `reflow-redstone`: 方案二 - 语义回填重排字幕
- `maintain-knowledge`: 维护知识库与术语 
- [`humanizer-zh`](./skills/humanizer-zh): 去除翻译腔 / AI 味（可选） 

## 翻译视频字幕

1. 使用 **VS Code / Claude Code** 打开本项目目录
2. 将待翻译字幕放入 **`_input/`**
3. 向 Agent 发起翻译指令，如：*"翻译 `_input/<文件名>.srt`"*（或描述视频内容）；拿不准用哪个工作流时，让 Agent 按字幕类型推荐（见下"两个工作流怎么选"）

翻译流程由 Agent 驱动，大部分环节自动完成，**只在以下两处暂停并等待用户确认**：

1. **翻译阶段前（01/02 确认）**：ASR 修正字幕 + 术语清单（无法确定的词条附候选译名、依据与字幕时间戳）交用户确认，确认后才进入翻译（Agent 不擅自跨阶段）
2. **翻译结果审核**：提交翻译结果，可多轮修改，确认后定稿；如需调整分段 / 回填方案，Agent 会同步征求你的意见

确认定稿后，结果写入 **`_output/`**，默认双语对照（原文一行 + 中文一行），文件名与输入一致。

> 可选：如需译文更自然，可要求 Agent 使用 `humanizer-zh` 去除翻译腔。
> 若流程中途中断（如会话关闭），重新发起即可；Agent 会从 `_work/<视频名>/` 的中间产物自动续跑。

## 工作流区别介绍

`translate-redstone`: 
- 适用字幕： 任意字幕（无时间码纯文本也可）
- 处理方式： 先断句、再逐句翻译
- 产物时间轴： 按中文语感重新分段，段落规整
- 行宽 / 观感： 需人工把关行宽
- 输出文件后缀： `*.srt`

`reflow-redstone`: 
- 适用字幕： 带时间码的原字幕（SRT）
- 处理方式： 整段翻译后，贴合原视频时间轴重排字幕
- 产物时间轴： 尽量贴合原视频节奏（在原轴基础上合并/切分）
- 行宽 / 观感： 脚本自动保证单条行宽与时长合理
- 输出文件后缀： `*.reflow.srt`

一句话：**要段落规整、逐句清晰 → 选 `translate-redstone`；要尽量贴合原视频节奏、字幕跟着原轴走 → 选 `reflow-redstone`。** 拿不准就让 Agent 按字幕类型推荐。

## 日常维护

翻译过程中，新术语的登记及其索引更新由 Agent 自动完成。日常维护仅需在以下场景偶尔执行：

- **分拣新术语**：翻译确认的新译名由 Agent 写入 `knowledge/01_terminology/_uncategorized.csv`，可定期手工分拣至对应分类 CSV
- **更新索引**：向 `_repos/` 新增仓库、或知识库与术语表内容发生较大变动时，`indexes/` 下的对应索引不会自动更新，需手动触发（请 Agent 重新生成 `indexes/repos/` 与 `indexes/knowledge/`）
- **同步上游知识**：当 `_repos/` 下的知识仓库有更新时，运行 `git submodule update --remote` 拉取
- **清理临时产物**：`.cache/`（爬取缓存）与 `_work/`（翻译中间产物）均为临时文件，如需清理可手动删除（项目禁止自动删除）

> 知识按来源分为三类：**人工维护知识库**（`knowledge/`，译名标准，Git 追踪）、**脚本生成与抓取缓存**（`.cache/`，含官方词汇表、Wiki 页面、社区资料）、**外部仓库**（`_repos/`，只读 submodule 引用）。翻译术语以 `knowledge/` 与 `.cache/` 为据，外部仓库内容经索引定位后参考。

## 相关文档

- [`docs/EDITOR_COMPAT.md`](docs/EDITOR_COMPAT.md) — 编辑器兼容性
- [`docs/MCP_DEPLOYMENT.md`](docs/MCP_DEPLOYMENT.md) — MCP Wiki 工具部署
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

### 工具

- [op7418/Humanizer-zh](https://github.com/op7418/Humanizer-zh)
- [L3-N0X/Minecraft-Wiki-MCP](https://github.com/L3-N0X/Minecraft-Wiki-MCP)
- [rice-awa/mc-wiki-mcp-pypi](https://github.com/rice-awa/mc-wiki-mcp-pypi)

### 核心理念

- [llm-wiki](https://gist.github.com/442a6bf555914893e9891c11519de94f)
