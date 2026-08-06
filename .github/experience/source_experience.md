# 数据源经验沉淀

> 从 `coverage_log.md` 的「发现」提炼的可复用结论，**收敛型**资产（新增递减、越沉淀越精）。
> 阶段〇优先读本文件，了解"哪个数据源擅长哪类知识"。
> 永久指南见 `SOURCE_COVERAGE.md`；流水记录见 `coverage_log.md`。

## 经验提炼规则（写入门槛）

写之前逐条套"三问"（能力 / 盲区 / 下次去哪），**只有第 3 问的答案入库**：
1. 它帮我解决了**哪一类**问题？（→ 能力，记流水）
2. 它**解决不了**什么？（→ 盲区，记流水）
3. **下次**遇到这类问题我先去哪？（→ 路由，入库）

入库条目必须为 **IF-THEN 句式**：`当〈触发条件〉时 → 查〈数据源/动作〉，因为〈原因〉。（案例：〈一行内嵌〉）`

写完后**自检四问**：
1. 删掉日期/视频名/数字后还成立吗？——不成立 → 回 `coverage_log.md`
2. 能否指导下一个视频的决策？——不能 → 回 `coverage_log.md`
3. 写明了触发条件（何时用）吗？——没写 → 补上
4. 与已有条目重复吗？——重复 → 只合并案例，不新开条

若一次产出 >5 条"规律"→ 重新过一遍以上判据（规律是稀缺的，过多说明在罗列事实）。

---

## MCP Wiki（中文 wiki）

- 当术语涉及「快照新增生物/方块」时 → 查中文 Wiki，因为 Mojang 官方表不收录快照特性。（案例：Copper Golem→铜傀儡）
- 当术语是「机制性」的、可整页覆盖多项时 → 一次抓取页面可多收，因为 Wiki 页面常包含相关子概念。（案例：下界页一次解决 nether ceiling + 8:1 坐标比）
- 当术语属于「凋灵笼/凋灵类机制」时 → 查中文 Wiki 教程页。（案例：窒息伤害、蓝色凋灵之首、wither cage）
- 盲区：Wiki 教程页可能不存在（案例：Tutorials/Item sorter 页面 404）。

## _repos/TechMCDocs（Technical Minecraft Wiki）

- 当需要「高端机制细节 / 具体 bug 号 / B36 类边界行为」时 → 查 TechMCDocs 页面，因为它按机制主题成文且含 MC- bug 号。（案例：WorldBorder.md 覆盖 4 个 bug 号；MovingBlock36.md 补 B36 行为）
- 当术语是「社区专有技术」时 → 查 TechMCDocs 而非 Wiki，因为社区技术常只在社区文档成文。（案例：sliced nether portal 源自 UpdateSuppression.md）
- 技术站点名为专有名词不译：Technical Minecraft Wiki 保留英文，不译"技术 Wiki"。
- 盲区：部分社区黑科技（1.12 字撕裂等）TechMCDocs 也无直接页面。

## Mojang 官方表

- 当需要「物品/方块标准中文名」时 → 必用 Mojang 官方表，不可自创/覆盖。
- 盲区：快照新增特性、社区术语与俗称、1.12 黑科技概念（falling block 非法形态、字撕裂、safe state 等）不在 Mojang 表收录范围。

## 知识三级路由 / 上下文推断

- 当出现「人名/服务器名」时 → 先查 `knowledge/01_terminology/proper_nouns.csv`，直接覆盖则复用。（案例：cubicmetre、Wavetech）
- 当出现「视频内部 jargon / 社区黑话」时 → 优先上下文推断 + 用户确认，因为无公开数据源。（案例：safe state、global flag、spawn tower、falling flag；末影龙寻路机制 node/pathfind/end island 同样无 Mojang 表与术语表收录，靠视频内定义"a coordinate that the dragon uses to create paths"推断；即时红石 jargon floating state、infinite frequency、update doubler、update chain、slanted rail 同样靠视频内定义推断）
- 当术语属「数字电路/逻辑门」时 → 直接用[数电常识]标准译名，因为数电译名固定、无需网络源。（案例：xyw455piBUE 视频 22 条逻辑门/锁存器/半加器/进位/LSB/MSB/时钟电路全数电常识命中）
- 人名与黑话的最终译名 → 依赖用户确认（ASR 听感/语境不可靠；大小写同样不可信，Hamster→hampter 由用户确认小写）。

## 已纠正的误判（防止重犯）

- `main storage` ≠ 直译"主存储"：在存储科技中是专有名词「全物品仓库」（TechMC Glossary：MS=全物品/全物品分类仓库）。
- `filter` 在物品分类语境 = 「分类器」，非"过滤器"（与术语表"脉冲式/无粉物品分类器"一致）。
- `world border` 取 Mojang zh_cn.json `commands.worldborder.*` 官方译名「世界边界」。
- ASR 高发主题：人名密集视频（SciCraft 成员、嘉宾）与"落沙/命令方块"主题误识别会爆发（单视频 114 条），此类视频需重点准备人名库与主题词集；实体机制讲解视频中机制词会被误听为常见词（末影龙主题：note/notes/endnote/i know→node、pat find→pathfind、gender dragon→ender dragon、iceland→island、play blocks→place blocks、by level→y level）。
