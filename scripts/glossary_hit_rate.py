# -*- coding: utf-8 -*-
"""术语表命中率回测（长期维护的统计工具）。

用途：以历史视频的 `scan_terms.txt` 为证据，统计**每张术语表**的实际使用情况，
      为「哪些表该常驻加载 / 哪些分类该补关键词 / 哪些表该退役」提供数据依据。
      **可定期重跑**，观察命中率随语料积累的漂移。

两个维度，互相校验：

  (A) 实际命中 —— 读各视频 `scan_terms.txt`，统计每张表被多少视频真实命中。
      这是最硬的证据，直接反映「该表是否需要加载」。

  (B) 预判命中 —— 用 `glossary_categories.yaml` 的 keywords 对字幕前 20 句复现
      「命中 ≥2 次」规则，统计每个分类的预判命中率。
      (A) vs (B) 的差异可诊断「关键词缺不缺」「关键词宽不宽」。

误报消歧（关键）：
    `glossary_lookup.py scan` 是**字面匹配**——术语词形恰好是通用英文词时必然误命中
    （如 `and` = 与门，在英文里到处出现；这不是表的错，是扫描机制的固有缺陷）。
    故每张表同时给出两个命中率：

      - **原始命中率**：含误报，会虚高（如 `computational.csv` 84%）
      - **净命中率**：剔除硬停用词后重算，接近真实使用情况

    分两档停用词，避免误杀真术语（`block`/`item` 在 Minecraft 语境多为真命中）：

      - 硬档（HARD）：连接词/代词/介词/助动词等**不可能单独作术语**的词 → 直接剔除
      - 软档（SOFT）：抽象名词/方位词等**可能是真术语**的词 → 仅单列"可疑"计数，不剔除

    停用词表可外置覆盖（`--stopwords`，每行一词，`#` 注释）；内表为保守起点。

输出报告（UTF-8 落盘，默认 `_work/_glossary_hit_rate.md`）：
    一、概览 / 二、实际命中（原始 + 净）/ 三、常驻候选 / 四、零命中表 /
    五、预判命中 / 六、诊断提示 / 七、噪声观测

用法（命令根 = Project_Main/）：
  python scripts/glossary_hit_rate.py --root _input --out _work/_glossary_hit_rate.md
  python scripts/glossary_hit_rate.py --root _input --history _work/_hit_rate_history.md
  python scripts/glossary_hit_rate.py --root _work --root _input --out _work/_glossary_hit_rate.md

`--root` 可多次；每个根下支持两种语料形态（视频目录 / 平铺 `.srt`）。
**语料应 ≥10 个视频**，否则命中率不可信（`--min-videos`）——语料被清理后重跑会误判。
"""

import argparse
import glob
import os
import re
import sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from shared.asr_common import STOP_HARD, STOP_SOFT  # noqa: E402
from shared.asr_common import load_stopwords as _load_stopwords  # noqa: E402

YAML_PATH = os.path.join(BASE, ".github", "experience", "glossary_categories.yaml")

SUBTITLE_PRIORITY = ("00_subtitle_snapped.srt", "01_subtitle_asr_fixed.srt")

# 最小可信样本量：低于此数量时命中率不可信（语料可能被清理过），不得据此增删常驻表。
# 取 10 是因为命中率按「命中视频数 ÷ 总视频数」算——分母太小则单视频权重过大。
MIN_VIDEOS = 10

# 停用词表（`STOP_HARD` / `STOP_SOFT` / `load_stopwords`）已迁至
# `shared/asr_common.py` 作单一权威——ASR 触发清单的 X 层过滤复用同一张表
# （可执行方案 §三 判据 4），两处各存一份必然漂移。


# ---------------- 语料发现 ----------------

def discover_videos(roots):
    """返回 [(视频名, 路径)]；路径可能是**视频目录**或**单个 .srt 文件**。

    两种语料形态：

    - **视频目录**（如 `_work/<视频名>/`）：含 `00`/`01`/`scan_terms.txt`/`02_terms.md` 等工作产物。
    - **平铺素材**（如 `_input/`）：目录内直接是待处理 `.srt`，每个文件视作一个视频。
      该形态**只有原始素材、无工作产物** → 仅离线口径（主口径）可用。

    根目录自身含 `scan_terms.txt` 时也视为一个视频。

    排除备份/重复目录（`_old*`/`_bak`/`DownSub`/`backup`）——否则同一视频会被
    重复计数（语料里存在同一视频的多份 `_old*` 备份）。
    """
    found = []
    for r in roots:
        if not os.path.isdir(r):
            continue
        base = os.path.abspath(r)
        if os.path.exists(os.path.join(base, "scan_terms.txt")):
            found.append((os.path.basename(base), base))
            continue
        for name in sorted(os.listdir(base)):
            p = os.path.join(base, name)
            if os.path.isdir(p):
                if not SKIP_DIR_PAT.search(name):
                    found.append((name, p))
            elif name.lower().endswith(".srt"):
                found.append((os.path.splitext(name)[0], p))
    return found


