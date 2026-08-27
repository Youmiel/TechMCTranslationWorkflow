# 引用仓库

通过 **Git Submodule** 管理。添加：`git submodule add <url> _repos/<name>`。

**同步第三方仓库（维护纪律）**：运行 `git submodule update`，把 submodule 拉到父仓库锁定的版本（新 clone 后需先初始化，直接用 `git submodule update --init`）。需要拉到上游最新并重新锁定版本时，用 `git submodule update --remote`。

> **sparse-checkout 特例（storage-archive）**：该仓库体积大（含向量索引大文件），用**非 cone 模式**只稀疏检出 `dictionary/` 目录（连根级大文件 `embeddings.json`/`hnsw.idx`/`persistent.idx` 也不检出）。此设置存于 submodule 的 git 目录（`Project_Main/.git/modules/_repos/storage-archive/`），`git submodule update` 不会清除（已验证）；若需重新启用：
> ```sh
> git -C _repos/storage-archive sparse-checkout init --no-cone
> git -C _repos/storage-archive sparse-checkout set /dictionary/
> ```

- [Storage-Catalog/Archive](https://github.com/Storage-Catalog/Archive)（storage-archive，仅稀疏检出 `dictionary/`；存储科技术语查询用 `scripts/dictionary_lookup.py`，见 `indexes/repos/storage-archive.md`）
- [acaciachan/tree-hole](https://github.com/acaciachan/tree-hole) 
- [lovexyn0827/Discovering-Minecraft](https://github.com/lovexyn0827/Discovering-Minecraft) 
- [techmc-wiki/articles](https://github.com/techmc-wiki/articles) 
- [TechMC-Glossary/TechMC-Glossary](https://github.com/TechMC-Glossary/TechMC-Glossary)
- [TechMCDocs/pages](https://github.com/TechMCDocs/pages)（Technical Minecraft Wiki 页面源）
- [Youmiel/ArticlesAndDevNotes](https://github.com/Youmiel/ArticlesAndDevNotes)
