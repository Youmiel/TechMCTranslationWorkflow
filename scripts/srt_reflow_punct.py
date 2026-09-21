# -*- coding: utf-8 -*-
"""标点功能角色层（断句/拼句的单一事实源）：把断句与拼合从「按语言硬编码标点」改为「按**功能角色**分层」。

设计（2026-09-21 用户定调「重要的不是标点符号属于哪种语言，而是标点符号承载的功能角色」）：

1. **角色表（强度降序）**——中英只是同一角色的不同字符映射：

   | 角色 | 语义 | zh | en |
   |------|------|----|----|
   | `terminator` | 句界（显示段硬边界；也是 Z/E 句界） | `。！？…` | `.?!` |
   | `rparen` | 右括号后（括注插入语后可断） | `）】」》` | `)]` |
   | `strong` | 强断点（并列/引出/插入） | `；：—` | `;:—` |
   | `clause` | 句内断点 | `，` | `,` |
   | `list` | 并列内部（最后手段） | `、` | — |

   角色的字符集与「断开代价」**全部可配**（CLI `--punct-*` / `build_profile` 参数）；
   默认值 = 既有行为（`terminator` 默认字符集不变 → Z 句数不变式保持、`align/` 不失效）。

2. **拼合决策 = 代价最小化**（取代「贪心填满 `hard_max`」）：
   贪心会吞掉强断点、保留弱断点——实例 `不过有几个问题值得回答一下：第一，`(17) + `怎么搭…？`(12)，
   断点落在逗号而非冒号。代价最小化给出 `…回答一下：`(14) + `第一，怎么搭…？`(15)。
   代价 = Σ 断开处断点弱度 + Σ 段宽偏离 `[soft_min, soft_max]` 惩罚 + 碎片惩罚。

3. **例外模式（guards）统一保护层**——取代散落在 `split_en` / `split_zh` / `is_en_sentence_end` 的特判：
   - `decimal` 小数点 / 版本号（`2.17` / `1.20.4`）
   - `abbr` 英文缩写（`Mr.` / `Fig.` / `e.g.`）
   - `ordinal` 序号（`1)` `2）` `1、` `①、` `a)`）
   - `ellipsis` 省略号（`...`）不作句界
   - `bracket_balance` 括号配平（配对区间内不切 = 保护区间）

用法（模块）：
    from srt_reflow_punct import build_profile, split_atomic, pack_by_strength, split_sentences
    prof = build_profile("zh")
    units = split_units(text, lang="zh", hard_max=26, min_unit=5, soft_min=15, soft_max=22)
    sents = split_sentences(text, prof)          # 按句界切句

命令根 = Project_Main/；本模块被 srt_reflow_presplit / srt_reflow2_backfill / srt_reflow2_zsent 复用。
"""
import re

from srt_reflow_common import text_width

# ---- 角色常量（强度降序；断句/拼句两侧共用同一套角色）----
TERMINATOR = "terminator"   # 句界（显示段硬边界；Z/E 句界）
RPAREN = "rparen"           # 右括号后（括注插入语后可断）
STRONG = "strong"           # 强断点（并列/引出/插入）
CLAUSE = "clause"           # 句内断点
LIST = "list"               # 并列内部（最后手段）

ROLE_ORDER = (TERMINATOR, RPAREN, STRONG, CLAUSE, LIST)   # 强度降序

# 断开代价（越小越优先在此断开；terminator=0 因句界本身是硬边界、不构成「代价」）
DEFAULT_BREAK_COST = {
    TERMINATOR: 0.0,
    STRONG: 2.0,
    RPAREN: 3.0,      # 比 strong 高：括注后是否可断需语义判断，宽度应作主导
    CLAUSE: 5.0,
    LIST: 8.0,
}

# 默认角色字符集（= 既有行为；terminator 保持现状以保 Z 句不变式）
DEFAULT_ROLE_CHARS = {
    "zh": {TERMINATOR: "。！？…", STRONG: "；：—", CLAUSE: "，", LIST: "、"},
    "en": {TERMINATOR: ".?!", STRONG: ";:—", CLAUSE: ",", LIST: ""},
}

# 默认括号配对（配对区间 = 保护区间，内部标点不跨区拼合；右括号 = rparen 角色）
DEFAULT_BRACKETS = {
    "zh": [("（", "）"), ("【", "】"), ("「", "」"), ("《", "》")],
    "en": [("(", ")"), ("[", "]")],
}