def pick_subtitle(path):
    """取字幕：视频目录 → 优先 `00`/`01`，其次任 `.srt`；平铺素材（`.srt` 文件）→ 返回自身。"""
    if os.path.isfile(path):
        return path if path.lower().endswith(".srt") else None
    for fn in SUBTITLE_PRIORITY:
        p = os.path.join(path, fn)
        if os.path.exists(p):
            return p
    hits = sorted(glob.glob(os.path.join(path, "*.srt")))
    return hits[0] if hits else None


# ---------------- (A) 实际命中 ----------------

def norm_source(raw):
    """来源路径 → 归一化表名（统一正斜杠，去掉 .cache/ 与 ./ 前缀）。"""
    s = raw.strip().replace("\\", "/")
    for pre in (".cache/", "./"):
        if s.startswith(pre):
            s = s[len(pre):]
    return s


def rel_table(path):
    """绝对路径 → 与 norm_source 同口径的表名。"""
    return norm_source(os.path.relpath(path, BASE))


def parse_scan(path):
    """解析 scan_terms.txt → [(词, 表名, 层级, 是否标误报)]。

    行格式：`c<idx>\\t<时间码> | <词> | <译名> | <来源> | <层级>`
    （split " | " 后：cols[0]=时间码, [1]=词, [2]=译名, [3]=来源, [4]=层级）
    """
    out = []
    with open(path, encoding="utf-8-sig") as f:
        for ln in f:
            ln = ln.rstrip("\n")
            if not ln.strip():
                continue
            if "\t" in ln:
                _cue, rest = ln.split("\t", 1)
            else:
                parts2 = ln.split(None, 1)
                if len(parts2) < 2:
                    continue
                rest = parts2[1]
            cols = [c.strip() for c in rest.split(" | ")]
            if len(cols) < 5:
                continue
            word, src, level = cols[1], cols[3], cols[4]
            flagged = ("⚠" in ln) or ("误报" in ln)
            out.append((word, norm_source(src), level, flagged))
    return out


def word_class(word, hard, soft):
    """命中的英文词形 → 'hard' / 'soft' / 'normal'。"""
    w = word.strip().lower()
    if not w:
        return "normal"
    if w in hard:
        return "hard"
    if w in soft:
        return "soft"
    # 单字母/双字母纯字母（T / N / it 类）→ 硬停用（几乎必为误报）
    if len(w) <= 2 and w.isalpha():
        return "hard"
    return "normal"


# ---------------- (B) 预判命中 ----------------

def parse_yaml_categories():
    """解析 glossary_categories.yaml → {分类: [keywords]}（兼容引号键名）。"""
    cats = {}
    if not os.path.exists(YAML_PATH):
        return cats
    in_cats = False
    cur = None
    for ln in open(YAML_PATH, encoding="utf-8"):
        if re.match(r"^categories:\s*$", ln):
            in_cats = True
            continue
        if in_cats and re.match(r"^\S", ln):
            break
        if not in_cats:
            continue
        m = re.match(r'^  "?([A-Za-z0-9_.\-]+)"?:\s*$', ln)
        if m:
            cur = m.group(1)
            cats[cur] = []
            continue
        if cur:
            m = re.search(r"^    keywords:\s*\[(.*)\]\s*$", ln)
            if m:
                cats[cur] = [k.strip().strip('"').strip("'")
                             for k in m.group(1).split(",") if k.strip()]
    return cats


def srt_cues(path, limit):
    """读 SRT 前 limit 条 cue 的文本。"""
    text = open(path, encoding="utf-8-sig").read()
    cues = []
    for block in re.split(r"\n\s*\n", text):
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        cues.append(" ".join(lines[2:]))
        if len(cues) >= limit:
            break
    return cues


def predict_categories(vdir, cats, limit=20, threshold=2):
    """复现「前 N 句 × keywords 命中 ≥2 次」→ {分类: 命中次数}（仅返回达阈值的）。"""
    sub = pick_subtitle(vdir)
    if not sub:
        return None
    text = " ".join(srt_cues(sub, limit)).lower()
    if not text:
        return None
    hits = {}
    for cat, kws in cats.items():
        n = 0
        for kw in kws:
            k = kw.lower().strip()
            if not k:
                continue
            n += len(re.findall(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])", text))
        if n >= threshold:
            hits[cat] = n
    return hits


# ---------------- 停用词加载 ----------------

def gather_pred(videos, cats, limit=20, threshold=2):
    """统计每个分类的预判命中视频集合（独立函数，便于校验与复用）。

    返回 (pred: {分类: {视频}}, n_pred: 可读字幕的视频数)。
    """
    pred = defaultdict(set)
    n_pred = 0
    for vname, vdir in videos:
        p = predict_categories(vdir, cats, limit=limit, threshold=threshold)
        if p is None:
            continue
        n_pred += 1
        for c in p:
            pred[c].add(vname)
    return pred, n_pred


def load_stopwords(path):
    """外置停用词表：每行一词（`#` 注释）。返回 (hard, soft)。

    实现已迁 `shared/asr_common.py`（单一权威，ASR 触发清单共用）；此处保留
    同名薄壳，避免既有调用方与 `--stopwords` 文档口径断裂。
    """
    return _load_stopwords(path)


