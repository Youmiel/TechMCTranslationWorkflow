# -*- coding: utf-8 -*-
"""ASR 触发清单生成器（确定性、无状态；可执行方案 §五 5.1）。

## 要解决的问题

ASR 误听修正原由 LLM 逐块“遍历全文、发现怪词”触发 → **触发依赖注意力**。
实测该环节是主瓶颈：长对话低频词修正率最低 45.2%，缺失项中 69.8% 属
“长文本里没注意到”而非不知道。本脚本把“发现”从**注意力驱动**改为**清单驱动**。

## 数据源纪律（硬约束）

**只看当前视频字幕 + Git 追踪的正式资产**（`asr_fixes.md`）——**绝不**读其它视频的
字幕/产物，也不用历史语料的统计特征（即使更准）。故本脚本**无状态**。

## 分层（判据 4 的实测依据）

| 层 | 判据 | 动作 |
|---|---|---|
| **M** | 变体**含空格** | 列出（实测误报率 3%） |
| **S** | **单字**且不在停用词表 | 列出（实测高价值） |
| **X** | **单字**且在 `STOP_HARD ∪ STOP_SOFT` | **不列**（实测误报率 96%，`as` 一句就 111 次） |

⚠️ 真实分界是**单字 vs 多词**，**不是**词数（初稿假设“2 词档最危险”已被实测否定）。

⚠️ **不得**用“变体是否为词表词的组成词”作过滤——实测误滤 19 个真命中（含 `lock` 16 个）。

### S 层不区分“同形异义”子类（已验证 · 不实现）

方案初稿曾设想给“常见内容词”加“需语境”标注（Y 层，如 `note`→node / `minecraft`→minecart）。
**实测否定**（报告 = `References/ASR修正-实测资料/pre-implementation/Y_LAYER_VERIFICATION.md`）：

- **误纠实例 = 0**（223 条决策 / 7 视频；3 条候选逐条人工核，全为探针假阳性）
- 候选判据（长度≥5 ∧ 词表外 ∧ 纯字母）**误伤真命中 76%** → 无判别力
- **机制**：同形异义是**单次出现的属性**，不是**变体的类别**——同一串 `light`：
  "light a portal"＝点燃（正常），他处 `light`→`lag` 才是误听。
  而判定所需的语境（完整句子）清单注入**已给到 subagent** → 叠加标注仅冗余。
- **关键区分**：标注只能帮**误纠**（模型误解语境），帮不了**漏检**（模型没注意到）。

**⚡ 回来重议的触发条件**（任一出现即重看此节）：

| 触发 | 为何改变结论 | 怎么做 |
|---|---|---|
| **发现真实误纠实例**（定稿里正确词被改坏） | A/B 才有**可检验的假设**（当前预期收益为零） | 重跑第 0 步探针（归档目录 `_y_layer_step0_misrefix.py`，在 `Project_Main/` 下跑）→ 有实例再开 A/B（`scripts/_dev/asr_bench_b.py gen` 已具备） |
| **S 项挤占上下文**（项数/字符数显著增长） | 降噪开始有**边际价值**（当前收益为零，但可换上下文） | 统计当前 `--layers M,S` 行数与字符数，与分块预算对比 |
| **出现“出现级”判据**（非变体级） | 变体级静态判据**已被否定**，出现级**未被证否** | 如按上下文窗口/词性区分**单次出现**，而非给变体分类 |
| **语料规模显著扩大**（远超当前 8 视频） | “零误纠”是**未观察到**，不是“永远不会” | 重跑第 0 步确认零误纠仍成立 |

## 两条铁律

1. **检出必须带绑定**（`变体 → 完整正确词形`）。注入裸词条会退化——实测：
   注入 `Tile Tick = 计划刻` 使 `instantic switch` 丢词；注入 `tile tick(s) ← titic / titics` 才改对。
2. **只用整串精确匹配**（大小写不敏感 + 空白折叠）。一旦模糊，本脚本即退化为
   “另一个会漏检的近似器”。

## 用法（命令根 = Project_Main/）

  python scripts/asr_trigger.py scan <字幕.srt> [--video <工作目录>] [--out <tsv>]
                                          [--local-fixes <局部asr_fixes.md>]
                                          [--layers M,S] [--no-stopwords]

输出 `<工作目录>/asr_trigger/triggers.tsv`（`--out` 可覆盖；两者都缺省则打印 stdout）。
退出码：0 = 正常（含零命中）；1 = 输入不可解析。
"""
import argparse
import bisect
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from shared.asr_common import (  # noqa: E402
    STOP_ANY, collect_pairs, fmt_hhmmss, normalize, read_srt, variant_re,
)

