# -*- coding: utf-8 -*-
"""跨块句衔接归位（reflow2 步骤 3 校验 #4 —— 文档早有设计、此前无实现）

## 文档设计（phase2.md 步骤 3 校验 #4）

> 跨块句重复（块 k `【延伸句】` ≡ 块 k+1 `【承接句】`）——**只在一侧留无标记完整句，另一侧不留文本**；
> 单边标记兜底（回填 01 cue 拼接原文留完整句删标记）

## 为什么必须有这一步

块边界由 `--owned` cue 数等分，**常落在句子中间**；ASR 字幕 93% 的 cue 末尾无句末标点、cue 间又常无缝
→ **无句末可吸附**（调 `--owned` 无法避开，实测 150–270 全范围无解）。补标点 agent 按 task-punctuate
规则 4 在块边界**两侧各补全一次**同一句（供 en_timeline 锚定），于是同一句在 r01 出现两次：

- 块 k 末：`... the hopper. 【延伸句】Hoppers are ... transfer items.`
- 块 k+1 首：`【承接句】Hoppers are ... transfer items. The shape ...`

若原样进入翻译 → 同一句被翻两遍（两块各一次）→ 中文重复、E 句时间重复。

**归位 = 翻译前删掉后块侧的重复**（保留前块的无标记完整句），使翻译看到干净输入。
（保留前块：句子归属它开始的地方，前块译完整句、后块从下一句开始。）

## 用法（命令根 = Project_Main/）

    python scripts/srt_reflow2_stitch.py reflow2/r01_results/
    python scripts/srt_reflow2_stitch.py reflow2/r01_results/ --dry-run   # 只报告
"""
import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

from srt_reflow_common import auto_wrap_file, collect_chunk_files

# 标记与「标记 + 其句」：与 srt_reflow_common.STITCH_RE 同构（此处独立声明，避免隐式耦合）
EXT_RE = re.compile(r"【延伸句】")
JOIN_RE = re.compile(r"【承接句】.*?(?:[.?!。]|$)", re.DOTALL)


def norm(s):
    """比较用归一化：去标记、去空白、小写、去首尾标点。"""
    s = s.replace("【延伸句】", "").replace("【承接句】", "")
    return re.sub(r"[^a-z0-9']", "", s.lower())


def tail_sentence(text):
    """取文本末尾句（按句末标点 `.?!` 回溯到上一个句末标点之后）。"""
    t = text.rstrip()
    m = re.search(r"[.?!][\"'\)\]]*\s*$", t)
    if not m:
        return t
    end = m.end()
    body = t[:end].rstrip()
    # 向前找上一个句末标点
    prev = None
    for mm in re.finditer(r"[.?!][\"'\)\]]*(?:\s|$)", body[:-1]):
        prev = mm
    start = prev.end() if prev else 0
    return body[start:].strip()


def main():
    ap = argparse.ArgumentParser(description="跨块句衔接归位：删后块侧重复（保留前块无标记完整句）")
    ap.add_argument("r01_dir", help="r01_results 目录（就地归位）")
    ap.add_argument("--dry-run", action="store_true", help="只报告、不写回")
    args = ap.parse_args()

    blocks = collect_chunk_files(args.r01_dir)
    if not blocks:
        sys.exit(f"❌ 无块文件：{args.r01_dir}")
    keys = sorted(blocks)
    texts = {k: open(blocks[k], encoding="utf-8").read() for k in keys}

    n_fix = 0
    for i in range(len(keys) - 1):
        ka, kb = keys[i], keys[i + 1]
        ta, tb = texts[ka], texts[kb]
        has_ext, has_join = "【延伸句】" in ta, "【承接句】" in tb
        if not (has_ext or has_join):
            continue
        # 前块末句 / 后块首句
        a_tail = tail_sentence(ta)
        m = JOIN_RE.match(tb.lstrip())
        b_head = m.group(0) if m else (tb.lstrip().split(".")[0] + "." if tb.strip() else "")
        same = bool(norm(a_tail)) and norm(a_tail) == norm(b_head)

        if has_ext and has_join and same:
            # 双侧标记 + 同一句 → 归位：前块留无标记完整句，后块整句删除
            texts[ka] = EXT_RE.sub("", ta, count=1)
            texts[ka] = re.sub(r"[ \t]{2,}", " ", texts[ka])
            texts[kb] = JOIN_RE.sub("", tb.lstrip(), count=1).lstrip()
            n_fix += 1
            print(f"🔗 归位 块{ka}【延伸句】≡ 块{kb}【承接句】 → 后块删除该句 | {a_tail[:60]}")
        else:
            # 单边标记 / 内容不等 → 只删标记、保留句子（etimeline 会剥标记；交人工确认）
            if has_ext:
                texts[ka] = EXT_RE.sub("", ta, count=1)
                texts[ka] = re.sub(r"[ \t]{2,}", " ", texts[ka])
            if has_join:
                texts[kb] = JOIN_RE.sub("", tb.lstrip(), count=1).lstrip()
                texts[kb] = re.sub(r"[ \t]{2,}", " ", texts[kb])
            n_fix += 1
            print(f"⚠️ 单边标记 块{ka}/{kb} → 仅删标记保留句（{'内容不等' if (has_ext and has_join) else '单侧'}）: {a_tail[:50]}")

    if args.dry_run:
        print(f"\n（--dry-run 未写回；命中 {n_fix} 处）")
        return 0
    for k in keys:
        if texts[k] != open(blocks[k], encoding="utf-8").read():
            with open(blocks[k], "w", encoding="utf-8", newline="\n") as fh:
                fh.write(texts[k])
            auto_wrap_file(blocks[k])          # 就地折行（显示性换行，非语义分行）
    print(f"\n✅ 衔接归位完成：{n_fix} 处（{'无命中' if not n_fix else '已写回'}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