# ---------------- 主流程 ----------------

def gather(videos, hard, soft):
    """汇总统计。返回一个 dict。"""
    tbl_videos = defaultdict(set)         # 表 → {视频}
    tbl_videos_net = defaultdict(set)     # 表 → {视频}（剔除硬停用词后仍有命中）
    tbl_words = defaultdict(Counter)      # 表 → Counter(词)（净，已剔硬）
    tbl_hard = Counter()                  # 表 → 硬停用词命中次数
    tbl_hard_words = defaultdict(Counter)  # 表 → Counter(硬停用词)（展示用）
    tbl_soft = Counter()                  # 表 → 软停用词命中次数
    tbl_level = {}
    tbl_flagged = Counter()
    word_counter = Counter()              # 词 → 次数（含硬停用词，供噪声观测）
    word_srcs = defaultdict(set)
    n_scan = 0

    for vname, vdir in videos:
        st = os.path.join(vdir, "scan_terms.txt")
        if not os.path.exists(st):
            continue
        n_scan += 1
        for word, src, level, flagged in parse_scan(st):
            tbl_videos[src].add(vname)
            tbl_level[src] = level
            if flagged:
                tbl_flagged[src] += 1
            cls = word_class(word, hard, soft)
            if cls == "hard":
                tbl_hard[src] += 1
                tbl_hard_words[src][word.strip().lower()] += 1
                word_counter[word.strip().lower()] += 1
                word_srcs[word.strip().lower()].add(src)
                continue
            if cls == "soft":
                tbl_soft[src] += 1
            tbl_videos_net[src].add(vname)
            tbl_words[src][word] += 1
            word_counter[word.strip().lower()] += 1
            word_srcs[word.strip().lower()].add(src)
    return {
        "tbl_videos": tbl_videos, "tbl_videos_net": tbl_videos_net,
        "tbl_words": tbl_words, "tbl_hard": tbl_hard, "tbl_hard_words": tbl_hard_words,
        "tbl_soft": tbl_soft,
        "tbl_level": tbl_level, "tbl_flagged": tbl_flagged,
        "word_counter": word_counter, "word_srcs": word_srcs, "n_scan": n_scan,
    }


def offline_scan(videos, hard, soft, levels=("L1", "L1.5", "L2"),
                 l2_categories=None, max_cues=None):
    """离线全量重扫：用**当前全部术语表**对历史视频字幕重新匹配。

    与读 `scan_terms.txt` 的本质区别：**不受历史 `--categories` 过滤影响**。
    历史产物只记录了「实际加载过的表」的命中，未加载的表一律无记录 → 对应
    「假零命中」（真零 vs 没扫过无法区分）。本函数拿整张词汇表去匹配完整字幕，
    因此这里的「零命中」**就是真零命中**。

    复用 `glossary_lookup` 的索引/匹配层（同一套适配器与词边界判据），
    保证与生产扫描口径一致；不重复实现。

    返回 {表名: {"videos", "videos_net", "words", "hard", "soft", "samples"}}
    """
    import glossary_lookup as GL

    index = GL.build_term_index(GL.discover_sources(),
                                l2_categories=l2_categories, levels=levels)
    rx = GL.make_matcher(index)
    if rx is None:
        return {}, 0

    stats = defaultdict(lambda: {"videos": set(), "videos_net": set(), "level": "?",
                                "words": Counter(), "hard": 0, "soft": 0,
                                "hard_words": Counter()})
    n_off = 0
    for vname, vdir in videos:
        sub = pick_subtitle(vdir)
        if not sub:
            continue
        try:
            cues = GL.parse_srt(sub)
        except Exception:
            continue
        if max_cues:
            cues = cues[:max_cues]
        text = " ".join(" ".join(body) for _i, _s, _e, body in cues)
        if not text.strip():
            continue
        n_off += 1
        for m in rx.finditer(text):
            term = m.group(0)
            entry = index.get(term.lower())
            if not entry:
                continue
            _level, path, _zh = entry
            st = stats[rel_table(path)]
            st["level"] = _level
            st["videos"].add(vname)
            cls = word_class(term, hard, soft)
            if cls == "hard":
                st["hard"] += 1
                st["hard_words"][term.strip().lower()] += 1
                continue
            if cls == "soft":
                st["soft"] += 1
            st["words"][term] += 1
            st["videos_net"].add(vname)
    return dict(stats), n_off


# ---------------- (C) 实际采用口径（02_terms.md） ----------------

# 非表来源（人类/推断/通用词/维基等）—— 不参与「表」统计
NON_TABLE_PAT = re.compile(
    r"^(\[|无$|直译|意译|用户裁定|用户确认|维基|wiki|通用|人名|服务器名|视频语境|"
    r"保留原文|未找到|未收录|推断|领域术语集|分类器|全局|本视频|http)", re.IGNORECASE)

