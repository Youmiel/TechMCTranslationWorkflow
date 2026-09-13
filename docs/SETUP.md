# 环境配置与部署

让项目在你的机器与编辑器上跑起来的全部配置、部署与适配步骤。编辑器差异（agent 定义迁移、派发入口映射）另见 [EDITOR_COMPAT](EDITOR_COMPAT.md)。

## 初始化

```bash
# 安装依赖
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

## 配置项总览

`configs/` 下均为**本地个性化配置**（不入库，因人而异），模板见 [`examples/configs/`](examples/configs/)：

| 配置 | 文件 | 何时需要 |
|------|------|----------|
| [请求身份](#请求身份) | `configs/request_identity.yaml` | 建议确认（非 git clone 获取、或想用邮箱/站点） |
| [执行型 subagent 模型](#执行型-subagent-模型) | `configs/subagent_model.yaml` | 派发 subagent 前**必填** |
| [上下文窗口](#上下文窗口与分块比例) | `configs/context_window.json` | 换用窗口不同的模型时 |
| [MCP Wiki 工具](#mcp-wiki-工具可选) | `.vscode/mcp.json` 等 | 可选，提升查证质量 |
| 编辑器适配 | — | 用非 VS Code 编辑器时，见 [EDITOR_COMPAT](EDITOR_COMPAT.md) |

## 请求身份

抓取 Minecraft Wiki 与 Mojang 资源时，脚本会发送带联系方式的 User-Agent。

### 为什么需要配置

[Wikimedia 官方 UA 政策](https://foundation.wikimedia.org/wiki/Policy:User-Agent_policy)要求脚本的 UA **必须包含可联系到操作者的方式**（邮箱 / 站点 / 仓库 URL），否则可能被 **403 拒绝或静默封禁**——默认值 `python-urllib` / `python-requests` 明确在拒绝之列。

本项目**不内置作者的联系方式**：若沿用作者的仓库地址，所有 clone / fork 用户的请求都会以原作者名义发出，一旦有人滥用（高频抓取），被归因的是原作者。你必须提供**自己的**联系方式。

### 怎么配置

**通常无需配置**——脚本按以下优先级自动取值（实现见 `scripts/request_identity.py`）：

1. 环境变量 `TCTW_CONTACT`（临时覆盖，如 CI）
2. `configs/request_identity.yaml` 的 `contact`
3. **git remote 探测**——clone / fork 后 remote 天然是你自己的仓库
4. 占位符 `<PROJECT_URL>`（并在 stderr 告警）

即：**通过 `git clone` / fork 获取本项目时，第 3 步会自动取到你的仓库地址，开箱即可用**。

以下情形需手动配置（复制模板 [examples/configs/request_identity.yaml](examples/configs/request_identity.yaml) 到 `configs/` 后填写）：

- 以 zip 下载而非 git clone（无 git remote）
- 想让 UA 指向邮箱或个人站点而非仓库
- 项目放在无 git 环境的共享机器上

```yaml
# configs/request_identity.yaml
contact: "you@example.com"
```

### 验证

```powershell
python scripts/request_identity.py
# contact  = https://github.com/<your-name>/<your-repo>
# UA       = TechMCTranslationWorkflow/1.0 (https://github.com/<your-name>/<your-repo>)
```

UA 由 `scripts/fetch_wiki.py`、`scripts/mojang_glossary/` 共用；未配置且无 git remote 时会打印告警并暂用占位符。

## 执行型 subagent 模型

执行型 subagent（`reflow-worker`，承担补标点 / 翻译 / 分句等一次性产出任务）需使用**无思考模型**。模型名**因人而异、脚本无法探测**，须由使用者填写：

```yaml
# configs/subagent_model.yaml
execution_model: "<你的 no-think 模型名>"
```

模板见 [examples/configs/subagent_model.yaml](examples/configs/subagent_model.yaml)。

- **因人而异**：按你当前编辑器里可用的模型名填写（VS Code：模型选择器中的名称；Claude Code：模型标识；等）
- **所有 skill / 文档不硬编码模型名**
- Agent 派发 `reflow-worker` 时**必须读取本文件，把 `execution_model` 的值「照原样」填入派发参数**（逐字复用，不得改动 / 推断 / 凭记忆臆造；文件缺失或未配置 → 停下请使用者填写）
- 各编辑器的模型指定方式（派发参数 / agent frontmatter）见 [EDITOR_COMPAT#各编辑器派发 subagent 命令表](EDITOR_COMPAT.md#各编辑器派发-subagent-命令表)

> **Copilot 特例标注（仅本机适用）**：LLM API 配置（VS Code `chatLanguageModels.json`，BYOK 注册）**不随仓库分发**，故下述仅适用于本机 VS Code Copilot + BYOK 场景。
> - Copilot 不透传 `thinking: disabled`（chat-completions 只认 `temperature` / `top_p`）
> - 且 DeepSeek 无非思考模型
> - 故 `execution_model` 实际运行的是 **`reasoning_effort: low`（最小思考量）**——Copilot 不支持传递 disabled 情况下的**权宜办法**，并非真正关闭思考
> - 「无思考模型」是执行型纪律的**称呼**（配合 `thinking: false` 隐藏思考 UI），不代表模型零思考
>
> 其它编辑器 / 其它模型配置无此限制，按各自方式填真正 no-think 模型即可。

## 上下文窗口与分块比例

`configs/context_window.json`——描述**你所用的模型容量**，分块阈值计算的基准（决定「何时把长视频拆给多个 subagent」）。

**必须按你实际使用的模型填写**：不同模型的窗口与单次输出上限差异很大，**没有通用默认值**（文件缺失时脚本按内置兜底值估算并告警，结果可能偏差较大）。

| 字段 | 含义 |
|------|------|
| `context_length` | 模型**实际有效**窗口上限（非标称值；输入+输出共享） |
| `max_output` | 模型单次生成最大输出 |
| `split_ratio` | 输入阈值比例（窗口 × 该值 = 单块输入材料上限，宁低勿高） |
| `output_ratio` | 输出阈值比例（max_output × 该值 = 单块最大输出上限，留余量） |
| `amplification` | 最重环节（分句）预测放大倍数 |

- 模板：[examples/configs/context_window.json](examples/configs/context_window.json)（**模板内数值仅为填写格式示例，需按你的模型替换**）
- 字段语义 / 算法推导 / 变更同步要求见 [PRODUCT_FORMATS#configscontext_windowjson](PRODUCT_FORMATS.md#configscontext_windowjson)（权威）

## MCP Wiki 工具（可选）

两个 Minecraft Wiki MCP 工具的本地部署。未配置时 Agent 自动降级至脚本或浏览器方案，查证可靠度相对较低。

> 推荐使用 `uv` 标准调用方式；若 `uv` 无效，可用 `venv` + `pip` 本地部署（见各节安装步骤）。
> 编辑器适配另见 [EDITOR_COMPAT](EDITOR_COMPAT.md)。

### 配置模板

项目提供 4 份 MCP 配置参考（位于 [`examples/`](examples/)，复制内容到对应位置并替换路径即可）：

| 文件 | 格式 | 适用场景 |
|------|------|----------|
| `mcp.vscode.json` | VS Code `servers`（uv） | VS Code / GitHub Copilot，标准 uv 方式 |
| `mcp.vscode.non-uv.json` | VS Code `servers`（非 uv） | VS Code / GitHub Copilot，直接调用 venv |
| `mcp.claude.json` | Claude `mcpServers`（uv） | Claude Desktop / Claude Code / Cursor / Windsurf / Cline |
| `mcp.zed.json` | Zed `mcp_servers`（uv） | Zed |

> 格式差异：VS Code 的 `.vscode/mcp.json` 支持 JSONC（可用 `//` 注释）；Claude / Cursor / Zed 按严格 JSON 解析，模板中不含注释。MCP 服务器名称（`servers` / `mcpServers` 下的键）可自由命名，建议使用项目相关名称。