# 宽度代价权重（段宽偏离 [soft_min, soft_max] 的线性罚；碎片额外重罚）
W_UNDER = 1.0         # 低于 soft_min 每单位
W_OVER = 1.0          # 高于 soft_max 每单位
FRAG_PENALTY = 20.0   # 段宽 < min_unit 的额外罚（应显著大于任何断点代价，防碎片）
# 括号内断开的额外罚（**软优先**：优先保持括号完整，但段宽超限时允许断开）。
# 取值约束（实证 LyU6a4PuJo 回归：硬禁止会使 `…中继器（当然，如果布线更糟那就另说）`(28) 无法切分）：
#   BRACKET_BREAK_PENALTY > clause(5.0)  → 宁可有逗号断点，也不轻易破括号
#   BRACKET_BREAK_PENALTY < FRAG_PENALTY(20.0) → 宁可破括号，也不制造碎片
# 6.0 同时满足两条：括号内逗号（6.0）略贵于句外逗号（5.0），但远便宜于碎片（20.0）。
BRACKET_BREAK_PENALTY = 6.0

# EN 常见缩写（缩写点不作句界；匹配须紧邻标点且以 . 结尾）
_ABBR_RE = re.compile(
    r"(?i)(?<![A-Za-z])"
    r"(?:Mr|Mrs|Ms|Dr|Prof|Rev|St|Sr|Jr|vs|etc|al|Inc|Ltd|Corp|Co|Dept|"
    r"Fig|Eq|No|Vol|e\.g|i\.e|approx|min|max|hr|sec|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
    r"\.\s*$"
)
# 圈号数字（`①、` 这类中文列举序号的 guard）
_RING_NUM = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"


class PunctProfile:
    """标点角色定义（语言 + 角色字符集 + 括号配对 + 断开代价）。

    lang 决定默认字符集（zh/en），其余可逐项覆盖（CLI 参数经 build_profile 传入）。
    """

    def __init__(self, lang="zh", role_chars=None, brackets=None, break_cost=None):
        self.lang = lang if lang in DEFAULT_ROLE_CHARS else "zh"
        base = dict(DEFAULT_ROLE_CHARS[self.lang])
        for role, chars in (role_chars or {}).items():
            if chars is not None:
                base[role] = chars
        self.role_chars = base
        self.brackets = list(DEFAULT_BRACKETS[self.lang] if brackets is None else brackets)
        self.break_cost = dict(DEFAULT_BREAK_COST)
        for role, cost in (break_cost or {}).items():
            if cost is not None:
                self.break_cost[role] = float(cost)
        # 反向索引：字符 → 角色（按强度降序写入，先写者优先——高角色不被低角色覆盖）
        self.char_role = {}
        for role in ROLE_ORDER:
            for ch in self.role_chars.get(role, ""):
                self.char_role.setdefault(ch, role)
        self.open_chars = {o for o, _c in self.brackets}
        self.close_chars = {c for _o, c in self.brackets}
        # 右括号 = rparen（覆盖括号自身可能落在的角色）
        for ch in self.close_chars:
            self.char_role[ch] = RPAREN

    def role_of(self, ch):
        """字符 → 角色（None = 非断点字符）。"""
        return self.char_role.get(ch)

    def cost_of(self, role):
        return self.break_cost.get(role, 0.0) if role else 0.0

    def terminators(self):
        return self.role_chars.get(TERMINATOR, "")


def build_profile(lang="zh", terminators=None, strong=None, clause=None, list_chars=None,
                  brackets=None, break_cost=None):
    """构造角色 profile（未给的项取语言默认）。CLI `--punct-*` 透传入口。"""
    role_chars = {}
    if terminators is not None:
        role_chars[TERMINATOR] = terminators
    if strong is not None:
        role_chars[STRONG] = strong
    if clause is not None:
        role_chars[CLAUSE] = clause
    if list_chars is not None:
        role_chars[LIST] = list_chars
    return PunctProfile(lang, role_chars, brackets, break_cost)


# ---- 例外模式（guards）：统一保护层 ----