# 层前缀（来源列里可能写成 `L1 blocks.csv` / `L1.5 mojang/redstone.csv`）
LEVEL_PREFIX = re.compile(r"^(L1(?:\.5)?|L2)[\s:/]+(?:mojang/)?", re.IGNORECASE)

# 备份/重复目录（排除，避免重复计数）
SKIP_DIR_PAT = re.compile(r"(_old\d*|_bak|DownSub|backup)", re.IGNORECASE)


def build_table_index():
    """现存表索引：{basename: [相对路径, ...]}（与 rel_table 同口径，不带 .cache/）。"""
    idx = defaultdict(list)
    for pat in ("knowledge/01_terminology/*.csv", ".cache/glossary/*.csv", ".cache/mojang/*.csv"):
        for p in glob.glob(os.path.join(BASE, pat)):
            s = rel_table(p)
            idx[os.path.basename(s)].append(s)
    return idx


def norm_adopted_source(src, table_index):
    """02_terms.md 来源列 → **[表名列表]**（无表来源返回空列表）。

    来源列是**自由文本**，实测 22 个视频出现 40+ 种写法，且有**多表组合**：

        `proper_nouns.csv + 用户指定`
        `.cache/mojang/blocks.csv / items.csv`
        `.cache/glossary/contraptions.csv + storage.csv（techmc-glossary，源分类 …）`
        `L1 engineering.csv（lag=卡顿）+ 用户确认`

    故按 `+` / `、` / ` / `（两侧空格，避免破坏路径内的 `/`）切成 token，
    逐个识别；人工/推断类 token 自动跳过。

    返回 `(tables, ambiguous)`：`ambiguous` 为该行有 token 命中**多张同名表**
    且写法未指明路径的情况（`storage.csv` 在 L1/L2 各有一张）。
    """
    s = src.strip()
    if not s or NON_TABLE_PAT.match(s):
        return [], False
    s = re.sub(r"（[^）]*）", "", s).strip()          # 去括注
    if not s:
        return [], False
    s = LEVEL_PREFIX.sub("", s).strip()

    tokens = [t.strip() for t in re.split(r"\s*\+\s*|\s*、\s*|\s+/\s+", s) if t.strip()]
    tables, ambiguous = [], False
    for tok in tokens:
        tok = tok.replace("\\", "/").strip()
        if not tok or NON_TABLE_PAT.match(tok):
            continue
        m = re.match(r"^Mojang\s+([A-Za-z0-9_.]+?)(?:\.csv)?$", tok, re.IGNORECASE)
        if m:
            name = m.group(1)
            # `Mojang zh_cn` / `Mojang en_us` 指的是**列名**（该表的语言列），不是表
            if name.lower() in ("zh_cn", "en_us", "zh", "en"):
                continue
            tables.append(f"mojang/{name}.csv")
            continue
        if tok.lower() in ("mojang", ".cache/mojang", ".cache/mojang/", "l1", "l2", "l1.5"):
            continue                                  # 泛指某层，未指明具体表 → 不可归
        # 单 token 内可能还有 `/`（如 `blocks.csv / items.csv` 已切；但 `a.csv/b.csv` 未切）
        sub = [x.strip() for x in re.split(r"/(?=[^/]*\.csv)", tok) if x.strip()]
        for t in sub:
            if not t.endswith(".csv"):
                continue
            base = os.path.basename(t)
            cands = table_index.get(base, [])
            if len(cands) == 1:
                tables.append(cands[0])
            elif len(cands) > 1:
                exact = [c for c in cands if c.endswith(t) or t in c]
                tables.append(exact[0] if exact else cands[0])
                if not exact:
                    ambiguous = True
            else:
                tables.append(f"knowledge/01_terminology/{base}")
    # 去重保序
    seen, out = set(), []
    for t in tables:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out, ambiguous


def parse_terms_md(path):
    """02_terms.md → [(原文, 译名, 来源原文)]。"""
    out = []
    for ln in open(path, encoding="utf-8"):
        t = ln.strip()
        if not t.startswith("|"):
            continue
        cols = [c.strip() for c in t.strip("|").split("|")]
        if len(cols) < 4 or cols[0] == "时间戳" or set(cols[0]) <= set("-: "):
            continue
        out.append((cols[1], cols[2], cols[3]))
    return out


def adopted_scan(videos):
    """C 口径：统计 `02_terms.md`（用户确认后的**实际采用**记录）的来源表。

    **为什么要这个口径**：A（历史 scan）与 B（离线全量重扫）都是**字面匹配**，
    含 `and`/`bit` 这类在英文里到处出现的词形噪声（`and` 命中「与门」）；
    C 是**用户逐条确认**后的结果，**无字面噪声**，直接反映
    「哪些表真被用上了」——但它也**受加载历史限制**（没加载过的表不可能被采用）。

    返回 ({表: {"videos": set, "rows": int}}, 视频数)。
    """
    table_index = build_table_index()
    stats = defaultdict(lambda: {"videos": set(), "rows": 0})
    n = 0
    n_ambig = 0
    n_multi = 0
    for vname, vdir in videos:
        p = os.path.join(vdir, "02_terms.md")
        if not os.path.exists(p):
            continue
        n += 1
        for _en, _zh, src in parse_terms_md(p):
            tbls, ambig = norm_adopted_source(src, table_index)
            if ambig:
                n_ambig += 1
            if len(tbls) > 1:
                n_multi += 1
            for tbl in tbls:
                stats[tbl]["videos"].add(vname)
                stats[tbl]["rows"] += 1
    return dict(stats), n, n_ambig, n_multi


