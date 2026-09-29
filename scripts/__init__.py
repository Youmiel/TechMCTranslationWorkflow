# -*- coding: utf-8 -*-
"""scripts 包标记，并保证 `shared` / `srt_reflow_core` 可被绝对导入。

用途：使两种入口下 `from shared.xxx import ...` / `from srt_reflow_core.xxx import ...` 均可解析——
- 直接运行工具（`python scripts/<工具>.py`）：sys.path[0] 已是 `scripts/`，天然满足；
- 以包方式导入（`python -m scripts.<工具>` 或 `from scripts.<模块> import ...`）：把 `scripts/`
  追加进 sys.path 兜底（append 而非 insert——保留 cwd 与既有优先级）。

约定：可运行的工具留在本目录；不含 CLI 的共享模块放 `shared/` 或对应语义文件夹（如 `srt_reflow_core/`）。
"""
import os as _os
import sys as _sys

_HERE = _os.path.dirname(_os.path.abspath(__file__))
if _HERE not in _sys.path:
    _sys.path.append(_HERE)
