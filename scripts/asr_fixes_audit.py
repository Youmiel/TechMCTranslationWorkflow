# -*- coding: utf-8 -*-
"""asr_fixes 审计：冗余候选 + 能力边界分类。

## 用途

`asr_fixes.md` 长期只追加不删改，条目会堆积（含大量模型本就能猜的高频术语变体）。
本脚本按 **ASR 实测的能力边界**（见 `development-history` 的 ASR 实测节）出**候选清单**，
供人工裁定——**只报告，不自动删改**（`AGENTS.md` 核心原则 #6）。

## 分类判据

**唯一可删类**：

| 类 | 判据 |
|---|---|
| **拼写错误** | 正确词是普通英文词（各表均无），变体是同首字母的错拼（与术语无关） |

**保留类**（其余全部）：

| 类 | 为何留 |
|---|---|
| **专名类** | 模型真弱项（实测单问也答错） |
| **逻辑门/命令** | 模型弱项（实测判反） |
| **多词长术语** | **映射起“边界锚定”作用**（实测：词表单独存在时模型仍丢中间词） |
| **已验证可纠** | 无词表实测能改对，但映射仍提供**精确词形 + 抑制乱猜** |
| **按需表** | 正确词在 L1/L2 但非常驻 → 仅门禁选中时才注入 |
| **词表外** | 真知识缺口（无候选可联想） |

### 为何不再用“无词表能改对”当可删判据

该判据（前版）假设“模型能独立纠回 → 映射无用”，但**对照实验（A/B/C 三组）证伪**：

| 组 | 注入 | `titics` 改后 |
|---|---|---|
| A 裸 | 无 | `tile ticks` ✅ |
| B 仅词表 | 常驻集 | `ticks` ❌ 丢中间词 |
| C 词表+映射 | 常驻集 + 映射 | `tile ticks` ✅ |

**映射的作用不是“补模型不知道的词”，而是提供精确词形 + 抑制乱猜**——
无法用“模型能否独立纠回”衡量。故除拼写错误外一律保留。

报告：`_work/_abc_experiment.md`（三组对照，以参考稿裁决：主动改对 35 / 抑制乱猜 6 / 带偏 6）。

输出报告（UTF-8 落盘，默认 `_work/_asr_fixes_audit.md`）。

用法（命令根 = Project_Main/）：
  python scripts/asr_fixes_audit.py
  python scripts/asr_fixes_audit.py --out _work/_asr_fixes_audit.md
  python scripts/asr_fixes_audit.py --expand
"""
import argparse
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import glossary_lookup as GL                        # noqa: E402
import glossary_load_plan as GLP                    # noqa: E402
from shared.glossary_sources import iter_terms      # noqa: E402

ASR_FIXES = os.path.join(BASE, ".github", "experience", "asr_fixes.md")
PROPER_NOUNS = os.path.join(BASE, "knowledge", "01_terminology", "proper_nouns.csv")

# 逻辑门名（实测模型判反）与命令 → 保留
LOGIC_PAT = re.compile(r"^/?(and|or|not|nand|nor|xor|xnor|logic gate|tp|give|execute)s?$",
                       re.IGNORECASE)

# “变体是短英文单词”→ 高风险提示：这类变体本身合法，易把正确词误纠
SHORT_VARIANT_LEN = 5

# 报告章节编号（按实际出现的类数动态取，避免两个「三、」）
CN_NUM = ("", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
          "十一", "十二", "十三", "十四", "十五")

# 拼写错误判据：正确词长度下限 + 变体与正确词的编辑距离上限
SPELL_MIN_WORD = 6
SPELL_MAX_DIST = 2
SPELL_MIN_VARIANT = 4


def edit_distance(a, b):
    """Levenshtein 距离（字符级）。"""
    if a == b:
        return 0
    if not a or not b:
        return len(a) or len(b)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def parse_fixes(path):
    """解析 asr_fixes.md 表格 → [(正确词, [变体], 说明)]。"""
    rows = []
    for ln in open(path, encoding="utf-8"):
        if not ln.startswith("|") or set(ln.strip()) <= set("|- "):
            continue
        cols = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cols) < 3 or cols[0].lower() in ("正确词", "correct"):
            continue
        variants = [v.strip() for v in cols[1].split("/") if v.strip()]
        rows.append((cols[0], variants, cols[2]))
    return rows


