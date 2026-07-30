# MCP Wiki 工具部署指南

两个 Minecraft Wiki MCP 工具的非 `uv` 本地部署方式汇总。

## 前置说明

假如 `uv` 标准调用方式无效，可以使用 `venv` + `pip` 进行本地部署。

## MCP 配置模板

项目提供两份 MCP 配置参考：

| 文件 | 适用场景 |
|------|----------|
| `.vscode/mcp.uv.json` | 标准 uv 方式 |
| `.vscode/mcp.non-uv.json` | 非 uv，直接调用 venv |

## 一、mc-wiki-fetch-mcp（自定义 API）

- **仓库**：`https://github.com/rice-awa/mc-wiki-mcp-pypi`
- **后端依赖**：`https://mcwiki.rice-awa.top`（自定义 Wiki API）

### 安装

```powershell
cd mc-wiki-mcp-pypi

# 补丁：pyproject.toml 中 mcp 依赖须加 <2.0.0 上限（mcp 2.0 移除了 fastmcp）
# 将 "mcp>=1.12.3" 改为 "mcp>=1.12.3,<2.0.0"（已修改则跳过）

python -m venv .venv
.\.venv\Scripts\activate.ps1
pip install -e .
```

### 手动测试

```powershell
# HTTP 模式
.\.venv\Scripts\activate.ps1
mc-wiki-fetch-mcp --transport http --port 3001
# 端点：http://127.0.0.1:3001/mcp
```

### MCP 客户端配置

```json
{
  "mc-wiki": {
    "command": "/path/to/venv/mc-wiki-fetch-mcp.exe",
    "cwd": "/path/to/mc-wiki-mcp-pypi",
  }
}
```

工具：`search_wiki`、`get_page`、`check_page_exists`、`check_health`、`list_namespaces`

---

## 二、Minecraft-Wiki-MCP（MediaWiki API 直连）

- **仓库**：`https://github.com/L3-N0X/Minecraft-Wiki-MCP`
- **后端依赖**：`https://zh.minecraft.wiki/api.php`（官方 MediaWiki API）

### 安装

```powershell
cd Minecraft-Wiki-MCP
python -m venv .venv
.\.venv\Scripts\activate.ps1
pip install -e .
```

### 手动测试

```powershell
# HTTP 模式（端口 8192）
.\.venv\Scripts\activate.ps1
minecraft-wiki-mcp.exe --transport streamable-http --port 8192
# 端点：http://127.0.0.1:8192/mcp
```

### MCP 客户端配置

```json
{
  "minecraft-wiki": {
    "command": "/path/to/venv/minecraft-wiki-mcp.exe",
    "cwd": "/path/to/Minecraft-Wiki-MCP",
    "disabled": true,
  }
}
```

工具：`minecraft_wiki_search`、`minecraft_wiki_get_page`、`minecraft_wiki_get_section`、`minecraft_wiki_get_categories`、`minecraft_wiki_get_category_members`、`minecraft_wiki_resolve_redirect`


