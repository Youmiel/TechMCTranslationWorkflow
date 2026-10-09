# -*- coding: utf-8 -*-
"""机制断言自洽性复核产物校验（reflow2 / vocalign）。

校验 `<工作流>/consistency/` 各块产物的形态与句号引用合法性（**不判断矛盾是否判对**——
内容真伪由人工裁决，本脚本只保证产物可被机械消费、引用的句号真实存在）：

1. 块覆盖与 `en_timeline/` 一致（缺块 / 多余块）
2. 首行 = 固定注释行
3. 疑点行 4 字段（tab 分隔：句号 A / 句号 B / 对立主题 / 冲突说明）
4. 无矛盾行 = 单独一行 `无矛盾`，与疑点行**互斥**；二者必居其一
5. 引用句号存在于本块 `en_timeline` 且**文本有效**（非 `MISS` / 非剥离标记后为空）
6. 字段长度（告警级，不影响退出码）：对立主题 ≤20 字 / 冲突说明 ≤60 字

格式契约见 `docs/PRODUCT_FORMATS_REFLOW2.md`（reflow2）/ `docs/PRODUCT_FORMATS_VOCALIGN.md`（vocalign）
的 `consistency/chunk_<k>.txt` 节。
用法（命令根 = Project_Main/）：
    # reflow2（句号前缀 E，默认）
    python scripts/srt_reflow2_check_consistency.py reflow2/consistency/ \\
        [--etimeline reflow2/en_timeline/] [--expand] [--chunk k]
    # vocalign（句号前缀 S；长句号为全局编号）
    python scripts/srt_reflow2_check_consistency.py vocalign/consistency/ \\
        --etimeline vocalign/e0/en_timeline/ --id-prefix S [--expand]

退出码：0 = 通过；1 = 存在格式 / 引用违规
"""
import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

HEADER = "# 机制断言自洽性复核（块内对立扫描）"
NO_CONFLICT = "无矛盾"
TOPIC_MAX = 20
NOTE_MAX = 60
DEFAULT_ID_PREFIX = "E"          # reflow2 的句号前缀；vocalign 用 `--id-prefix S`（长句号）


def id_re(prefix):
    """句号正则（`E12` / `S12`）"""
    return re.compile(r"^%s(\d+)$" % re.escape(prefix))


def read(path):
    # utf-8-sig：产物可能被手工用 PowerShell 编辑，PS 5.1 默认写出带 BOM
    # （BOM 会污染首行 → 固定注释行误报），与项目其余校验脚本惯例一致
    with open(path, encoding="utf-8-sig") as f:
        return f.read()


def chunk_map(directory, pattern):
    """目录内 `chunk_<k>.<ext>` → {k: 路径}。"""
    out = {}
    if not os.path.isdir(directory):
        return out
    for name in os.listdir(directory):
        m = re.match(pattern, name)
        if m:
            out[int(m.group(1))] = os.path.join(directory, name)
    return out


def valid_e_numbers(etimeline_path, rx):
    """本块有效的句号集合（文本段为空 / MISS 的句号不参与复核）。"""
    good = set()
    for line in read(etimeline_path).splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        m = rx.match(parts[0].strip())
        if not m:
            continue
        if "-->" in parts[1]:                      # 有效锚定（MISS / `-` 均无 `-->`）
            good.add(int(m.group(1)))
    return good


def check_block(k, path, good_e, rx, prefix):
    """返回 (errors, warns)：均为 (块号, 行号, 说明) 列表。"""
    errors, warns = [], []
    text = read(path)
    lines = text.splitlines()
    if not lines or lines[0].strip() != HEADER:
        errors.append((k, 1, f"首行不是固定注释行（应为 `{HEADER}`）"))
    body = [(i + 1, ln) for i, ln in enumerate(lines[1:]) if ln.strip()]
    has_conflict = False
    has_none = False
    for lineno, raw in body:
        ln = raw.rstrip()
        if ln.startswith("#"):
            continue
        if ln.strip() == NO_CONFLICT:
            has_none = True
            continue
        has_conflict = True
        parts = ln.split("\t")
        if len(parts) != 4:
            errors.append((k, lineno, f"疑点行应 4 个 tab 分隔字段，实为 {len(parts)} 个"))
            continue
        a, b, topic, note = (p.strip() for p in parts)
        for label, token in (("句号 A", a), ("句号 B", b)):
            m = rx.match(token)
            if not m:
                errors.append((k, lineno, f"{label} 形态非法（应 `{prefix}<n>`，实为 `{token}`）"))
            elif int(m.group(1)) not in good_e:
                errors.append((k, lineno, f"{label} `{token}` 不在本块有效句号集合内"))
        if not topic:
            errors.append((k, lineno, "对立主题为空"))
        elif len(topic) > TOPIC_MAX:
            warns.append((k, lineno, f"对立主题 {len(topic)} 字 > 上限 {TOPIC_MAX}"))
        if not note:
            errors.append((k, lineno, "冲突说明为空"))
        elif len(note) > NOTE_MAX:
            warns.append((k, lineno, f"冲突说明 {len(note)} 字 > 上限 {NOTE_MAX}"))
    if has_conflict and has_none:
        errors.append((k, 0, f"`{NO_CONFLICT}` 行与疑点行并存（二者互斥）"))
    if not has_conflict and not has_none:
        errors.append((k, 0, f"既无疑点行也无 `{NO_CONFLICT}` 行（未给出复核结论）"))
    return errors, warns


