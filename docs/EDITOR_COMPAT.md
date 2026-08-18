# 编辑器兼容性

本项目核心资产（Skill、指令、agent 定义）存放在 `.github/` 下，通过**自动适配（脚本）+ 手动配置（使用者自己 / 配合自己的 agent）**两部分在不同编辑器中工作。

## 支持的编辑器

| 编辑器 | Skill 支持 | 指令文件 | 适配方式 |
|--------|-----------|----------|----------|
| **VS Code Copilot** | ✅ `.github/skills/` | `AGENTS.md` | 原生支持，无需额外配置 |
| **Claude Code** | ✅ `.claude/skills/` | `CLAUDE.md` | 运行 `python scripts/setup_editors.py` 创建链接 + 同步 |
| **Cursor** | ❌ 无 Skill 系统 | `AGENTS.md` | 自动读取，无需配置 |
| **GitHub Copilot (web)** | ❌ | `.github/copilot-instructions.md` | 按需手动创建 |

## 自动适配（脚本能完成的）

`python scripts/setup_editors.py` 只做**文件链接/同步类**适配：

- `.claude/skills/ → .github/skills/`（符号链接 / junction / 复制，含 humanizer-zh）
- `CLAUDE.md ← AGENTS.md`（生成，文件头注明来源）

## 手动配置（脚本无法完成，需使用者自己 / 配合自己的 agent）

以下**没有脚本**，须按编辑器手工配置（依赖各编辑器私有的 agent 机制 / 模型标识 / 派发入口，无法统一自动化）：

| 配置项 | 脚本能否处理 | 说明 |
|--------|-------------|------|
| **agent 定义适配**（reflow-worker） | ❌ | 脚本不生成各编辑器 agent 文件；迁移时按下方「agent 定义适配」手动 adapt |
| **派发 subagent 入口** | ❌ | 各编辑器派发命令/工具名不同（见「各编辑器派发 subagent 命令表」），由**使用者自己的 agent** 按表执行 |
| **no-think 模型名**（execution_model） | ❌ | 因人而异、脚本无法探测；统一填 `configs/subagent_model.yaml`（见下「模型配置」） |
| **MCP 配置** | ❌ | `.vscode/mcp.json` 仅 VS Code；其它编辑器 mcp 配置格式不同，需自行对照其文档 |
| **agent 内模型字段** | ❌ | `reflow-worker.agent.md` 已**移除** `model` 硬编码，模型统一由「模型配置」+ 派发参数决定 |

### 模型配置（execution_model，单一事实源）

`configs/subagent_model.yaml` 的 `execution_model` 字段 = 执行型 subagent（reflow-worker 类）运行的 **no-think 模型名**。**因人而异**，按你当前编辑器里可用的模型名填写（VS Code：模型选择器中的名称；Claude Code：模型标识；等）。**所有 skill / 文档不硬编码模型名**，派发时从该文件读取：

```yaml
# 执行型 subagent 运行的 no-think 模型名——因人而异，按你当前编辑器可用的模型名填写
# 脚本无法自动探测，见本文件 description / 本文档「手动配置」
execution_model: "<你的 no-think 模型名>"
```

## 各编辑器派发 subagent 命令表

派发 subagent 的**入口名称各编辑器不同**（并非都叫 `runSubagent`），且**不在任何 skill 中硬编码**——使用者自己的 agent 按本表调用（具体语法以各编辑器官方文档为准）：

| 编辑器 | 派发入口 / 工具 | agent 定义位置 | 模型指定方式 |
|--------|----------------|----------------|--------------|
| **VS Code / GitHub Copilot** | `runSubagent`（参数 `agentName` / `model`） | `.github/agents/*.agent.md` | `model` 参数（读 `configs/subagent_model.yaml`） |
| **Claude Code** | `Task` 工具（subagent 调用） | `.claude/agents/*.md` | agent frontmatter `model` |
| **Cursor** | agent 选择器 / 派发工具 | `.cursor/agents/*.md` | agent 定义内模型字段 |
| **Gemini CLI** | subagent 工具 | `.gemini/agents/*.md` | agent 定义内模型字段 |
| **其它** | 以官方文档为准 | 以官方文档为准 | 以官方文档为准 |

> 派发时若编辑器支持**调用时指定模型**，优先传 `configs/subagent_model.yaml` 的 `execution_model`；否则在 agent 定义 frontmatter 模型字段填入（见「agent 定义适配」模型行）。

## 约定文件机制（通用性说明）

项目约定层：**通用格式承载全部知识/流程**（`AGENTS.md` + `.github/skills/`），**执行型 agent 定义 = GitHub Copilot 格式单一权威**（`.github/agents/`），**系统提示词覆盖由 agent 承载**；迁移其它编辑器时从该格式 **adapt**。**所有编辑器相关操作细节（agent 定义文件 / 格式 / 派发入口 / 模型名 / adapt 步骤）集中在本文档，主逻辑 skill（`subagent-dispatch` 等）不承载编辑器适配，只表述「派发 `reflow-worker`，使用无思考模型」。**