### mc-wiki-fetch-mcp（自定义 API）

- **仓库**：`https://github.com/rice-awa/mc-wiki-mcp-pypi`
- **后端依赖**：`https://mcwiki.rice-awa.top`（自定义 Wiki API）
- **工具**：`search_wiki`、`get_page`、`check_page_exists`、`check_health`、`list_namespaces`

```powershell
cd mc-wiki-mcp-pypi

# 补丁：pyproject.toml 中 mcp 依赖须加 <2.0.0 上限（mcp 2.0 移除了 fastmcp）
# 将 "mcp>=1.12.3" 改为 "mcp>=1.12.3,<2.0.0"（已修改则跳过）

python -m venv .venv
.\.venv\Scripts\activate.ps1
pip install -e .

# 手动测试（HTTP 模式，端点 http://127.0.0.1:3001/mcp）
mc-wiki-fetch-mcp --transport http --port 3001
```

### Minecraft-Wiki-MCP（MediaWiki API 直连）

- **仓库**：`https://github.com/L3-N0X/Minecraft-Wiki-MCP`
- **后端依赖**：`https://zh.minecraft.wiki/api.php`（官方 MediaWiki API）
- **工具**：`minecraft_wiki_search`、`minecraft_wiki_get_page`、`minecraft_wiki_get_section`、`minecraft_wiki_get_categories`、`minecraft_wiki_get_category_members`、`minecraft_wiki_resolve_redirect`

```powershell
cd Minecraft-Wiki-MCP
python -m venv .venv
.\.venv\Scripts\activate.ps1
pip install -e .

# 手动测试（HTTP 模式，端点 http://127.0.0.1:8192/mcp）
minecraft-wiki-mcp.exe --transport streamable-http --port 8192
```

## 相关文档

- [EDITOR_COMPAT](EDITOR_COMPAT.md) — 编辑器兼容性、agent 定义迁移
- [PRODUCT_FORMATS](PRODUCT_FORMATS.md) — 产物格式与配置项语义
- [PROJECT_STRUCTURE](PROJECT_STRUCTURE.md) — 目录用途与产物归属
