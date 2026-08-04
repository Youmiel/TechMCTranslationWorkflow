# 项目结构指南

> 本文档是 `Project_Main/`（核心工作流项目）的**目录用途与产物归属**权威说明。
> Agent 在处理或产出文件时，按本文档确定文件该放在哪里。
> 相关：脚本清单见 [`scripts/README.md`](../scripts/README.md)；翻译目录约定细节见 `translate-redstone` Skill；分步隔离见 [`PIPELINE_ISOLATION.md`](PIPELINE_ISOLATION.md)。

## 目录总览

```
Project_Main/
├── _input/              # 待翻译字幕（SRT / transcript），Git 忽略
├── _work/               # 翻译中间产物（断点续翻），Git 忽略；每视频一文件夹
├── _output/             # 翻译输出（默认双语对照），Git 忽略
├── ref_translations/    # 参考译例，供 Agent 模仿翻译风格

├── .cache/              # 脚本生成缓存（glossary/wiki/社区资料），Git 忽略
├── _repos/              # 外部知识仓库（git submodule 只读引用）
├── knowledge/           # 人工维护核心知识（译名标准），Git 追踪
├── indexes/             # 检索索引（knowledge/ + repos/），Git 追踪

├── .github/             # Skills 定义（skills/）+ Agent 经验（experience/）
├── .vscode/             # 编辑器配置（mcp.json 等）
├── scripts/             # 正式辅助脚本（glossary_*/srt_*/独立工具）
├── configs/             # 配置（当前空）
├── docs/                # 项目文档
└── AGENTS.md            # 项目级 Agent 指令
```

## 翻译工作区（Git 忽略）

| 目录 | 用途 | 产物归属 |
|------|------|----------|
| `_input/` | 待翻译字幕入口。用户放入，Agent 读取 | 待翻译的 SRT / transcript 文件 |
| `_work/<视频名>/` | 翻译中间产物，断点续翻依据 | ASR 修正稿 `01_subtitle_asr_fixed.srt`、术语清单 `02_terms.md`、分段方案 `03_segments.md`、翻译草稿 `04_translation_draft.srt`；**视频专属的一次性脚本**（如 `_verify_draft.py`） |
| `_output/` | 翻译最终输出 | 定稿字幕（默认双语对照），文件名与输入一致 |
| `ref_translations/` | 参考译例 | 供 Agent 模仿风格的优质译文样本 |

## 缓存与数据（临时 / 只读）

| 目录 | 用途 | 产物归属 |
|------|------|----------|
| `.cache/` | 脚本生成缓存，Git 忽略，可清理 | `glossary_split.py` 拆分的分类 CSV（`glossary/`）、Mojang 官方词汇表（`mojang/`）、Wiki 抓取页、社区资料等 |
| `_repos/` | 外部知识仓库 | git submodule（只读引用，不直接修改） |

## 知识资产（Git 追踪）

| 目录 | 用途 | 产物归属 |
|------|------|----------|
| `knowledge/01_terminology/` | 术语译名标准 | 分类 CSV：`common.csv`、`game_system.csv`、`proper_nouns.csv`、`redstone_concepts.csv`、`storage.csv`；**新译名暂存 `_uncategorized.csv`**（待人工分拣） |
| `knowledge/02_mechanic/` | 机制知识 | 红石机制说明 md |
| `indexes/knowledge/` | 知识库检索索引 | 由维护流程生成，Git 追踪 |
| `indexes/repos/` | 外部仓库检索索引 | 每仓库一 md，头部记录上游 commit |

## 工程结构

| 目录 | 用途 | 产物归属 |
|------|------|----------|
| `.github/skills/` | Skill 定义 | 工作流/机制说明 SKILL.md（如 translate-redstone、segment-subtitles、wiki-tools） |
| `.github/experience/` | Agent 运行经验 | `asr_fixes.md`、`coverage_log.md`、`glossary_categories.yaml`、`trap_words.md` |
| `scripts/` | 正式辅助脚本 | **通用、可复用、经校验**的脚本（`glossary_*`、`srt_*`、`fetch_wiki.py`、`refresh_cache.py`、`check_index_stale.py`、`setup_editors.py`、`split_subtitles.py` 等）；一次性脚本不在此列 |
| `configs/` | 配置 | 当前为空 |
| `docs/` | 项目文档 | 本文档及 PIPELINE_ISOLATION / EDITOR_COMPAT / MCP_DEPLOYMENT / SOURCE_COVERAGE / WIKI_CACHE_FORMAT |

## 产物归属速查

| 产物类型 | 归属位置 |
|----------|----------|
| 待翻译字幕 | `_input/` |
| ASR 修正稿 / 术语清单 / 分段方案 / 翻译草稿 | `_work/<视频名>/`（`01_`/`02_`/`03_`/`04_`） |
| 翻译最终输出 | `_output/` |
| 视频专属的一次性脚本 | `_work/<视频名>/` |
| 通用可复用脚本 | `scripts/` |
| 新术语译名（待分拣） | `knowledge/01_terminology/_uncategorized.csv` |
| 分类术语表 | `knowledge/01_terminology/<类别>.csv` |
| 机制知识 | `knowledge/02_mechanic/` |
| 爬取/生成缓存 | `.cache/` |
| 检索索引 | `indexes/knowledge/`、`indexes/repos/` |
| 参考译例 | `ref_translations/` |
| Agent 运行经验 | `.github/experience/` |
| Skill 文档 | `.github/skills/<skill>/SKILL.md` |