def main():
    ap = argparse.ArgumentParser(description="校验 reflow2/consistency/ 产物（格式 + 句号引用）")
    ap.add_argument("consistency_dir", help="consistency 目录（如 reflow2/consistency/）")
    ap.add_argument("--etimeline", default=None,
                    help="en_timeline 目录（默认 = consistency 同级 en_timeline/）")
    ap.add_argument("--id-prefix", default=DEFAULT_ID_PREFIX,
                    help="句号前缀（reflow2 = E（默认）；vocalign 传 S）")
    ap.add_argument("--chunk", type=int, help="只校验该块（单块模式默认展开详情）")
    ap.add_argument("--expand", action="store_true", help="展开每处问题明细")
    args = ap.parse_args()
    rx = id_re(args.id_prefix)

    cdir = args.consistency_dir
    edir = args.etimeline or os.path.join(os.path.dirname(os.path.normpath(cdir)), "en_timeline")
    if not os.path.isdir(cdir):
        print(f"错误：consistency 目录不存在：{cdir}", file=sys.stderr)
        return 1
    if not os.path.isdir(edir):
        print(f"错误：en_timeline 目录不存在：{edir}（用 --etimeline 指定）", file=sys.stderr)
        return 1

    e_chunks = chunk_map(edir, r"^chunk_(\d+)\.txt$")
    c_chunks = chunk_map(cdir, r"^chunk_(\d+)\.txt$")
    if not e_chunks:
        print(f"错误：{edir} 内无 chunk_<k>.txt", file=sys.stderr)
        return 1

    targets = [args.chunk] if args.chunk else sorted(e_chunks)
    expand = args.expand or bool(args.chunk)

    total_err = total_warn = 0
    details = []
    stat = []
    for k in targets:
        if k not in e_chunks:
            details.append((k, 0, "en_timeline 无此块（块号超出范围）"))
            total_err += 1
            stat.append((k, 1, 0))
            continue
        if k not in c_chunks:
            details.append((k, 0, "缺产物文件（未派发或未写盘）"))
            total_err += 1
            stat.append((k, 1, 0))
            continue
        good_e = valid_e_numbers(e_chunks[k], rx)
        errs, warns = check_block(k, c_chunks[k], good_e, rx, args.id_prefix)
        details.extend(errs)
        total_err += len(errs)
        total_warn += len(warns)
        stat.append((k, len(errs), len(warns)))
        if expand:
            details.extend(warns)

    for k in sorted(c_chunks):
        if k not in e_chunks:
            details.append((k, 0, "多余块（en_timeline 无对应块）"))
            total_err += 1

    if not args.chunk:
        print("块级统计（块号 / 错误 / 告警）：")
        for k, e, w in stat:
            print(f"  chunk_{k:03d}: {e} / {w}")
    if details and (expand or args.expand or args.chunk):
        print("\n明细：")
        for k, lineno, msg in details:
            loc = f"chunk_{k:03d}" + (f":{lineno}" if lineno else "")
            print(f"  {loc}  {msg}")
    elif details:
        print("\n明细（--expand 展开）：")
        agg = {}
        for _, _, msg in details:
            key = msg.split("（")[0].split("，")[0]
            agg[key] = agg.get(key, 0) + 1
        for key, n in agg.items():
            print(f"  {key}: {n}")

    print(f"\n共 {total_err} 处错误、{total_warn} 处告警")
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main())