ASR_FIXES_GLOBAL = os.path.join(BASE, ".github", "experience", "asr_fixes.md")

# 分层判据：多词（含空格）/ 单字停用词外 / 单字停用词内
LAYER_MULTI = "M"
LAYER_SINGLE = "S"
LAYER_STOPWORD = "X"
ALL_LAYERS = (LAYER_MULTI, LAYER_SINGLE, LAYER_STOPWORD)
DEFAULT_LAYERS = (LAYER_MULTI, LAYER_SINGLE)


def layer_of_variant(vn, stop_any):
    """归一化变体 → 层（M/S/X）。纯机械，无算法风险。"""
    if " " in vn:
        return LAYER_MULTI
    return LAYER_STOPWORD if vn in stop_any else LAYER_SINGLE


def build_index(cues):
    """cue 文本归一化后空格拼接 → `(full_text, spans)`。

    `spans` = `[(start, end, cue_idx, timestamp)]`（按起点升序）。

    必须**扫全文**（cue 空格连接）——实测有跨 cue 断裂实例（`play ahead and bedwalk`），
    按单 cue 扫会漏。
    """
    parts, spans, pos = [], [], 0
    for i, (idx, start, _end, text) in enumerate(cues, 1):
        t = normalize(text)
        if parts:
            pos += 1  # 拼接用的空格
        spans.append((pos, pos + len(t), idx or i, fmt_hhmmss(start)))
        parts.append(t)
        pos += len(t)
    return " ".join(parts), spans


def locate(spans, starts, pos):
    """命中起点字符偏移 → `(cue_idx, timestamp)`（跨 cue 变体取**起点**所在 cue）。"""
    i = bisect.bisect_right(starts, pos) - 1
    if i < 0:
        i = 0
    return spans[i][2], spans[i][3]


def scan(sub_text, spans, pairs, stop_any, layers, no_stopwords):
    """→ `(items, stat)`。

    `items` = `[(cue_idx, timestamp, layer, variant, [正确词...], 说明/来源)]`，按 cue 升序。
    `stat` = 分层命中统计（**按变体去重**，用于自检）。
    """
    starts = [s for s, _e, _i, _t in spans]
    # 归一化变体 → {正确词集合}（多义 = 命中多个不同正确词）
    by_variant = {}
    for correct, variant, note, _src in pairs:
        vn = normalize(variant)
        rec = by_variant.setdefault(vn, {"variant": variant, "corrects": []})
        if correct not in rec["corrects"]:
            rec["corrects"].append(correct)

    layers_of = {vn: layer_of_variant(vn, stop_any) for vn in by_variant}

    # 变体去重口径（自检用）：字幕中出现的已登记变体（归一化）
    appeared = set()
    rows = {}
    for vn, rec in by_variant.items():
        layer = layers_of[vn]
        hit = False
        for m in variant_re(vn).finditer(sub_text):
            hit = True
            # `--no-stopwords`：放宽为列出 X 项（对照评测），但**保留 X 层标注**——
            # 改标成 S 层会让对照结果无法归因。
            if layer not in layers and not (no_stopwords and layer == LAYER_STOPWORD):
                continue
            cue_idx, ts = locate(spans, starts, m.start())
            key = (cue_idx, vn)
            if key in rows:
                continue
            rows[key] = (cue_idx, ts, layer, rec["variant"], list(rec["corrects"]), [])
        if hit:
            appeared.add(vn)

    items = [rows[k] for k in sorted(rows)]
    stat = {
        "appeared": len(appeared),
        "by_layer": {lay: len([v for v in appeared if layers_of[v] == lay]) for lay in ALL_LAYERS},
        "listed_layers": list(layers),
        "no_stopwords": no_stopwords,
        "rows": len(items),
    }
    return items, stat


def fmt_row(item):
    """`c<idx>\\t<时间码> | <层> | <变体> | <正确词形> | <标签>`（与 scan_terms.txt 同风格）。"""
    cue_idx, ts, layer, variant, corrects, _notes = item
    tags = ["mapping"]
    if len(corrects) > 1:
        tags.append("ambiguous")
    return "c%d\t%s | %s | %s | %s | %s" % (
        cue_idx, ts, layer, variant, " / ".join(corrects), ",".join(tags))


def render(items, stat, sub_path):
    """清单文本（**只含清单行**，供渲染脚本按 cue 号过滤注入）。"""
    layers_note = "M 多词 / S 单字·高价值 / X 单字·停用词（默认不列）" \
        if not stat["no_stopwords"] else "M 多词 / S 单字·高价值 / X 单字·停用词（本次已列）"
    lines = ["# ASR 触发清单（脚本检出；变体 → 正确词形）",
             "# SRC: %s" % os.path.basename(sub_path),
             "# 层：%s" % layers_note,
             "# 格式：c<idx>\\t<时间码> | <层> | <变体> | <正确词形> | <标签>"]
    lines += [fmt_row(it) for it in items]
    if not items:
        lines.append("# （本视频无已登记变体命中）")
    return "\n".join(lines) + "\n"