def norm_forms(word):
    """正确词 → 匹配形式集合（去括注、试单复数）。"""
    w = re.sub(r"\(.*?\)", "", word).strip().lower().strip("/")
    forms = {w} if w else set()
    if w.endswith("s"):
        forms.add(w[:-1])
    else:
        forms.add(w + "s")
    return {f for f in forms if f}


def load_evidence(wdiff_dir):
    """读 `_wdiff/*.md` 的表格行 → `{原词小写: {子代理改动小写}}`。

    这些行记录了**无词表**条件下子代理的逐处改动（实测数据）——
    是“变体能否被纠回”的**唯一可靠证据**。

    行格式：`| \`原词\` | \`参考改动\` | \`子代理改动\` |`
    目录不存在则返回空 dict（调用方降级为“全部保留”）。
    """
    ev = {}
    if not os.path.isdir(wdiff_dir):
        return ev
    for fn in sorted(os.listdir(wdiff_dir)):
        if not fn.endswith(".md"):
            continue
        for ln in open(os.path.join(wdiff_dir, fn), encoding="utf-8",
                       errors="replace"):
            m = re.match(r"^\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|",
                         ln.strip())
            if m:
                ev.setdefault(m.group(1).lower(), set()).add(
                    m.group(3).lower().strip())
    return ev


def read_term_index(paths):
    """读若干表 → {词条小写}。"""
    s = set()
    for p in paths:
        if os.path.exists(p):
            for terms, _zh, shorts in iter_terms(p):
                for t in list(terms) + list(shorts):
                    s.add(t.lower())
    return s


def is_spelling(word, variants, known):
    """拼写错位：正确词是**单个通用英文词**，变体是错拼。

    四条同时成立才算（实测逐条加约束才可用，宽松判据会误扫 3 类）：

    1. **不在任何词表**——`calculate`/`simple` 类通用英文词；
       而 `shulker`←`shocker` 虽字符接近，却是术语音近误听（正确词在表内）
    2. **单 token**——多词短语（`cluster chunk`）的变体可能只是其中一词写错，
       不代表整条是拼写错误 → 归其他类
    3. **无大写字母**——表中的专名/缩写（`Mojang`/`MiniHUD`/`MSPT`）是大写，
       它们是模型可能不认识的知识（**必须保留**），不是拼写错误
    4. **变体不短于原词 -1**——排除**删前缀型**：`despawn`←`spawn` 的变体是
       真子串（编辑距离 2 却跨音素），属词边界/语义问题（表解决不了，靠语境）；
       而拼写错位是**同长度字母重排**（`caclulate`↔`calculate`、`simle`↔`simple`）

    ⚠️ 仍有假阳性（无英文词典可依）→ 本类报告**仅供参考**，逐条人工确认。
    """
    if " " in word.strip():
        return False
    if any(c.isupper() for c in word):
        return False
    forms = norm_forms(word)
    if forms & known:
        return False
    if any(len(f) < SPELL_MIN_WORD for f in forms):
        return False
    for v in variants:
        vl = v.lower().strip()
        if len(vl) < SPELL_MIN_VARIANT or vl in known:
            continue
        for f in forms:
            if len(vl) < len(f) - 1:
                continue
            if edit_distance(vl, f) <= SPELL_MAX_DIST:
                return True
    return False


