# translate 产物格式（PRODUCT_FORMATS_TRANSLATE）

> translate-redstone（方案一 逐句翻译；**项目最早建立的工作流**）阶段三 专有产物的格式 / 结构 / 标记约定。
> 通用约定、共享产物（`01` / `02` / `term_*` / `wiki_*`）、通用文本分块、配置文件 → [PRODUCT_FORMATS](PRODUCT_FORMATS.md)。
> 其它工作流复用本文件约定时，在各自文件内只留短句 + 链接，不重复展开。

## 产物速查

| 产物 | 生成者 | 消费/校验 |
|------|--------|-----------|
| `s03_plan.md` | Agent（合并断句定稿） | `srt_check_segments.py`（md 模式） |
| `s04_draft.srt` | Agent（逐段翻译） | `srt_check_segments.py`、`srt_check_width.py`、`srt_check_terms.py` |
| `_merge_results/chunk_<k>.txt` | Agent（断句 subagent `task-merge`） | `text_merge.py` → `s03_plan.md`；`srt_check_plan_words.py` |
| `_trans_results/chunk_<k>.txt` | Agent（翻译 subagent `task-translate`） | `text_merge.py` → s04；`srt_check_terms.py` |
| `_humanize_results/chunk_<k>.txt` | Agent（去翻译腔 subagent `task-humanize`） | 主会话按段号回写 `s04_draft.srt` |

## `s03_plan.md`

- 命名：`<工作目录>/s03_plan.md`
- 生成：Agent（合并断句定稿，交用户审核前落盘）
- 格式：**每行一段**：

```
段号|cstart[-cend][~]|文本
```

- `cstart`/`cend` = 该段覆盖的原字幕 cue 号区间；`~` 标注该侧为估算切分点（受控例外，见 segment-subtitles）
- 示例：`1|c1-c3|This is why I am literally the smartest programmer that ever lived.`
- 校验：`python scripts/srt_check_segments.py s03_plan.md --orig <01>`

## `s04_draft.srt`

- 命名：`<工作目录>/s04_draft.srt`
- 生成：Agent（逐段翻译，逐段落盘断点续译）
- 格式：标准 SRT，双语 `zh-en`（中文行在前、英文行在后）
- 约束：时间边界 **⊆ 原字幕边界集合**（translate 特有，不允许新造时间点）；行宽软 22 / 硬 27
- 校验：`python scripts/srt_check_segments.py s04_draft.srt --orig <01>`、`python scripts/srt_check_width.py s04_draft.srt --order zh-en`、`python scripts/srt_check_terms.py 01_subtitle_asr_fixed.srt 02_terms.md s04_draft.srt --plan s03_plan.md`

## `_merge_results/chunk_<k>.txt`

- 命名：`<工作目录>/_merge_results/chunk_<k>.txt`（每块一个；分块时产生，N=1 即单块）
- 生成：断句 subagent（`task-merge`）——对 chunks 块 OWNED cue 做英文侧断句（游离单词归位 + 语义合并 + 对白拆分 + 分割超长句 + 共享 cue 归属）
- 格式：**srt 类型**，**每行一段** `段号|cstart[-cend][~]|英文文本`。
  - 段号**块内从 1 连续编号**（`text_merge.py` 合并时全局段号重排）
  - `~` = 估算切分点（受控例外，见 「segment-subtitles#中间断句与估算时间」）
  - `CARRY: c<idx>` 结转标记行**独立成行**（跨块未完成句，见 redstone-conventions §5）
- 约束：
  - **断句只合并 / 分割、不改措辞**（英文词序列须与 01 对应 cue 区间一致，`srt_check_plan_words.py` 校验；02_terms 确认的 ASR 修正除外）
  - 时间边界 ⊆ 原边界集、不新造时间点（`~` 除外）
  - 空 cue（[Music] 等）不单独产出、时间并入相邻段
- 合并：`python scripts/text_merge.py <chunks_dir> <_merge_results/> --out s03_plan.md`（srt 类型：全局段号重排）
- 校验（合并后）：`python scripts/srt_check_plan_words.py 01_subtitle_asr_fixed.srt s03_plan.md [--asr-fixes 02_terms.md]`

## `_trans_results/chunk_<k>.txt`

- 命名：`<工作目录>/_trans_results/chunk_<k>.txt`（每块一个）
- 生成：翻译 subagent（`task-translate`）——对 `_merge_results/chunk_<k>.txt` 段行逐段翻译为中文
- 格式：**srt 类型**——**每行一段** `段号|cue范围|中文译文`，段号与输入段行一致（不重编号）；`CARRY: c<idx>` 结转标记行**原样保留**（text_merge 去重用）；中文译文**单行**（不折行，折行由主会话统一处理）
- 约束：不改变句子顺序、段号与 cue 范围不变；术语严格用 02_terms 确认译名（`srt_check_terms.py` 校验）；时间边界不新造时间点
- 合并：`text_merge.py <chunks_dir> <_trans_results/> --out <中间稿>`（srt 类型全局段号重排）→ 主会话转 `s04_draft.srt`（标准 SRT 双语 zh-en）
- 校验：`python scripts/srt_check_terms.py 01_subtitle_asr_fixed.srt 02_terms.md <_trans_results/> --chunks <chunks/>`（分块时逐块核对）

## `_humanize_results/chunk_<k>.txt`

- 命名：`<工作目录>/_humanize_results/chunk_<k>.txt`（每块一个）
- 生成：去翻译腔 subagent（`task-humanize`）——对 `s04_draft.srt` 全稿或其分块做去翻译腔/去 AI 味
- 格式：**每行一段** `段号|修订后译文`（可附改动点说明，如 `3|改成这样（删了多余的"然后"）`）；未改动段也输出（`段号|原中文`），保证段号齐全
- 约束：术语译名**不受影响**（只润措辞）；保留字幕口语感与节奏；已自然段落默认不改
- 消费：主会话按段号把修订稿回写 `s04_draft.srt` 中文行（人工确认后）
