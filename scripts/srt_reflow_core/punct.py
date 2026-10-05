# -*- coding: utf-8 -*-
"""标点功能角色层（断句/拼句的单一事实源）：把断句与拼合从“按语言硬编码标点”改为“按**功能角色**分层”。

设计（2026-09-21 用户定调“重要的不是标点符号属于哪种语言，而是标点符号承载的功能角色”）：

1. **角色表（强度降序）**——一张**跨语言通用**字符表（单一事实源在 `shared/srt_common`），
   不按语言分表：中英同形标点自然合流，异形标点靠统一强度分级：

   | 角色 | 语义 | 字符集 |
   |------|------|--------|
   | `terminator` | 句界（显示段硬边界；也是 Z/E 句界） | `。！？…．｡` + `.?!` |
   | `rparen` | 右括号后（括注插入语后可断） | 全角/半角括号右符 |
   | `strong` | 强断点（并列/引出/插入） | `；：—` + `;:` |
   | `clause` | 句内断点 | `，` + `,` |
   | `list` | 并列内部（最后手段） | `、､` |

   字符集与“断开代价”全部可配（CLI `--punct-*` / `build_profile` 参数）。

2. **拼合决策 = 代价最小化**（取代“贪心填满 `hard_max`”）：
   贪心会吞掉强断点、保留弱断点——实例 `不过有几个问题值得回答一下：第一，`(17) + `怎么搭…？`(12)，
   断点落在逗号而非冒号。代价最小化给出 `…回答一下：`(14) + `第一，怎么搭…？`(15)。
   代价 = Σ 断开处断点弱度 + Σ 段宽偏离 `[soft_min, soft_max]` 惩罚 + 碎片惩罚。

3. **例外模式（guards）统一保护层**——取代散落在 `split_en` / `split_zh` / `is_en_sentence_end` 的特判：
   - `decimal` 小数点 / 版本号（`2.17` / `1.20.4`）
   - `abbr` 英文缩写（`Mr.` / `Fig.` / `e.g.`）
   - `ordinal` 序号（`1)` `2）` `1、` `①、` `a)`）
   - `ellipsis` 省略号（`...`）不作句界
   - `bracket_balance` 括号配平（配对区间内不切 = 保护区间）

4. **启发式保护层（可配置；2026-10-05 用户裁定）**——两类「语义整体优先于标点美观」的偏好，
   统一为 `HEURISTIC_DEFAULTS`（每项都可 CLI 覆盖/关闭）：
   - `bracket_keep` 括号整体：开括号前断开（把括注整体后移）优先于括号内标点；括号内断开加罚
     （`bracket_break_penalty`）。实例 `…中继器（当然，除非你布线更巧妙）。` 不切成
     `…中继器（当然，` + `除非…`。
   - `enum_keep` 数字枚举整体：枚举（`8、8、4` / `8, 8 and 4` / `0, 3, 7, 11 and 15`）内部加罚
     （`enum_break_penalty`）；副语言侧（英文行）另有**保护区挪移**——切点落在保护区内时
     挪到保护区**外**的最近词边界（`word_cut_advantage` 阔限），修 `…on 8,` + `8 and 4 gameticks`
     这类枚举被劈开。**只对保护区生效**，不是通用就近切词（无差别启用会劣化大量标点切点）。

用法（模块）：
    from srt_reflow_core.punct import build_profile, split_atomic, pack_by_strength, split_sentences
    prof = build_profile("zh")
    units = split_units(text, lang="zh")   # 宽度阈值默认引 shared.srt_common（硬限/最小单元/目标区间）
    sents = split_sentences(text, prof)          # 按句界切句

命令根 = Project_Main/；本模块被 srt_reflow_presplit / srt_reflow2_backfill / srt_reflow2_zsent 复用。
"""
import re

from shared.srt_common import (
    text_width, SOFT_MIN, SOFT_MAX, HARD_MAX, MIN_UNIT,
    ROLE_ORDER, PUNCT_ROLE_CHARS, PUNCT_BRACKETS, LATIN_TERMINATORS, CLOSING_CHARS,
    TERMINATOR_ROLE as TERMINATOR, RPAREN_ROLE as RPAREN,
    STRONG_ROLE as STRONG, CLAUSE_ROLE as CLAUSE, LIST_ROLE as LIST,
)

