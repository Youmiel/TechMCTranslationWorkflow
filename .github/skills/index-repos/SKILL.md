---
name: index-repos
description: 为 _repos/ 下的外部 Git 仓库生成内容索引文件（indexes/repos/）。新增 submodule 或上游仓库更新后使用。
---

# 外部仓库索引生成

为 `_repos/` 下的 Git Submodule 仓库生成内容索引。

## 输入

- `_repos/` 目录下的所有 submodule 仓库

## 输出

- `indexes/repos/<repo-name>.md` — 每个仓库一个索引文件
- `indexes/repos/_manifest.md` — 总清单

## 工作流程（处理顺序）

1. **判断哪些需更新** -> [更新判断](#更新判断submodule-commit-id)：`python scripts/check_index_stale.py`，取需更新的仓库列表
2. **逐仓库扫描**：读 `_repos/<repo>/` 内容，按 [扫描范围](#扫描范围) 过滤
3. **生成索引**：按 [索引格式](#索引格式) 与 [质量要求](#质量要求) 写 `indexes/repos/<repo>.md`（头部记录 生成时间 + 上游 commit）
4. **更新总清单**：写 `indexes/repos/_manifest.md` -> [_manifest.md 格式](#_manifestmd-格式)

> 每个需更新的仓库执行 2-3，全部完成后执行 4。

## 规则

### 更新判断（submodule commit id）

- **更新依据**：比较 `_repos/<repo>/` 当前 HEAD commit 与索引中记录的「上游 commit」——不一致即该仓库索引过期，需重新生成
- **固化脚本**：`python scripts/check_index_stale.py`（扫描全部 submodule，比对当前 commit 与索引记录 commit，报告哪些需更新；`--only <repo>` 只看单个）
- **commit id 记录位置**：每个仓库索引文件头部 `> 上游 commit：<hash>`（即 `indexes/repos/<repo>.md`），**不**写入 `_manifest.md`（manifest 只做总清单，不重复记录 commit）

### 扫描范围
- 只读 Markdown（`.md`）、纯文本（`.txt`）、CSV（`.csv`）文件
- 跳过图片（`.png` `.jpg` `.gif` `.svg` `.webp`）、二进制、Notebook（`.ipynb`）的内部细节，但记录其存在和文件名
- 跳过 `node_modules`、`.git` 等非内容目录

### 索引格式

每个仓库的索引文件按主题组织，**条目格式与版本标注统一按 `indexing-rules` Skill 执行**：

```markdown
# <仓库名> 内容索引

> 生成时间：YYYY-MM-DD
> 上游 commit：<hash>

## <主题分类1>

- **<文件路径>** — 一句话概要 [<适用版本>]
  - 关键词：tag1, tag2, tag3
```

### 质量要求
- 主题分类以仓库内已有的目录结构为基础，必要时可重组
- 对 CSV 术语表类文件，记录其字段结构和语言覆盖范围
- 优先记录红石、机械、技术机制相关内容
- 纯工具脚本、模组配置等内容可简略记录
- 不追求覆盖每个文件，重点覆盖"对翻译有价值的参考内容"

### _manifest.md 格式

```markdown
# 外部仓库索引清单

| 索引文件 | 仓库 | 协议 | 条目数 | 主题数 |
|----------|------|------|--------|--------|
```