def build_report(videos, cats, A, top, roots, predict_cues=20, offline=None, n_off=0,
                 adopted=None, n_adopted=0, n_ambig=0, n_multi=0):
    n_scan = A["n_scan"]
    tv, tvn = A["tbl_videos"], A["tbl_videos_net"]
    tw, th, ts = A["tbl_words"], A["tbl_hard"], A["tbl_soft"]
    thw = A["tbl_hard_words"]
    zero = []

    L = []
    L.append("# 术语表命中率回测")
    L.append("")
    L.append(f"- 语料根：{', '.join(os.path.relpath(r, BASE) if r.startswith(BASE) else r for r in roots)}")
    L.append(f"- 发现视频目录：**{len(videos)}**；其中有 `scan_terms.txt`：**{n_scan}**；"
             f"离线可读字幕：**{n_off}**")
    MIN_VIDEOS_DEFAULT = MIN_VIDEOS
    if len(videos) < MIN_VIDEOS_DEFAULT:
        L.append("")
        L.append(f"> ⚠️ **语料量不足（{len(videos)} < {MIN_VIDEOS_DEFAULT}）——以下命中率不可信，"
                 f"不得据此增删常驻表。**语料可能被清理过；请先补充字幕后重跑。")
    L.append("")
    L.append("**离线全量** = 用当前全部词汇表重新匹配完整字幕，不受历史加载范围限制（**主口径**）。")
    L.append("**噪声率** = 硬停用词命中数 ÷ 该表总命中数；视频级命中率对噪声不敏感，故噪声程度看这一列。")
    L.append("**现行扫描** = 读历史 `scan_terms.txt`，仅作对照（受当时 `--categories` 限制，"
             "未加载的表必显示 0% → 假零）。")
    L.append("")

    # 二、实际命中（离线全量重扫为主，现行扫描为对照）
    L.append("## 二、实际命中（离线全量重扫）")
    L.append("")
    off = offline or {}
    zero = []

    def off_stats(tbl):
        """离线口径：(净命中率, 噪声率, 净命中词数, 噪声词 Counter)。"""
        d = off.get(tbl, {})
        words = d.get("words", Counter())
        hard_n, soft_n = d.get("hard", 0), d.get("soft", 0)
        tot = sum(words.values()) + hard_n + soft_n
        nr = hard_n * 100.0 / tot if tot else 0.0
        net_n = len(d.get("videos_net", ()))
        rate = net_n * 100.0 / n_off if n_off else 0.0
        return rate, nr, len(words), d.get("hard_words", Counter())

    def off_level(tbl):
        return off.get(tbl, {}).get("level") or A["tbl_level"].get(tbl, "?")

    if not off and not n_scan:
        L.append("（无语料）")
        L.append("")
    else:
        L.append("**「离线全量」= 拿当前全部术语表重新匹配完整字幕**，不受历史"
                 " `--categories` 过滤影响——其零命中是真零命中。")
        L.append("**「现行扫描」= 读历史 `scan_terms.txt`**，仅含当时实际加载过的表"
                 "（未加载的表必显示 0% → 假零）。两列差异大即说明该表曾被漏加载。")
        L.append("")
        L.append("| 表 | 层级 | **离线全量** | 现行扫描 | 差 | 噪声率 | 净命中词数 | 高频命中词 |")
        L.append("|---|---|---|---|---|---|---|---|")
        L.append("")

        def off_net(tbl):
            return len(off.get(tbl, {}).get("videos_net", ()))

        rows = sorted(set(off) | set(tv),
                      key=lambda t: (-off_net(t), -len(tvn.get(t, ())), t))
        for tbl in rows:
            words = off.get(tbl, {}).get("words", Counter())
            hard_n = off.get(tbl, {}).get("hard", 0)
            soft_n = off.get(tbl, {}).get("soft", 0)
            tot = sum(words.values()) + hard_n + soft_n
            nr = hard_n * 100.0 / tot if tot else 0.0
            off_rate = off_stats(tbl)[0]
            cur_rate = len(tvn.get(tbl, ())) * 100.0 / n_scan if n_scan else 0.0
            delta = off_rate - cur_rate
            d_txt = f"+{delta:.0f}" if delta > 0.5 else (f"{delta:.0f}" if delta < -0.5 else "0")
            top2 = "、".join(f"`{w}`×{c}" for w, c in words.most_common(2))
            L.append(f"| `{tbl}` | {off_level(tbl)} | **{off_rate:.0f}%** | "
                     f"{cur_rate:.0f}% | {d_txt} | {nr:.0f}% | {len(words):,} | {top2 or '—'} |")
        L.append("")
        L.append("### 对照：历史 scan 产物口径")
        L.append("")
        L.append("读 `scan_terms.txt` 聚合——受当时 `--categories` 限制，"
                 "**未加载的表显示为 0%（假零）**。仅作对照，不用于判定。")
        L.append("")
        L.append("| 表 | 层级 | 净命中率（历史） | 噪声率 | 净命中词数 |")
        L.append("|---|---|---|---|---|")
        for src in sorted(tv, key=lambda s: -len(tvn.get(s, ()))):
            net = tvn.get(src, set())
            wc = tw.get(src, Counter())
            all_hits = sum(wc.values()) + th.get(src, 0) + ts.get(src, 0)
            nr = th.get(src, 0) * 100.0 / all_hits if all_hits else 0.0
            L.append(f"| `{src}` | {off_level(src)} | "
                     f"{len(net) * 100.0 / n_scan:.0f}% | {nr:.0f}% | {len(wc):,} |")
        L.append("")

        def off_stats(tbl):
            d = off.get(tbl, {})
            words = d.get("words", Counter())
            hard_n, soft_n = d.get("hard", 0), d.get("soft", 0)
            tot = sum(words.values()) + hard_n + soft_n
            nr = hard_n * 100.0 / tot if tot else 0.0
            net_n = len(d.get("videos_net", ()))
            rate = net_n * 100.0 / n_off if n_off else 0.0
            return rate, nr, len(words), d.get("hard_words", Counter())

        L.append("### 常驻候选（离线全量净命中率 ≥ 80% 且噪声率 < 30%）")
        L.append("")
        cand = [(t, *off_stats(t)[:2]) for t in off]
        cand = [(t, r, nr) for t, r, nr in cand if r >= 80 and nr < 30]
        cand.sort(key=lambda x: -x[1])
        if cand:
            term = [(t, r, nr) for t, r, nr in cand if off_level(t) in ("L1", "L2")]
            univ = [(t, r, nr) for t, r, nr in cand if off_level(t) == "L1.5"]
            if term:
                L.append("**术语层（L1/L2）——可直接用作常驻依据：**")
                L.append("")
                for t, rate, nr in term:
                    L.append(f"- `{t}` — {rate:.0f}%，噪声率 {nr:.0f}%")
                L.append("")
            if univ:
                L.append("**L1.5 Mojang 官方通用词层 —— 高命中≠该常驻，须先剔除通用词再判：**")
                L.append("")
                L.append("该层收录 `water`/`thing`/`full`/`power` 类通用词，**几乎每个视频都会命中**"
                         "（所以命中率天然高）；但其高频命中词多不是术语 → 注入有误纠风险，"
                         "**与设计判断（L1.5 按需、默认不注入）一致，不据此常驻**。")
                L.append("")
                for t, rate, nr in univ:
                    wc = off.get(t, {}).get("words", Counter())
                    top_words = "、".join(f"`{w}`" for w, _c in wc.most_common(3))
                    L.append(f"- `{t}` — {rate:.0f}%，噪声率 {nr:.0f}%（高频：{top_words}）")
                L.append("")
        else:
            L.append("（无）")
            L.append("")

        L.append("### 高噪声表（噪声率 ≥ 50%，离线口径）")
        L.append("")
        L.append("**多数命中来自字面匹配噪声 —— 不应据此常驻**，应先修扫描判据（语境消歧）。")
        L.append("")
        noisy = [(t, *off_stats(t)[1:2], off_stats(t)[3]) for t in off]
        noisy = [n for n in noisy if n[1] >= 50]
        noisy.sort(key=lambda x: -x[1])
        if noisy:
            L.append("| 表 | 噪声率 | 主要噪声词 |")
            L.append("|---|---|---|")
            for t, nr, hw in noisy:
                L.append(f"| `{t}` | {nr:.0f}% | "
                         f"{', '.join('`' + w + '`' for w, _c in hw.most_common(3)) or '—'} |")
        else:
            L.append("（无）")
        L.append("")

        # 各表高频命中词（离线口径）
        L.append("### 各表高频命中词 Top 3（离线，剔硬停用词后；供人工复核）")
        L.append("")
        L.append("| 表 | 高频命中词 |")
        L.append("|---|---|")
        for src in rows:
            wc = off.get(src, {}).get("words", Counter())
            if not wc:
                continue
            top3 = "、".join(f"`{w}`×{c}" for w, c in wc.most_common(3))
            L.append(f"| `{src}` | {top3} |")
        L.append("")

        # 零命中（以离线全量为准）
        L.append("### 零命中表（离线全量口径）")
        L.append("")
        all_tables = [rel_table(p)
                      for pat in ("knowledge/01_terminology/*.csv", ".cache/glossary/*.csv",
                                  ".cache/mojang/*.csv")
                      for p in glob.glob(os.path.join(BASE, pat))]
        zero = sorted(t for t in all_tables
                      if not off.get(t, {}).get("videos_net"))
        L.append(f"现存表 {len(all_tables)} 张；**离线全量零命中** {len(zero)} 张：")
        L.append("")
        for t in zero:
            L.append(f"- `{t}`")
        L.append("")
        L.append("> 离线口径已拿**全部术语表**扫过**完整字幕** → 零命中即真零命中。")
        L.append("> 仅两种解释：**① 该领域尚无视频**（保留待验）② **该表冗余/关键词不当**。")
        L.append("")

    # 三、实际采用（C）
    ad = adopted or {}
    L.append("## 三、实际采用（C：`02_terms.md` 确认记录）")
    L.append("")
    if not ad:
        L.append("（无 `02_terms.md` 语料）")
        L.append("")
    else:
        L.append(f"视频数：**{n_adopted}**（已排除 `_old*`/`DownSub` 等备份目录）")
        L.append("")
        L.append(f"> 源写法的局限：**多表组合行 {n_multi}**（如 `.cache/mojang/blocks.csv / items.csv`，"
                 f"两表均计一次）、**同名表歧义行 {n_ambig}**（`storage.csv` 在 L1/L2 各有一张且写法未指明路径）。")
        L.append("")
        L.append("**这是三条口径中最硬的一条**：`02_terms.md` 是用户逐条确认后的结果，"
                 "**无字面匹配噪声**（`and`/`bit` 不会出现）。它也**受加载历史限制**"
                 "（未加载过的表不可能被采用），故与 B 口径互为补充："
                 "**B 说「字幕里有这个词」，C 说「确实用上了」。**")
        L.append("")
        L.append("| 表 | 使用视频数 | 使用率 | 采用行数 | 离线全量(B) | 现行扫描(A) |")
        L.append("|---|---|---|---|---|---|")
        L.append("")
        rows_c = sorted(ad.items(), key=lambda kv: (-len(kv[1]["videos"]), -kv[1]["rows"]))
        for tbl, d in rows_c:
            n_use = len(d["videos"])
            b_rate = off_stats(tbl)[0]
            a_rate = len(tvn.get(tbl, ())) * 100.0 / n_scan if n_scan else 0.0
            L.append(f"| `{tbl}` | {n_use} | {n_use * 100.0 / max(1, n_adopted):.0f}% | "
                     f"{d['rows']:,} | {b_rate:.0f}% | {a_rate:.0f}% |")
        L.append("")
        never = sorted(set(off) - set(ad))
        if never:
            L.append(f"**离线有命中、但从未被采用**（{len(never)} 张）——"
                     "可能是噪声命中，或该表内容需人工把关才用得上：")
            L.append("")
            for t in never:
                wc = off.get(t, {}).get("words", Counter())
                top_w = "、".join(f"`{w}`" for w, _c in wc.most_common(2))
                L.append(f"- `{t}`（B {off_stats(t)[0]:.0f}%；高频：{top_w or '—'}）")
            L.append("")

    # 四、预判命中
    L.append(f"## 四、预判命中（yaml `keywords` × 前 {predict_cues} 句，命中 ≥2 次）")
    L.append("")
    pred, n_pred = gather_pred(videos, cats, limit=predict_cues)
    L.append(f"> 预判窗口 = 字幕前 **{predict_cues}** 句。窗口过小会误判为「零命中」"
             "（多数视频开头是寒暄）——可用 `--predict-cues` 调整后对比。")
    L.append("")
    if n_pred and cats:
        L.append(f"可读字幕视频：**{n_pred}**")
        L.append("")
        L.append("| 分类 | 预判命中视频数 | 预判命中率 | 关键词数 |")
        L.append("|---|---|---|---|")
        for cat in sorted(cats, key=lambda x: (-len(pred.get(x, ())), x)):
            n = len(pred.get(cat, ()))
            L.append(f"| `{cat}` | {n} | {n * 100.0 / n_pred:.0f}% | {len(cats[cat])} |")
        L.append("")
        miss = [c for c in sorted(cats) if not pred.get(c)]
        if miss:
            L.append(f"**零预判命中**：{' / '.join('`' + c + '`' for c in miss)}")
            L.append("")
    else:
        L.append("（无可用字幕或无分类配置）")
        L.append("")

    # 五、诊断
    L.append("## 五、诊断提示")
    L.append("")
    L.append("| 现象 | 解释与动作 |")
    L.append("|---|---|")
    L.append("| 离线≫历史 | 该表当时**未被加载** → 历史口径的零/低命中是假零 |")
    L.append("| B 高、C 零 | 字幕里有词形但**确认时没采用** → 多半是字面噪声，或该表需人工把关 |")
    L.append("| C 高、B 低 | 几乎不会出现（C 的采用必先有命中） |")
    L.append("| 离线高、预判零 | 该表靠全量进入而非 keywords → 关键词缺失，应补 |")
    L.append("| 噪声率高 | 命中主要是字面匹配噪声 → **不是该表重要，是扫描判据弱** |")
    L.append("| 三处都零 | 该领域尚无视频，或分类/表待退役 |")
    L.append("")

    # 六、噪声
    L.append(f"## 六、噪声观测（跨视频词频 Top {top}）")
    L.append("")
    L.append("高频繁用词命中是「字面扫描」自身的代价；这类词形不应作为独立扫描词形。")
    L.append("")
    L.append("| 词 | 命中次数 | 涉及表数 |")
    L.append("|---|---|---|")
    for w, n in A["word_counter"].most_common(top):
        L.append(f"| `{w}` | {n:,} | {len(A['word_srcs'].get(w, ()))} |")
    L.append("")

    return L, {
        "videos": len(videos), "n_scan": n_scan, "n_offline": n_off, "n_adopted": n_adopted,
        "resident": [t for t in off
                     if off_stats(t)[0] >= 80 and off_stats(t)[1] < 30
                     and off_level(t) in ("L1", "L2")],
        "resident_l15": [t for t in off
                         if off_stats(t)[0] >= 80 and off_stats(t)[1] < 30
                         and off_level(t) == "L1.5"],
        "zero": len(zero),
    }


