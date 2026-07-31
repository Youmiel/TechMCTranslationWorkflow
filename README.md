# Minecraft红石技术视频字幕翻译辅助系统

基于渐进式轻量级方案的翻译辅助工作流。核心理念：

- **资产即代码** — 知识以 Markdown 文件存在，Git 追踪
- **缓存不入库** — 爬取内容本地临时副本，永不发布
- **三级检索路由** — 核心库 → 本地缓存 → 联网爬取

## 快速开始

1. 用 VS Code / Claude Code 打开本目录
2. 首次使用运行 `python scripts/setup_editors.py`（适配 Claude Code 等编辑器）
3. Agent 自动加载 Skill，直接输入要翻译的内容即可

> 编辑器兼容详情见 [`docs/EDITOR_COMPAT.md`](docs/EDITOR_COMPAT.md)

## 目录结构

```
├── .vscode/
│   ├── mcp.json                # MCP 配置（生效中，非 uv 直调）
│   ├── mcp.template.json       # MCP 配置模板（非 uv）
│   └── mcp.uv-template.json    # MCP 配置模板（标准 uv）
├── docs/
│   └── MCP_DEPLOYMENT.md       # MCP Wiki 工具部署指南
├── knowledge/                  # 核心知识库（Git 追踪）
│   ├── 01_terminology/         # 术语表   
│   │   └── _example.csv        # 术语 CSV 表头模板
│   └── .../
├── .cache/                     # 本地缓存（Git 忽略）
├── scripts/                    # 辅助脚本
└── AGENTS.md                   # 项目级 Agent 指令
```
