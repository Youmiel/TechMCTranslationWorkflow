# storage-archive 内容索引

> 生成时间：2026-08-28
> 上游 commit：ed04354123c4f37053bcf1c758154a77859ceddc
> 仓库：https://github.com/Storage-Catalog/Archive

Storage-Catalog 社区维护的**存储科技**术语词典（Discord 社区词条沉淀，submodule 仅稀疏检出 `dictionary/`）。

## 查询方式（权威）

- **不要**直接 grep / 手读 `entries/*.json`（结构化 JSON，主键是数字 id，无固定文件名语义）
- **用脚本** `python scripts/dictionary_lookup.py`（只读，数据源 `_repos/storage-archive/dictionary/`）：
  - `query <term>` — 按术语/缩写查完整定义（`query BUD` → Block Update Detector）
  - `scan <srt|chunk>` — 扫字幕找命中术语（输出 cue + 条目 id + 摘要）
  - `list [--brief]` — 列出全部术语（含同义词/缩写）
- 定位：**L2 社区源**（存储科技，社区层新增数据源），与 `glossary_lookup.py`（L1/L1.5/L2 译名 CSV）正交、按需并用

## 数据形态

- `config.json` — 社区官方轻量索引（id → terms + summary），约 39KB
- `entries/<id>.json` — 完整条目（definition / status / references / referencedBy / threadURL），**116 条**
- `embeddings.json` + `hnsw.idx` — 社区网站向量检索数据（本工作流不采用，关键词/脚本查询已够）
- 术语含同义词/缩写（如 `Block event delay`/`BED`、`Hopper speed`/`HS`/`1x`/`4x`/`6x`/`8x`）
- `references`/`referencedBy` 提供术语间引用网络（如 Batcher → Dropper speed）

## 术语清单（116 条）

（运行 `python scripts/dictionary_lookup.py list` 查看；不在此逐条复制，避免与上游脱节——本仓库随 `git submodule update` 演进）

- 关键词：存储科技, 术语词典, 社区, JSON, Discord, 存储, 漏斗, 潜影盒, 分类器