def main():
    ap = argparse.ArgumentParser(description="术语表命中率回测（长期维护的统计工具，只读）")
    ap.add_argument("--root", action="append", default=[],
                    help="语料根目录（可多次）；默认 _work")
    ap.add_argument("--out", default=os.path.join(BASE, "_work", "_glossary_hit_rate.md"),
                    help="报告输出路径（默认 _work/_glossary_hit_rate.md）")
    ap.add_argument("--history", default=None,
                    help="命中率历史文件；给了就把本次摘要追加一行（供长期趋势对比）")
    ap.add_argument("--top", type=int, default=20, help="噪声观测条数（默认 20）")
    ap.add_argument("--predict-cues", type=int, default=20,
                    help="预判窗口：读字幕前 N 句统计 keywords 命中（默认 20）")
    ap.add_argument("--offline-cues", type=int, default=0,
                    help="离线重扫的字幕范围：0=完整字幕（默认）；N=只看前 N 句")
    ap.add_argument("--no-offline", action="store_true",
                    help="跳过离线全量重扫（仅分析历史 scan 产物，快但有假零）")
    ap.add_argument("--stopwords", default=None,
                    help="外置停用词表（每行一词，# 注释；# soft 起为软档）")
    ap.add_argument("--dry-run", action="store_true", help="只打印摘要，不写盘")
    ap.add_argument("--min-videos", type=int, default=MIN_VIDEOS,
                    help=f"最小可信样本量（默认 {MIN_VIDEOS}）；低于此数量则命中率不可信，报告会标注并告警")
    args = ap.parse_args()

    roots = [os.path.join(BASE, "_work")] if not args.root else [
        r if os.path.isabs(r) else os.path.normpath(os.path.join(BASE, r)) for r in args.root
    ]
    if args.offline_cues < 0:
        sys.exit("--offline-cues 不能为负")
    hard, soft = load_stopwords(args.stopwords)
    videos = discover_videos(roots)
    if len(videos) < args.min_videos:
        print(f"⚠️ 语料仅 {len(videos)} 个（< {args.min_videos}）——**命中率不可信**，"
              f"不要据此增删常驻表。\n"
              f"   语料可能被清理过。请先补充字幕（放入 `_input/`）或换含素材的语料根。")
    cats = parse_yaml_categories()
    A = gather(videos, hard, soft)
    offline, n_off = ({}, 0) if args.no_offline else offline_scan(
        videos, hard, soft, l2_categories=None,
        max_cues=(args.offline_cues or None))
    adopted, n_adopted, n_ambig, n_multi = adopted_scan(videos)
    lines, summary = build_report(videos, cats, A, args.top, roots,
                                  predict_cues=args.predict_cues,
                                  offline=offline, n_off=n_off,
                                  adopted=adopted, n_adopted=n_adopted,
                                  n_ambig=n_ambig, n_multi=n_multi)

    if args.dry_run:
        print("\n".join(lines))
        return

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"已写入 {args.out}")
    print(f"  视频 {summary['videos']} 个（scan {summary['n_scan']}；离线 {summary['n_offline']}；"
          f"02_terms {summary['n_adopted']}）")
    print(f"  常驻候选（术语层 L1/L2）{len(summary['resident'])} 张；"
          f"零净命中 {summary['zero']} 张；"
          f"L1.5 高命中 {len(summary['resident_l15'])} 张（不据此常驻）")
    if args.history:
        import datetime
        stamp = datetime.date.today().isoformat()
        resident = "、".join(f"`{s}`" for s in summary["resident"]) or "（无）"
        row = (f"| {stamp} | {summary['videos']} | {summary['n_scan']} | {summary['n_offline']} | "
               f"{resident} | {summary['zero']} |\n")
        new = not os.path.exists(args.history)
        os.makedirs(os.path.dirname(os.path.abspath(args.history)), exist_ok=True)
        with open(args.history, "a", encoding="utf-8") as f:
            if new:
                f.write("# 术语表命中率历史\n\n")
                f.write("| 日期 | 视频数 | 有scan | 离线字幕 | 常驻候选（离线净命中≥80% 且噪声率<30%） | 零净命中表数 |\n")
                f.write("|---|---|---|---|---|---|\n")
            f.write(row)
        print(f"已追加历史：{args.history}")


if __name__ == "__main__":
    main()