# 角色字符集与括号配对的**单一事实源在 `shared/srt_common`**（跨语言通用表）；
# 本模块只保留**算法参数**（断开代价 / 宽度权重）与 DP 实现。

# 断开代价（越小越优先在此断开；terminator=0 因句界本身是硬边界、不构成“代价”）
# LIST（顿号）代价取 18.0（用户裁定“顿号处不断”）：
#   上限约束：< FRAG_PENALTY(20.0) → 宁可顿号断开，也不制造碎片；
#   下限依据：让“合并超软上限”胜过“在顿号断开”——实测案例
#   `…同为红石玩家、YouTuber 的 mattbatwings 一样，`：
#     不断顿号 = 低软 4.0 + 超软 4.2 + 逗号×3(15.0) = 23.2（用户要的结果）
#     顿号断开 = 超软 2.0 + 逗号×2(10.0) + 顿号 → 需顿号代价 > 13.2 才落败 → 取 18.0（留余量）
#   注意：顿号**仍可断**（超硬限时它是唯一出路）——完全禁止会使并列项长句切不动、直接超硬限。
# 开括号前的断点角色（非字符角色，split_atomic 在 depth==0 遇开括号时产出）：
# 把整个括注后移 = 保持括号完整的首选切法，代价应低于
# 「括号内标点 + BRACKET_BREAK_PENALTY」（如括号内逗号 = 5.0 + 6.0 = 11.0）。
BRACKET_OPEN_ROLE = "bracket_open"

DEFAULT_BREAK_COST = {
    TERMINATOR: 0.0,
    STRONG: 2.0,
    RPAREN: 3.0,      # 比 strong 高：括注后是否可断需语义判断，宽度应作主导
    BRACKET_OPEN_ROLE: 3.0,   # 开括号前断开（括注整体后移）——同 rparen 级
    CLAUSE: 5.0,
    LIST: 18.0,       # 最后手段：优先保住并列成分完整，切不动时才用
}

# 括号内断开的额外罚（**软优先**：优先保持括号完整，但段宽超限时允许断开）。
W_UNDER = 1.0         # 低于 soft_min 每单位
W_OVER = 1.0          # 高于 soft_max 每单位
FRAG_PENALTY = 20.0   # 段宽 < min_unit 的额外罚（应显著大于任何断点代价，防碎片）
# 括号内断开的额外罚（**软优先**：优先保持括号完整，但段宽超限时允许断开）。
# 取值约束（实证 LyU6a4PuJo 回归：硬禁止会使 `…中继器（当然，如果布线更糟那就另说）`(28) 无法切分）：
#   BRACKET_BREAK_PENALTY > clause(5.0)  → 宁可有逗号断点，也不轻易破括号
#   BRACKET_BREAK_PENALTY < FRAG_PENALTY(20.0) → 宁可破括号，也不制造碎片
# 6.0 同时满足两条：括号内逗号（6.0）略贵于句外逗号（5.0），但远便宜于碎片（20.0）。
BRACKET_BREAK_PENALTY = 6.0

# ---- 启发式保护规则（可配置层；2026-10-05 用户裁定）----
# 两类「语义整体优先于标点美观」的偏好，统一为**可配置的启发式层**（每个值都可 CLI 覆盖/关闭）：
#   ① 括号整体（bracket_keep）：开括号前断开（bracket_open）优先于括号内标点；括号内断开加罚
#   ② 枚举整体（enum_keep）：数字枚举（`8、8、4` / `8, 8 and 4` / `0, 3, 7, 11 and 15`）
#      **内部**断点加罚——枚举被劈开（一侧只剩 `8,` / `8、`）比切在别处更难读。
#      实例（2026-10-05 用户指出）：
#        `Well, if you said 3 repeaters on 8,` + `8 and 4 gameticks, you'd be correct.`
#      → 枚举的第一个元素被留在前一行；根因是**副语言侧**只能切在标点、而第一个 `8` 后的逗号
#        距目标最近 → 故除加罚外还需 `word_cut_advantage`（词边界回退，见 split_by_nearby_punct）。
# 关闭任一项 = 该偏好不参与代价（回退到纯断点强度 + 宽度）。
ENUM_BREAK_PENALTY = 8.0   # 枚举内部断开加罚：> clause(5.0) 宁可在别处逗号切；< FRAG_PENALTY(20.0) 宁可劈枚举也不制造碎片
WORD_CUT_ADVANTAGE = 2.0   # 副语言保护区挪移阔限：词边界比保护区标点**近出**该字符数时改用词边界
                           #   （保留余量：实测案例词边界近 6 字符 → 2.0 足够触发；
                           #    取值过大则挪移失效——曾先用 8.0 导致案例未修复，2026-10-05 自检发现）

