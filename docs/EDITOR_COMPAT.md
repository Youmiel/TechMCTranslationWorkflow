# 编辑器兼容性

本项目核心资产（Skill、指令）存放在 `.github/` 下，通过少量适配即可在不同编辑器中工作。

## 支持的编辑器

| 编辑器 | Skill 支持 | 指令文件 | 适配方式 |
|--------|-----------|----------|----------|
| **VS Code Copilot** | ✅ `.github/skills/` | `AGENTS.md` | 原生支持，无需额外配置 |
| **Claude Code** | ✅ `.claude/skills/` | `CLAUDE.md` | 运行 `python scripts/setup_editors.py` 创建链接 + 同步 |
| **Cursor** | ❌ 无 Skill 系统 | `AGENTS.md` | 自动读取，无需配置 |
| **GitHub Copilot (web)** | ❌ | `.github/copilot-instructions.md` | 按需手动创建 |

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

1. 在 `scripts/setup_editors.py` 中添加对应小节
2. 更新本文档的支持列表
3. 运行 `python scripts/setup_editors.py --force` 测试