def main():
    ap = argparse.ArgumentParser(description="asr_fixes 审计（只读，出候选清单）")
    ap.add_argument("--out", default=os.path.join(BASE, "_work", "_asr_fixes_audit.md"),
                    help="报告输出路径（默认 _work/_asr_fixes_audit.md）")
    ap.add_argument("--expand", action="store_true", help="报告含全部条目明细")
    args = ap.parse_args()

    rows = parse_fixes(ASR_FIXES)
    proper = read_term_index([PROPER_NOUNS])

    # 常驻集：**总是注入**的那部分（冗余判据用它，不用 L1/L2 全量——见模块 docstring）
    resident = set()
    for rel in GLP.RESIDENT:
        p = GLP.resolve(rel)
        if not p:
            continue
        for terms, _zh, shorts in iter_terms(p):
            for t in list(terms) + list(shorts):
                resident.add(t.lower())

    # L1 + L2（供“按需表”“词表外”判）
    all_sources = GL.discover_sources()
    l12_paths = [p for lv, p in all_sources if lv in ("L1", "L2")]
    l12 = read_term_index(l12_paths)
    l15 = read_term_index([p for lv, p in all_sources if lv == "L1.5"])
    known = l12 | l15

    # 先按正确词合并重复行（变体拼起来）——同一词多行分开分类会把同一词列两次
    merged = {}
    for w, variants, desc in rows:
        key = w.lower()
        if key in merged:
            merged[key][1].extend(variants)
            if desc and desc not in merged[key][2]:
                merged[key][2] = (merged[key][2] + " / " + desc).strip(" /")
        else:
            merged[key] = [w, list(variants), desc]
    items = [(v[0], v[1], v[2]) for v in merged.values()]

    seen = {w.lower(): 1 for w, _v, _d in items}
    dupes = {w.lower(): sum(1 for a, _v, _d in rows if a.lower() == w.lower())
             for w in {x[0] for x in rows}}
    dupes = {w: n for w, n in dupes.items() if n > 1}

    # 无词表实测证据（判“变体能否被纠回”的唯一可靠依据）
    evidence = load_evidence(os.path.join(BASE, "_work", "_asr_bench", "_wdiff"))

    def verified_fix(word, variants):
        """返回“变体被无词表改对”的证据（变体名），无则 None。

        两个条件同时成立才算可纠：
        ① 变体与正确词有相似度（实测里子代理确实联想到）
        ② 该改动方向指向本条的正确词
        """
        forms = norm_forms(word)
        for v in variants:
            fixed = evidence.get(v.lower().strip(), set())
            if any(f in forms or f == word.lower() for f in fixed):
                return v
        return None

    def classify(word, variants):
        """→ (类, 说明)。顺序即优先级。"""
        forms = norm_forms(word)
        if LOGIC_PAT.match(word.strip()) or word.strip().startswith("/"):
            return "逻辑门/命令", "模型弱项（实测判反），保留"
        if forms & proper:
            return "专名类", "模型真弱项（单问也答错），保留"
        if is_spelling(word, variants, known):
            return "拼写错误", "普通英文词错拼（非术语）→ LLM 自纠，可删"
        if " " in word.strip():
            return "多词长术语", "映射起边界锚定作用（模型易丢中间词），保留"
        if verified_fix(word, variants):
            return "已验证可纠", "无词表能改对，但映射仍提供精确词形与防乱猜，保留"
        if forms & resident:
            return "在常驻集", "词在常驻集，映射仍可防乱猜，保留"
        if forms & l12:
            return "按需表", "在 L1/L2 但非常驻 → 仅门禁选中时注入，保留"
        if forms & l15:
            return "词表外（仅 L1.5）", "L1.5 不注入，单靠联想纠不到"
        return "词表外", "真知识缺口（无候选可联想）→ 保留"

    buckets = {}
    detail = []
    for word, variants, desc in items:
        cls, why = classify(word, variants)
        buckets.setdefault(cls, []).append((word, variants, desc, why))
        # 高风险：变体里有短英文单词（本身合法，易误纠）
        risky = [v for v in variants
                 if len(v) <= SHORT_VARIANT_LEN and re.fullmatch(r"[a-z]+", v)]
        detail.append((word, cls, len(variants), risky, desc))

    L = []
    L.append("# asr_fixes 审计")
    L.append("")
    L.append(f"- 原始条目：**{len(rows)}** 条（合并重复后 **{len(items)}** 个正确词）；"
             f"变体合计 **{sum(len(v) for _w, v, _d in rows)}**")
    L.append(f"- 词表规模：**常驻集 {len(resident)} 词**（总是注入）；"
             f"L1+L2 **{len(l12)}** 词；L1.5 **{len(l15)}** 词；"
             f"`proper_nouns` **{len(proper)}** 词")
    if evidence:
        L.append(f"- 无词表实测证据：**{len(evidence)}** 个原词"
                 f"（来源 `_work/_asr_bench/_wdiff/`）")
    else:
        L.append("- ⚠️ **无实测证据**（`_work/_asr_bench/_wdiff/` 缺失）——"
                 "**降级模式**：只能报拼写错误，其余全部保留")
    L.append("")

    n = 0        # 章节计数器（统一编号，避免重复/跳号）

    if dupes:
        n += 1
        L.append(f"## {CN_NUM[n]}、重复条目（同一正确词多行，应合并）")
        L.append("")
        L.append("| 正确词 | 行数 |")
        L.append("|---|---|")
        for w, cnt in sorted(dupes.items(), key=lambda x: -x[1]):
            L.append(f"| `{w}` | {cnt} |")
        L.append("")

    n += 1
    L.append(f"## {CN_NUM[n]}、分类汇总")
    L.append("")
    L.append("| 类 | 条数 | 处理 |")
    L.append("|---|---|---|")
    order = ("拼写错误", "逻辑门/命令", "专名类", "多词长术语",
             "已验证可纠", "在常驻集", "按需表", "词表外（仅 L1.5）", "词表外")
    handling = {"拼写错误": "可删（LLM 自纠）",
                "逻辑门/命令": "**保留**", "专名类": "**保留**",
                "多词长术语": "**保留**（边界锚定）",
                "已验证可纠": "**保留**（精确词形/防乱猜）",
                "在常驻集": "**保留**", "按需表": "**保留**",
                "词表外（仅 L1.5）": "**保留**", "词表外": "**保留**"}
    for cls in order:
        if cls not in buckets:
            continue
        L.append(f"| {cls} | {len(buckets[cls])} | {handling[cls]} |")
    L.append("")

    for cls in order:
        if cls not in buckets:
            continue
        n += 1
        L.append(f"## {CN_NUM[n]}、{cls}（{len(buckets[cls])} 条）")
        L.append("")
        L.append("| 正确词 | 变体数 | 说明 |")
        L.append("|---|---|---|")
        for word, variants, desc, _why in buckets[cls]:
            L.append(f"| `{word}` | {len(variants)} | {desc} |")
        L.append("")

    risky_rows = [d for d in detail if d[3]]
    if risky_rows:
        n += 1
        L.append(f"## {CN_NUM[n]}、高风险变体（{len(risky_rows)} 条）")
        L.append("")
        L.append(f"变体含 ≤{SHORT_VARIANT_LEN} 字母的纯英文单词——**本身是合法词**，"
                 f"注入后模型可能反向误纠（把正确的 `spawn` 改成 `despawn`）。")
        L.append("")
        L.append("| 正确词 | 高风险变体 |")
        L.append("|---|---|")
        for word, _cls, _cnt, risky, _d in risky_rows:
            L.append(f"| `{word}` | {'、'.join('`' + r + '`' for r in risky)} |")
        L.append("")

    n += 1
    L.append(f"## {CN_NUM[n]}、人工裁定要点")
    L.append("")
    L.append("- **唯一可删类** = `拼写错误`（普通英文词错拼，与术语无关）")
    L.append("- **其余一律保留**——映射的价值不止“补模型不知道的词”，还有"
             "**提供精确词形 + 抑制乱猜**（对照实验见 `_work/_abc_experiment.md`）")
    L.append("- **多词长术语尤其要留**：实测词表单独存在时模型仍丢中间词"
             "（`titics`→`ticks`），而映射给出完整词形（`tile ticks`）")
    L.append("- `拼写错误` 判据**有假阳性**（专名、多词短语会被误扫）→ 逐条确认"
             "那真是普通英文词再删")
    L.append("")

    if args.expand:
        n += 1
        L.append(f"## {CN_NUM[n]}、全部条目明细")
        L.append("")
        L.append("| 正确词 | 类 | 变体数 |")
        L.append("|---|---|---|")
        for word, cls, _cnt, _r, _d in detail:
            L.append(f"| `{word}` | {cls} | {_cnt} |")
        L.append("")

    L.append("---")
    L.append("")
    L.append("> **本报告只出候选**。删改 `asr_fixes.md` 须人工裁定后手动执行"
             "（`AGENTS.md` 核心原则 #6）。")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")

    print(f"已写入 {args.out}")
    if not evidence:
        print("  ⚠️ 无实测证据（_work/_asr_bench/_wdiff/ 缺失）→ '已验证可纠' 标注不可用")
    print(f"  原始条目 {len(rows)} → 合并后 {len(items)} 个正确词；重复 {len(dupes)} 个；"
          f"可删（拼写错误）{len(buckets.get('拼写错误', []))}；"
          f"多词长术语 {len(buckets.get('多词长术语', []))}；"
          f"高风险变体 {len(risky_rows)} 条")


if __name__ == "__main__":
    main()