HEURISTIC_DEFAULTS = {
    "bracket_keep": True,                              # 括号整体保护（开括号前优先断 + 括号内加罚）
    "bracket_break_penalty": BRACKET_BREAK_PENALTY,
    "enum_keep": True,                                 # 数字枚举整体保护
    "enum_break_penalty": ENUM_BREAK_PENALTY,
    "word_cut_advantage": WORD_CUT_ADVANTAGE,
}

# EN 常见缩写（缩写点不作句界；匹配须紧邻标点且以 . 结尾）
_ABBR_RE = re.compile(
    r"(?i)(?<![A-Za-z])"
    r"(?:Mr|Mrs|Ms|Dr|Prof|Rev|St|Sr|Jr|vs|etc|al|Inc|Ltd|Corp|Co|Dept|"
    r"Fig|Eq|No|Vol|e\.g|i\.e|approx|min|max|hr|sec|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
    r"\.\s*$"
)


class PunctProfile:
    """标点角色定义（角色字符集 + 括号配对 + 断开代价）。

    字符集默认取 `shared.srt_common` 的**跨语言通用表**，按项覆盖（CLI 参数经 build_profile 传入）。
    `lang` 仅作标记/诊断，不参与字符集选择——新增书写系统无需加分支，只需其标点在通用表内。
    """

    def __init__(self, lang=None, role_chars=None, brackets=None, break_cost=None,
                 heuristics=None):
        self.lang = lang or "und"
        # 启发式保护规则（括号整体 / 数字枚举整体）——未给的项取 HEURISTIC_DEFAULTS
        self.heuristics = dict(HEURISTIC_DEFAULTS)
        self.heuristics.update(heuristics or {})
        base = dict(PUNCT_ROLE_CHARS)
        for role, chars in (role_chars or {}).items():
            if chars is not None:
                base[role] = chars
        self.role_chars = base
        self.brackets = list(PUNCT_BRACKETS if brackets is None else brackets)
        self.break_cost = dict(DEFAULT_BREAK_COST)
        for role, cost in (break_cost or {}).items():
            if cost is not None:
                self.break_cost[role] = float(cost)
        # `bracket_keep=False` → 取消「开括号前优先断」这一正向偏好：
        # 让 `bracket_open` 与普通句内断点（clause）同价，括号不再被整体后移。
        if not self.heuristics.get("bracket_keep", True):
            self.break_cost[BRACKET_OPEN_ROLE] = self.break_cost.get(CLAUSE, 5.0)
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
                  brackets=None, break_cost=None, heuristics=None):
    """构造角色 profile（未给的项取**通用默认表**）。CLI `--punct-*` / `--heuristic-*` 透传入口。

    `lang` 仅作标记（不再切换字符集）；显式传入的项覆盖通用表对应角色。
    `heuristics` = 启发式保护规则覆盖（括号整体 / 数字枚举整体；见 `HEURISTIC_DEFAULTS`）。
    """
    role_chars = {}
    if terminators is not None:
        role_chars[TERMINATOR] = terminators
    if strong is not None:
        role_chars[STRONG] = strong
    if clause is not None:
        role_chars[CLAUSE] = clause
    if list_chars is not None:
        role_chars[LIST] = list_chars
    return PunctProfile(lang, role_chars, brackets, break_cost, heuristics)


# ---- 启发式：数字枚举整体保护 ----
# 枚举对判据（断点 k 在 `texts[k]` 与 `texts[k+1]` 之间）：
#   前段**以数字/数字+量词收尾**（去掉尾随标点与空白）且 后段**以数字开头**（可带 and/or/和/以及）
# 实例：`8、|8、`、`8、|4 个游戏刻`、`on 8,| 8 and 4 gameticks`、`0,| 3,` → 命中
# 反例：`So default 2,| then 4,`（后段以 then 起）→ 不命中（正确：`then` 是连接词、断点在外）
_ENUM_TAIL_RE = re.compile(r"[\d一二三四五六七八九十百千]\s*(?:个|只|种|次|格|座|层|片|页|级|条|块|倍)?\s*[，,、;；\s]*$")
_ENUM_HEAD_RE = re.compile(r"^\s*(?:and|or|和|以及)?\s*[\d一二三四五六七八九十百千]")