def is_protected(text, pos, profile=None):
    """pos 处标点是否被例外模式保护（不可作断点）。guards 集中于此，替代散落特判。

    - `decimal`：`.` 两侧均为数字（2.17 / 1.20.4 / 版本号）
    - `abbr`：EN 缩写点（Mr. / Fig. / etc.）+ 含内部点的缩写（e.g. / i.e.）
    - `ellipsis`：`...`（句内停顿，不作句界）
    - `ordinal`：**仅保护无歧义形式**——`1)` `2）` `1、` `①、` 的 `)` `）` `、`
      本就不在任何语言的 `terminator` 集合内，不会被当句界切开（无需 guard 即安全）。
      **刻意不保护 `1.` 形式**：`1. 先建地基` 与 `takes 5. Again` 形态完全相同
      （数字 + 点 + 空格 + 内容），局部字符无法区分列表项与句末点；
      实测 6 个真实视频回归中 `数字.` 作句末点（`takes 5.`）出现多次、
      作列表项出现 0 次，故取舍为「按句界处理」（列表项误切由审核发现，
      代价远低于漏切句末点导致的跨句合流）。
    """
    ch = text[pos]
    prev = text[pos - 1] if pos > 0 else ""
    nxt = text[pos + 1] if pos + 1 < len(text) else ""
    if ch == ".":
        if prev.isdigit() and nxt.isdigit():          # decimal
            return True
        if prev.isdigit() and nxt == ")":             # ordinal `1.)`（数字+.+右括号，无歧义：
            return True                               #   句末点后不可能紧跟右括号）
        # e.g. / i.e. 内部点（点后紧跟 g/e、点前是孤立 e/i）
        if nxt in "ge" and re.search(r"(?i)(?:^|[^A-Za-z])[ei]$", text[:pos]):
            return True
        if _ABBR_RE.search(text[:pos + 1]):           # abbr（Mr./Fig./etc.）
            return True
        if nxt == "." or text[max(0, pos - 2):pos + 1] == "...":   # ellipsis
            return True
    return False


def _en_extra_guard(text, punct_end):
    """EN 附加 guard：标点后无空格直接续小写 = 异常粘连、非句末（字幕句首常小写）。

    实例：`a design. My idea`（正常应切）vs `...could. a design` 这类需按语义判断处，
    与旧 `split_en.is_en_sentence_end` 的 `nxt.islower()` 判据同源。
    """
    nxt = text[punct_end:punct_end + 1]
    return bool(nxt) and nxt.islower()


def split_sentences(text, profile, extra_guard=None):
    """按 `terminator` 角色切句 → [句文本]（标点归属前句、连续同类标点合并）。

    - 括号配平：配对区间内（depth > 0）不作句界 → 保护区间
    - 例外模式命中（小数点/缩写/省略号/序号）不作句界
    - extra_guard(text, punct_end) -> True 表示「此处不作句界」；
      省略时 EN profile 自动启用 `_en_extra_guard`（续小写粘连）
    - 忠实：句拼接（忽略空白）== 原文
    """
    if extra_guard is None and profile.lang == "en":
        extra_guard = _en_extra_guard
    sents = []
    buf = []
    depth = 0
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in profile.open_chars:
            depth += 1
        elif ch in profile.close_chars:
            depth = max(0, depth - 1)
        role = profile.role_of(ch)
        if role == TERMINATOR and depth == 0 and not is_protected(text, i):
            j = i + 1
            while j < n and profile.role_of(text[j]) == TERMINATOR:   # 连续句界（?! / ……）
                j += 1
            if not (extra_guard and extra_guard(text, j)):
                buf.append(text[i:j])
                s = "".join(buf).strip()
                if s:
                    sents.append(s)
                buf = []
                i = j
                continue
        buf.append(ch)
        i += 1
    s = "".join(buf).strip()
    if s:
        sents.append(s)
    return sents


def split_atomic(text, profile):
    """按全部可断点角色切出**原子段** → [(段文本, 段尾断点角色 or None, 断点是否在括号内)]。

    - 只在标点后切、标点归属前段 → 段拼接 == 原文（忠实铁律由结构保证，段文本不 strip）
    - 例外模式命中的标点不作断点（小数点/缩写/省略号）
    - **括号内标点不禁止、只标记**（`in_bracket=True`）——拼合时给额外代价
      （`BRACKET_BREAK_PENALTY`）：优先保持括号完整，但 **段宽超限时允许断开**
      （硬禁止会导致 `就得串联相同总延迟的中继器（当然，如果布线更糟那就另说）`(28)
       这类整块无法切分 → 超硬限，实证 2026-09-21 回归）
    - 注意与 `split_sentences` 的区别：那里括号内 `terminator` 是**硬保护**（不在括号内断句），
      此处句内断点是**软代价**（显示段拆分以宽度适配为先）
    """
    segs = []
    buf = []
    depth = 0
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in profile.open_chars:
            depth += 1
        elif ch in profile.close_chars:
            depth = max(0, depth - 1)
        role = profile.role_of(ch)
        if role is not None and not is_protected(text, i):
            j = i + 1
            while j < n and profile.role_of(text[j]) == role:         # 连续同类标点并入（?! / ——）
                j += 1
            seg = "".join(buf) + text[i:j]
            if seg.strip():
                segs.append((seg, role, depth > 0))
                buf = []
            else:
                buf.append(text[i:j])
            i = j
            continue
        buf.append(ch)
        i += 1
    if buf:
        segs.append(("".join(buf), None, False))
    return segs


