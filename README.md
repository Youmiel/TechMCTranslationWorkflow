# Minecraft 红石技术视频字幕翻译辅助系统

基于渐进式轻量级方案的红石技术视频字幕翻译辅助工作流，用于将英文 Minecraft 红石技术视频字幕高质量翻译为简体中文。

使用流程为：初始化环境 → 将字幕放入 `_input/` → 由 Agent 执行翻译 → 在 `_output/` 获取结果。术语查证、知识补齐与译名统一由 Skill 自动完成；用户仅在术语清单确认与翻译审核等关键节点参与确认。

本项目遵循 [llm-wiki](https://gist.github.com/442a6bf555914893e9891c11519de94f) 的核心理念：由 Agent 增量构建并持续维护一个持久的知识库，而非在每次提问时从原始文档重新检索。知识在摄入时编译一次并持续更新，交叉引用与矛盾标记预先建立，知识库随使用不断累积。用户负责资料筛选与提问，Agent 负责归纳、交叉引用与记录维护。


## 初始化

```bash
# 1. 进入项目目录
cd Project_Main

# 2. 安装依赖
pip install -r requirements.txt

# 3. 初始化 submodule（知识仓库 + humanizer-zh Skill）
git submodule update --init --recursive

# 4. 编辑器适配（为 Claude Code 等编辑器创建 Skill 链接）
python scripts/setup_editors.py
```

- 编辑器兼容性见 [`docs/EDITOR_COMPAT.md`](docs/EDITOR_COMPAT.md)

### （可选）配置 MCP Wiki 工具

联网查证术语依赖 MCP Wiki 工具，部署步骤见 [`docs/MCP_DEPLOYMENT.md`](docs/MCP_DEPLOYMENT.md)。未配置时，Agent 将自动降级至脚本或浏览器方案，查证可靠度相对较低。

## Skills 一览

以下为面向用户的 Skill（翻译与维护时由 Agent 自动加载，无需手动启用）：

- `translate-redstone`: 翻译视频字幕 
- `maintain-knowledge`: 维护知识库与术语 
- [`humanizer-zh`](./skills/humanizer-zh): 去除翻译腔 / AI 味（可选） 

## 翻译视频字幕（`translate-redstone`）

1. 使用 **VS Code / Claude Code** 打开本项目目录
2. 将待翻译字幕放入 **`_input/`**
3. 向 Agent 发起翻译指令，如：*“翻译 `_input/<文件名>.srt`”*（或描述视频内容）

翻译流程由 Agent 驱动，过程中在以下节点暂停并等待用户确认：

1. **扫描术语**：通读字幕，识别红石术语与专有名词，从本地知识库、官方词汇表与 Wiki 逐级查证译名
2. **术语清单确认**：向用户提交术语译名表——无法确定的词条附候选译名、依据与字幕时间戳。确认或修改后，译名方可定稿并自动登记入知识库
3. **分段方案审核**：正式翻译前提交合并/断句的分段方案，由用户确认
4. **翻译与断句**：确认后按中文语感逐句翻译，并调整字幕行
5. **翻译结果审核**：向用户提交翻译结果，可多轮修改，确认后定稿
6. **输出结果**：写入 **`_output/`**，默认双语对照（原文一行 + 中文一行），文件名与输入一致

> 可选：如需译文更自然，可要求 Agent 使用 `humanizer-zh` 去除翻译腔。
> 若流程中途中断（如会话关闭），重新发起即可；Agent 会从 `_work/<视频名>/` 的中间产物自动续翻。

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

```
Project_Main/
# 翻译工作区
├── _input/              # 待翻译字幕（SRT / transcript），Git 忽略
├── _work/               # 翻译中间产物（断点续翻），Git 忽略
├── _output/             # 翻译输出（默认双语对照），Git 忽略
└── ref_translations/    # 参考译例，供 Agent 模仿翻译风格

├── .cache/              # 脚本生成缓存：含官方词汇表、Wiki 等，Git 忽略
├── _repos/              # 外部仓库（submodule）：只读引用
├── knowledge/           # 人工维护知识：译名标准，Git 追踪
└── indexes/             # 检索索引，Git 追踪

├── .github/             # Skills 定义与 Agent 经验数据
├── .vscode/             # 编辑器配置（MCP 等）
├── scripts/             # 辅助脚本
├── configs/             # 配置
├── docs/                # 文档
└── AGENTS.md            # 项目级 Agent 指令
```

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