def _is_enum_pair(tail_text, head_text):
    """两相邻原子段之间是否为「枚举内部」断点（前段以数字收尾 且 后段以数字开头）。"""
    return bool(_ENUM_TAIL_RE.search(tail_text)) and bool(_ENUM_HEAD_RE.match(head_text))


def _enum_internal_flags(texts):
    """每个断点位置是否落在枚举内部 → `[bool] * len(texts)`（末元素恒 False，其后无断点）。"""
    n = len(texts)
    return [(_is_enum_pair(texts[k], texts[k + 1]) if k < n - 1 else False) for k in range(n)]


def _protected_span(k, texts, ends, inbr, enum_flags):
    """断点 k 所在**保护区**（枚举串 / 括号区间）的全局字符区间 `[lo, hi)`；非保护区返回 None。

    用途：副语言侧「命中保护区 → 挪到保护区外的最近词边界」——挪移目标必须落在保护区**之外**，
    否则等于没挪（`8, 8|and 4` 仍是劈开枚举）。故需先算出保护区的**字符范围**：
    - 枚举：起点 = 前段尾部数字的起始位置（`on 8,` 的 `8`）；终点 = 向右连续命中的最后一个元素末尾。
      实例 `Well, if you said 3 repeaters on 8,| 8 and 4 gameticks,` → `[33, 54)`，
      理想切点 28.9（`repeaters|on`）落在区间**左外** → 可达。
    - 括号：连续 `in_bracket` 原子段，含 `(` 的段向左扩、含 `)` 的段向右扩。
    """
    if enum_flags[k]:
        m = _ENUM_TAIL_RE.search(texts[k])
        lo = (ends[k - 1] if k > 0 else 0) + (m.start() if m else 0)
        j = k
        while j + 1 < len(texts) and _is_enum_pair(texts[j], texts[j + 1]):
            j += 1
        return lo, ends[j]
    if inbr[k]:
        a = k
        while a - 1 >= 0 and (inbr[a - 1] or "(" in texts[a - 1]):
            a -= 1
        b = k
        while b + 1 < len(texts) and inbr[b + 1]:
            b += 1
        lo = (ends[a - 1] if a > 0 else 0) + (texts[a].find("(") if "(" in texts[a] else 0)
        return lo, ends[b]
    return None


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
      作列表项出现 0 次，故取舍为“按句界处理”（列表项误切由审核发现，
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


def _extra_guard(text, punct_end):
    """标点后**未终止为正常词间隔** = 非句界（异常粘连 / 缩写内部点）。

    西文句末点后必有间隔：空白、串尾、或收尾符号（引号/括号）。否则该点是
    缩写或粘连的一部分，典型实例：
      - `W.A.I.F.U`（字母缩写）——点后是字母、无空白 → 不作句界
      - `...could. a design`（ASR 句首小写粘连，与旧 `nxt.islower()` 判据同源）
    中文句末（`。！？…`）无空格习惯，故本判据**只对西文句末点生效**（按标点种类，
    非按语言——中英混排时两侧都受保护，纯中文文本行为与改造前一致）。
    """
    if text[punct_end - 1:punct_end] not in LATIN_TERMINATORS:
        return False
    nxt = text[punct_end:punct_end + 1]
    if not nxt or nxt.isspace() or nxt in CLOSING_CHARS:
        return False
    return True