- **通用格式（所有编辑器）**：`AGENTS.md`（多工具标准）+ `.github/skills/`（Agent Skills 开放格式）
- **执行型 agent（系统提示词覆盖，单一权威）**：`.github/agents/reflow-worker.agent.md`——正文即**系统提示词**，从根源替代宿主通用提示词（内联覆盖声明对抗系统层不可靠）；VS Code / Copilot 原生直接使用
- **内联兜底**：`subagent-dispatch` 纪律母版 #0 与 `.agent.md` **同源**，派发时随 prompt 整体追加——编辑器无 agent 机制 / 未 adapt 时的通用兜底（效果弱于系统提示词覆盖）
- **运行模型**：读 `configs/subagent_model.yaml` 的 `execution_model`（解除硬编码，见「模型配置」），派发时按「各编辑器派发 subagent 命令表」传入

### 执行型 agent 定义文件（reflow-worker）

所有说明性内容集中在本文档，**系统提示词（agent 正文）不塞注释**：

- **位置 / 格式**：`.github/agents/reflow-worker.agent.md`，GitHub Copilot `.agent.md` 格式（frontmatter `name` / `description` / `tools` / `user-invocable`；正文 = 系统提示词）
- **能力**：系统提示词覆盖——从根源替代宿主通用提示词（「创造性思考 / 探索工作区」等），内联覆盖声明对抗系统层不可靠
- **模型**：frontmatter **不写 `model`**（因人而异），统一读 `configs/subagent_model.yaml` 的 `execution_model`，派发时按编辑器方式传入；如需 agent 自带模型，个人自行在 frontmatter 填 `model`
- **兜底**：纪律母版 #0 与其同源，派发时随 prompt 整体追加（编辑器无 agent 机制 / 未 adapt 时起效）
- **迁移**：其它编辑器从该文件 adapt（见下方「agent 定义适配」）

### agent 定义适配（迁移其它编辑器）

从 `.github/agents/reflow-worker.agent.md`（GitHub Copilot 格式）adapt 到目标编辑器的 agent 定义，**正文（系统提示词）原样复用**：

| 字段/内容 | GitHub Copilot | 适配要点 |
|-----------|---------------|----------|
| 名称 | `name` | 映射为目标编辑器 agent 名（如 Claude Code 同名） |
| 用途说明 | `description` | 原样保留（发现面） |
| 工具白名单 | `tools` | 映射为目标编辑器工具集（read/edit/search 概念一致） |
| 运行模型 | `model`（本文件不写，见「执行型 agent 定义文件」） | 映射为目标编辑器模型字段；值读 `configs/subagent_model.yaml` 的 `execution_model` |
| 系统提示词 | 正文（frontmatter 后全部） | **原样复用**——即执行型纪律，与纪律母版 #0 同源 |
| 可见性 | `user-invocable: false` | 映射为目标编辑器"仅 subagent 调用" |

- **Claude Code**：`.claude/agents/reflow-worker.md`（frontmatter `name/description/tools/model` + 正文），字段与 Copilot 格式高度对应，正文可直接复用
- **其它编辑器**：文件位置/字段名以该编辑器官方 agent 定义文档为准；正文（系统提示词）始终原样复用

## 初始化

```bash
# 首次设置
python scripts/setup_editors.py

# 更新 CLAUDE.md（AGENTS.md 有变更后）
python scripts/setup_editors.py --force
```

## 架构说明

```
.github/                     # 源（所有编辑器共享）
├── skills/                  # Skill 定义
│   ├── translate-redstone/
│   ├── use-glossary/
│   ├── maintain-knowledge/
│   ├── index-repos/
│   └── humanizer-zh/        # 外部 submodule（去翻译腔，op7418/Humanizer-zh）
└── experience/              # Agent 经验数据
    ├── asr_fixes.md
    ├── coverage_log.md
    ├── source_experience.md
    ├── glossary_categories.yaml
    └── trap_words.md

.claude/skills/  ──(symlink)──→ .github/skills/     # 自动同步（含 humanizer-zh）
CLAUDE.md        ──(生成)────→ AGENTS.md              # 运行 setup 同步
```

> `humanizer-zh` 是 Git submodule（`git@github.com:op7418/Humanizer-zh.git`），
> 直接位于 `.github/skills/humanizer-zh/`，因此 VS Code 原生发现、Claude Code 经 junction 自动同步，无需额外适配。
> 更新：`git submodule update --remote .github/skills/humanizer-zh`

- `.claude/skills/` 使用**符号链接**（Windows 降级为 Junction 或复制），修改 `.github/skills/` 即刻生效
- `CLAUDE.md` 由脚本从 `AGENTS.md` 生成，在文件头注明来源，避免手动编辑

## 添加新编辑器

1. **自动部分**：在 `scripts/setup_editors.py` 中添加对应小节（skill 链接 / 指令同步），运行 `python scripts/setup_editors.py --force` 测试
2. **手动部分**：按本文档「各编辑器派发 subagent 命令表」补该编辑器派发入口 / agent 定义位置 / 模型指定方式
3. **手动部分**：核对「手动配置」清单——agent 定义适配、模型名（`configs/subagent_model.yaml`）、MCP 配置是否需该编辑器特殊处理
4. 更新本文档的支持列表