def _width_cost(w, min_unit, soft_min, soft_max, w_under=W_UNDER, w_over=W_OVER,
                frag_penalty=FRAG_PENALTY):
    """段宽的代价：碎片重罚 > 低于 soft_min（线性）> 高于 soft_max（线性）> 区间内 = 0。"""
    if w < min_unit:
        return frag_penalty + (min_unit - w) * w_under
    if w < soft_min:
        return (soft_min - w) * w_under
    if w > soft_max:
        return (w - soft_max) * w_over
    return 0.0


def pack_by_strength(segs, hard_max, min_unit, soft_min=None, soft_max=None,
                     profile=None, w_under=W_UNDER, w_over=W_OVER, frag_penalty=FRAG_PENALTY,
                     bracket_penalty=BRACKET_BREAK_PENALTY):
    """代价最小化拼合：`split_atomic` 的原子段 → 显示单元 [(文本, 宽度)]。

    代价 = Σ 断开处断点弱度（`profile.break_cost`）+ Σ `_width_cost`（段宽偏离目标区间）
           + Σ 括号内断开的额外罚（优先保持括号完整，但**不禁止**——硬禁止会使
             `就得串联相同总延迟的中继器（当然，如果布线更糟那就另说）`(28) 无法切分 → 超硬限）；
    约束：每段宽 ≤ `hard_max`。DP 求全局最优（原子段数通常 < 20，O(n²) 可忽略）。

    取代「贪心填满 hard_max」：贪心会在弱断点断开、吞掉强断点（冒号被并进前段）。
    输入接受 `[(文本, 角色)]` 或 `[(文本, 角色, 括号内)]`（2 元组按非括号内处理）。
    无解（存在无标点且超 hard_max 的原子段）→ 原样返回各原子段，由调用方标 err（回 r02 改写）。

    soft_min/soft_max 省略时退化为只防碎片与超硬限（不惩罚宽度偏离）。
    """
    if not segs:
        return []
    # 归一化为 (文本, 角色, 括号内) 三元组
    norm = []
    for s in segs:
        if len(s) >= 3:
            norm.append((s[0], s[1], bool(s[2])))
        else:
            norm.append((s[0], s[1], False))
    if len(norm) == 1:
        return [(norm[0][0], text_width(norm[0][0]))]
    if soft_min is None and soft_max is None:
        soft_min, soft_max = 0.0, float(hard_max)     # 无目标区间 → 仅约束 ≤ hard_max
    elif soft_min is None:
        soft_min = 0.0
    elif soft_max is None:
        soft_max = float(hard_max)
    costs = profile.break_cost if profile else DEFAULT_BREAK_COST
    texts = [s for s, _r, _b in norm]
    roles = [r for _s, r, _b in norm]
    inbr = [b for _s, _r, b in norm]
    widths = [text_width(s) for s in texts]
    n = len(norm)
    INF = float("inf")
    dp = [INF] * (n + 1)
    prev = [-1] * (n + 1)
    dp[0] = 0.0
    for j in range(1, n + 1):
        w = 0.0
        for i in range(j - 1, -1, -1):
            w += widths[i]
            if w > hard_max:                          # 段宽超硬限：更早的起点只会更宽
                break
            if dp[i] == INF:
                continue
            # 在 j-1 与 j 之间断开：代价取 segs[j-1] 的段尾断点角色（j == n 为末尾，无代价）
            if j == n:
                bc = 0.0
            else:
                bc = costs.get(roles[j - 1], 0.0)
                if inbr[j - 1]:                       # 括号内断开 → 额外罚（软优先）
                    bc += bracket_penalty
            c = dp[i] + bc + _width_cost(w, min_unit, soft_min, soft_max, w_under, w_over, frag_penalty)
            if c < dp[j]:
                dp[j] = c
                prev[j] = i
    if dp[n] == INF:                                  # 无解：存在无标点超长原子段
        return [(s, text_width(s)) for s in texts]
    cuts = []
    j = n
    while j > 0:
        i = prev[j]
        cuts.append((i, j))
        j = i
    cuts.reverse()
    return [("".join(texts[i:j]), sum(widths[i:j])) for i, j in cuts]


def split_units(text, lang="zh", hard_max=26.0, min_unit=5.0, soft_min=15.0, soft_max=22.0,
                profile=None):
    """一步到位：切原子段 + 代价最小化拼合 → [(文本, 宽度)]（供拆显示段直接调用）。"""
    prof = profile or build_profile(lang)
    return pack_by_strength(split_atomic(text, prof), hard_max, min_unit, soft_min, soft_max, prof)