def split_sentences(text, profile, extra_guard=None):
    """按 `terminator` 角色切句 → [句文本]（标点归属前句、连续同类标点合并）。

    - 括号配平：配对区间内（depth > 0）不作句界 → 保护区间
    - 例外模式命中（小数点/缩写/省略号/序号）不作句界
    - extra_guard(text, punct_end) -> True 表示“此处不作句界”；
      省略时默认启用 `_extra_guard`（续小写粘连，按标点种类判定）
    - 忠实：句拼接（忽略空白）== 原文
    """
    if extra_guard is None:
        extra_guard = _extra_guard
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
            # 开括号前可断（把整个括注后移）——“优先保持括号完整”的首选切点：
            # 无此断点时，括号内逗号是唯一出路（`…中继器（当然，除非你布线更巧妙）。`
            # 会被切成 `…中继器（当然，` + `除非你布线更巧妙）。`，用户 2026-10-05 指出）
            if depth == 0 and buf:
                segs.append(("".join(buf), BRACKET_OPEN_ROLE, False))
                buf = []
            depth += 1
        elif ch in profile.close_chars:
            depth = max(0, depth - 1)
        role = profile.role_of(ch)
        if role is not None and not is_protected(text, i):
            # 断点 = **整个连续标点序列**（不分角色）：`》。` / `》，` / `?!` / `——` 属同一断点，
            # 不得拆开。若只并入“连续同类标点”，则 `…重制版》`(rparen) 处切一刀后，
            # 紧跟的 `，` 成了新段首 → 打包产出 `，这个系列会教你红石是怎么运作的，`
            # （用户 2026-09-27 指出；5 个项目共 6 处）。
            # 段尾角色取序列中**最强**者（break_cost 最小）——`）`+`。` 取 terminator，
            # 句界不丢（否则一行内会夹句号，用户明确否决）。
            j = i + 1
            best_role = role
            while j < n:
                cj = text[j]
                if cj in profile.open_chars or cj in profile.close_chars:
                    break                      # 括号不并入序列（depth 由主循环维护）
                r2 = profile.role_of(cj)
                if r2 is None or is_protected(text, j):
                    break
                if profile.break_cost.get(r2, 0.0) < profile.break_cost.get(best_role, 0.0):
                    best_role = r2
                j += 1
            seg = "".join(buf) + text[i:j]
            if seg.strip():
                segs.append((seg, best_role, depth > 0))
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


