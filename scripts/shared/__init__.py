# -*- coding: utf-8 -*-
"""跨工具共享模块（非可运行工具）。

归属：被**多个独立工具**共用、且本身不含 CLI 入口的模块放这里。
可运行的入口工具留在 `scripts/` 根（约定见 `scripts/README.md`）。

成员：
- `srt_common.py`——字幕处理共享层（折行 / 时间 / 非语音标记 / 块解析 / 视觉宽度 / 跨模块阈值常量）
- `request_identity.py`——对外请求身份（UA）解析

导入方式：
- 独立工具（`python scripts/srt_xxx.py` 运行，sys.path[0]=scripts/）：`from shared.srt_common import ...`
- `srt_reflow_core` 包内：`from shared.srt_common import ...`（绝对导入，理由见 `shared/srt_common.py` docstring）
"""