def report(stat, stream):
    """自检：M/S/X 三层命中数之和应等于“字幕中出现的已登记变体去重数”。"""
    b = stat["by_layer"]
    total = b[LAYER_MULTI] + b[LAYER_SINGLE] + b[LAYER_STOPWORD]
    ok = "OK" if total == stat["appeared"] else "差异 %d" % (total - stat["appeared"])
    print("自检：M=%d S=%d X=%d 合计=%d / 命中变体去重=%d →%s"
          % (b[LAYER_MULTI], b[LAYER_SINGLE], b[LAYER_STOPWORD],
             total, stat["appeared"], ok), file=stream)
    x_note = "X 层已列出（停用词过滤关闭）" if stat["no_stopwords"] \
        else ("X 层=%d 条噪声未列（停用词过滤生效）" % b[LAYER_STOPWORD])
    print("清单行数=%d（层 %s；%s）"
          % (stat["rows"], ",".join(stat["listed_layers"]), x_note), file=stream)
    if total != stat["appeared"]:
        print("!! 自检不等：请核对分层判据（M/S/X 应覆盖全部已登记变体）", file=stream)


def main():
    ap = argparse.ArgumentParser(description="ASR 触发清单生成器（无状态，只读当前视频 + 正式资产）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("scan", help="扫字幕生成触发清单")
    p.add_argument("subtitle", help="当前视频字幕（00_subtitle_snapped.srt）")
    p.add_argument("--video", help="视频工作目录（输出默认落 <video>/asr_trigger/triggers.tsv）")
    p.add_argument("--out", help="输出 tsv 路径（覆盖默认）")
    p.add_argument("--local-fixes", action="append", default=[],
                   help="本视频局部 asr_fixes.md（默认 <video>/asr_fixes.md）")
    p.add_argument("--layers", default=",".join(DEFAULT_LAYERS),
                   help="输出哪些层（默认 M,S；加 X 可对照评测）")
    p.add_argument("--no-stopwords", action="store_true",
                   help="关闭判据 4（停用词过滤）：X 层也列出（仍标 X 层），仅供对照评测")
    p.add_argument("--expand", action="store_true",
                   help="展开分层明细（默认只给计数；本脚本清单已是明细，此开关仅影响自检输出）")
    args = ap.parse_args()

    if not os.path.exists(args.subtitle):
        print("错误：字幕不存在：%s" % args.subtitle, file=sys.stderr)
        return 1
    cues, bad = read_srt(args.subtitle)
    if not cues:
        print("错误：无法从 %s 解析出任何 cue（格式不可解析）" % args.subtitle, file=sys.stderr)
        return 1

    layers = tuple(x.strip().upper() for x in args.layers.split(",") if x.strip())
    unknown = [x for x in layers if x not in ALL_LAYERS]
    if unknown:
        print("错误：未知层 %s（可选 %s）" % (",".join(unknown), ",".join(ALL_LAYERS)), file=sys.stderr)
        return 1

    fixes = [ASR_FIXES_GLOBAL]
    for path in args.local_fixes or (
            [os.path.join(args.video, "asr_fixes.md")] if args.video else []):
        if os.path.exists(path):
            fixes.append(path)
    pairs = collect_pairs(fixes)
    if not pairs:
        print("错误：未解析到任何映射条目（%s）" % "、".join(fixes), file=sys.stderr)
        return 1

    text, spans = build_index(cues)
    items, stat = scan(text, spans, pairs, STOP_ANY, layers, args.no_stopwords)

    out = render(items, stat, args.subtitle)
    dest = args.out
    if not dest and args.video:
        dest = os.path.join(args.video, "asr_trigger", "triggers.tsv")
    # 统计流：--out 模式下 stdout 空闲 → 走 stdout（PowerShell 把 stderr 渲染成报错，
    # 会让调用者误判失败）；未指定输出时 stdout 归清单，统计退到 stderr。
    stream = sys.stdout
    if dest:
        os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(out)
        print("已写入 %s" % dest)
    else:
        sys.stdout.write(out)
        stream = sys.stderr

    if bad:
        print("提示：跳过 %d 个坏块（无时间码或空文本）" % bad, file=stream)
    print("映射表：%d 份 / %d 变体；cue 数 %d" % (len(fixes), len(pairs), len(cues)), file=stream)
    report(stat, stream)
    return 0


if __name__ == "__main__":
    sys.exit(main())