def split_by_nearby_punct(segs, widths, profile=None):
    """把**副语言**（非目标语言）整句切成 len(widths) 片：**就近按标点找断点**。

    用途：双语字幕里目标语言（中文）已由代价最小化 DP 定出 N 个单元，副语言侧必须
    凑成同样的 N 片才能逐片配对显示。副语言切点应落在**标点处**而非词中——机械按词数
    比例切会劈开语义单元（实测：`soft | power`、`stone pressure | plates`、
    `from 0 to | 15`）。

    做法（贪心，**不用 DP**）：逐个目标位置取“距目标最近的原子段边界”，并保证
    剩余段数足够（`i < n-1` 时至少留 1 段给剩余单元）。
    - 为何不用 DP：副语言断点素材稀疏——实测 49% 的英文整句**一个逗号都没有**
      （强断点 `;`/`—` 为 0），候选只有一个时 DP 必然退化为贪心，徒增复杂度
    - **目标位置由宽度比例给出**：`widths` 是目标语言各单元的宽度（视觉宽度口径与
      `text_width` 一致），累计比例 → 副语言累计宽度上的目标点
    - 找不到标点时退回**词边界**（不劈词）；仍不可行则均分（由 `_even_split` 兜底）
    - 保序：返回的切点严格递增

    参数
      segs   : `split_atomic(text, prof)` 的产物 `[(段文本, 段尾角色, 括号内)]`
      widths : 目标语言各单元的宽度列表（长度 = 期望片数 N）
    返回：`[(文本片段, 断点角色 or None)]`，长度 == len(widths)，拼接（去空白）== 原文。
    """
    n = len(widths)
    if n <= 0:
        return []
    atoms = []
    for s in segs:
        if not s[0]:
            continue
        atoms.append((s[0], s[1], bool(s[2]) if len(s) >= 3 else False))
    full = "".join(s for s, _r, _b in atoms)
    if n == 1:
        return [(full, None)]
    if len(atoms) < n:
        # 原子段比目标片数还少（副语言断点素材极稀疏）→ 无可依标点，退回按宽度比例的词边界切分
        return _even_split(full, n, widths)

    hz = dict(HEURISTIC_DEFAULTS)
    hz.update(getattr(profile, "heuristics", None) or {})
    cost = profile.break_cost if profile is not None else DEFAULT_BREAK_COST
    ends, acc = [], 0
    for s, _r, _b in atoms:
        acc += len(s)
        ends.append(acc)
    total_len = ends[-1]
    total_w = sum(widths) or 1
    tol = max(1.0, total_len / max(1, n - 1) / 3.0)   # “距离相近”的容忍桶宽
    # 枚举内部断点标记（`8, 8 and 4` 这类枚举不得在内部切；关闭时恒 False）
    keep_enum = bool(hz.get("enum_keep", True))
    keep_br = bool(hz.get("bracket_keep", True))
    enum_flags = (_enum_internal_flags([s for s, _r, _b in atoms]) if keep_enum
                  else [False] * len(atoms))
    inbr_flags = [(b and keep_br) for _s, _r, b in atoms]
    # 保护断点（枚举内部 / 括号内部）：**不受词边界回退影响**，但作为「同距离时的破平」更差；
    # 副语言侧对它们做「挪出保护区」的专用处理（见下），而不是在候选间加罚重排
    # （加罚重排会把更早的弱断点顶上来：实测 `Well,`(5) 胜出，2026-10-05 自检发现）。
    prot_flags = [(enum_flags[k] or inbr_flags[k]) for k in range(len(atoms))]

    # 目标点：按目标语言各单元宽度的累计比例，映射到副语言的字符位置
    cum, targets = 0.0, []
    for w in widths[:-1]:
        cum += w
        targets.append(total_len * cum / total_w)

    cuts, prev = [], 0
    for i, t in enumerate(targets):
        max_idx = len(atoms) - (n - i - 1) - 1        # 该刀允许的最大原子段下标
        legal = []
        for k in range(max_idx + 1):
            if ends[k] <= prev or atoms[k][1] is None:
                continue                              # 越界 / 无标点的原子段尾不作候选
            bucket = int(abs(ends[k] - t) / tol)      # 距离分桶：同桶内比标点强度
            # 同桶同强度时按**距目标最近**取（旧写法直接比 ends[k]，会取最早的断点：
            # `Well, if you said 3 repeaters on 8, 8 and 4 gameticks, you'd be correct.`
            # 目标 ≈29 字符却切在 `Well,`(5)——用户 2026-10-05 指出）
            # `prot`（保护区）仅作**距离完全相同**时的破平（放最后：绝不能压倒「距目标最近」，
            # 否则 `Well,`(5) 会因「非保护区」胜出——2026-10-05 自检踩过）
            legal.append((bucket, cost.get(atoms[k][1], 0.0), abs(ends[k] - t),
                          int(prot_flags[k]), ends[k], k))
        hi = ends[max_idx] if max_idx >= 0 else total_len
        hi = max(hi, prev + 1)
        if legal:
            bucket, _c, dist, _pf, cut, kb = min(legal)
            # **保护区挪移**（枚举/括号整体保护在副语言侧的落点）：
            # 最优标点若**本身落在保护区内**（枚举内部 / 括号内部），挪到保护区**外**的最近词边界。
            # 这是"从这里挪开"的逃生通道，**不是**通用就近切词——无差别启用会把大量
            # 原本切在标点上的位置改成词中切点（实测 216 段里 36 段劣化，2026-10-05 自检发现）。
            # 实例：`...3 repeaters on 8,| 8 and 4 gameticks,...` 首选标点 = 枚举内部逗号
            # → 挪到 `repeaters|on`（距目标 0.06 vs 24；保护区 `[33,54)` 外）。
            # 若最优标点在保护区之外（普通逗号），一律不动、保持标点优先。
            if prot_flags[kb]:
                span = _protected_span(kb, [s for s, _r, _b in atoms], ends, inbr_flags, enum_flags)
                wcut = _word_cut_outside(full, t, prev, hi, span) if span else None
                if (wcut is not None and abs(wcut - t) + hz.get(
                        "word_cut_advantage", WORD_CUT_ADVANTAGE) < dist):
                    cut = wcut
        else:
            cut = _nearest_word_cut(full, t, prev, hi)
        cuts.append(cut)
        prev = cut

    frags, start = [], 0
    for c in cuts + [total_len]:
        frags.append(full[start:c])
        start = c
    while len(frags) < n:
        frags.append("")
    # 片段去首尾空白：切点落在“标点 + 空格”之后时，后片会带前导空格
    # （双语行显示为 “ are often overlooked, …”，用户 2026-10-05 指出）
    return [(f.strip(), None) for f in frags[:n]]


def _word_cut_outside(text, t, lo, hi, span):
    """在 `[lo, hi)` 内按词边界就近切，且**切点须在保护区 `span` 之外**（不在 `span` 内则退回最近词边界）。

    保护区的「挪移」目标：`span` 左外侧（首选，`8, 8 and 4` 前）或右外侧；
    两侧都不可达（保护区盖满 `[lo, hi)`）时**返回 None**（保持原标点断点，宁劈枚举也不制造碎片）。
    """
    cands = [lo + m.end() for m in re.finditer(r"\S+", text[lo:hi])]
    if not cands:
        return None
    s0, s1 = span
    out = [p for p in cands if p <= s0 or p >= s1]
    if not out:
        return None
    return min(out, key=lambda p: (abs(p - t), p))


def split_secondary(text, widths, profile=None):
    """**副语言切分便捷入口**：`split_atomic` + `split_by_nearby_punct`。

    用途：目标语言已定出 N 个单元时，把副语言整句也切成 N 片（就近按标点）。
    `profile` 缺省用 en（当前副语言只有英文；传 `build_profile("ja")` 等即可复用于其它语言——
    角色表是跨语言通用表，无需改算法）。
    返回 `[片文本]`（长度 == len(widths)）。
    """
    prof = profile or build_profile("en")
    return [f for f, _r in split_by_nearby_punct(split_atomic(text, prof), widths, prof)]


def _nearest_word_cut(full, t, lo, hi):
    """在 `[lo, hi]` 内按**词边界**就近切（不劈词）；无词边界则退回 `hi`。"""
    if hi <= lo:
        return lo
    cands = [lo + m.end() for m in re.finditer(r"\S+", full[lo:hi])]
    if not cands:
        return hi
    return min(cands, key=lambda p: (abs(p - t), p))


def _even_split(full, n, widths=None):
    """无标点可用时的兜底：按**词边界**切 n 片（不劈词；片数不足时补空串）。

    有 `widths`（目标语言各单元宽度）时按**宽度比例**定词数切点——与
    `split_by_nearby_punct` 的目标位置口径一致，避免“中文段长、英文片却等长均分”
    的失衡（用户 2026-10-05 指出：`what do you think happens when I input a | pulse …`
    按均分劈在 `a | pulse` 短语中间）。
    """
    words = re.findall(r"\S+", full)
    if not words:
        return [("", None)] * n
    m = len(words)
    if widths and len(widths) == n and sum(widths) > 0:
        total_w, cum, cuts = float(sum(widths)), 0.0, []
        for w in widths[:-1]:
            cum += w
            cuts.append(m * cum / total_w)
        out, prev = [], 0
        for i, c in enumerate(cuts):
            c = max(prev + 1, min(int(round(c)), m - (n - i - 1)))
            out.append(" ".join(words[prev:c]))
            prev = c
        out.append(" ".join(words[prev:]))
        return [(s, None) for s in out]
    out = []
    for i in range(n):
        if i == n - 1:
            out.append(" ".join(words[m * i // n:]))
        else:
            out.append(" ".join(words[m * i // n:m * (i + 1) // n]))
    while len(out) < n:
        out.append("")
    return [(s, None) for s in out[:n]]


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

    取代“贪心填满 hard_max”：贪心会在弱断点断开、吞掉强断点（冒号被并进前段）。
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
    hz = dict(HEURISTIC_DEFAULTS)
    hz.update(getattr(profile, "heuristics", None) or {})
    texts = [s for s, _r, _b in norm]
    roles = [r for _s, r, _b in norm]
    inbr = [b for _s, _r, b in norm]
    widths = [text_width(s) for s in texts]
    # 启发式保护：枚举内部 / 括号内断开加罚（可配可关；关闭时该偏好不参与代价）
    enum_flags = (_enum_internal_flags(texts) if hz.get("enum_keep", True)
                  else [False] * len(texts))
    en_pen = hz.get("enum_break_penalty", ENUM_BREAK_PENALTY)
    br_pen = (bracket_penalty if bracket_penalty is not None
              else hz.get("bracket_break_penalty", BRACKET_BREAK_PENALTY))
    if not hz.get("bracket_keep", True):
        br_pen = 0.0
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
                    bc += br_pen
                if enum_flags[j - 1]:                 # 枚举内部断开 → 额外罚（数字枚举整体优先）
                    bc += en_pen
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


def split_units(text, lang="zh", hard_max=HARD_MAX, min_unit=MIN_UNIT,
                soft_min=SOFT_MIN, soft_max=SOFT_MAX, profile=None):
    """一步到位：切原子段 + 代价最小化拼合 → [(文本, 宽度)]（供拆显示段直接调用）。

    宽度阈值默认引 shared.srt_common 单一事实源（硬限/最小单元/目标区间）；调用方仍可显式覆盖。
    """
    prof = profile or build_profile(lang)
    return pack_by_strength(split_atomic(text, prof), hard_max, min_unit, soft_min, soft_max, prof)
