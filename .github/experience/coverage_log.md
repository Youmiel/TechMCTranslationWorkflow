# 数据源覆盖范围日志（流水）

> 每次翻译任务后由 Agent 在阶段三追加**简短流水**（日期|视频|领域|一句话关键结论|指针）。
> 可复用结论**提炼**到 `source_experience.md`（收敛型经验沉淀）；本文件只留流水，
> 不再堆入查询数字表格与长"发现"段。永久指南见 `SOURCE_COVERAGE.md`。

| 日期 | 视频 | 领域 | 一句话关键结论 | 指针 |
|------|------|------|----------------|------|
| 2026-07-31 | Solving Minecraft's Storage Problem | 存储 | TechMC 术语表为主源；Mojang 表盲区（快照新特性）由 Wiki 兜底 | source_experience.md |
| 2026-08-01 | Solving Minecraft's Storage Problem（审核循环修订） | 存储 | main storage→全物品仓库（TechMC 专有名词）纠正直译；filter→分类器 | source_experience.md |
| 2026-08-01 | The Minecraft World Border - Technical Analysis | 世界边界/活塞机制 | TechMCDocs 为主源；world border 取 Mojang 官方译名「世界边界」 | source_experience.md |
| 2026-08-03 | We Caged 52 Withers to Make This Farm | 凋灵笼/黑曜石农场 | Wiki 补机制术语；proper_nouns/storage 术语表直接覆盖人名与全物品仓库 | source_experience.md |
| 2026-08-04 | SciCraft Getting Command Blocks In Survival | 1.12.2 黑科技/落沙/命令方块 | 1.12.2_magic.csv 主源；ASR 114 条（人名/落沙/命令主题误识别密集） | source_experience.md |
| 2026-08-05 | How to Trap the Ender Dragon Forever in Survival Minecraft | 末影龙 AI 寻路机制 | node/pathfind 无公开源→视频内定义+上下文推断+用户确认；Mojang 表覆盖末影龙/末地水晶等标准名 | source_experience.md |
| 2026-08-06 | How 4 Blocks Revolutionized Computational Redstone | 即时红石/数电 | 数电术语（逻辑门/锁存器/加法器/进位等 22 条）全由[数电常识]覆盖无需网络源；更新抑制/即时红石 jargon 靠 Wiki 教程页 + 视频内定义推断 | source_experience.md |
| 2026-08-07 | 22UL5d4G3mY Flying Machine But Pistons Can Only Move 2 Blocks | 飞行器/推动上限 2 | 手动转录字幕免 ASR 解码；断句后时间戳错位用文本流匹配重算对齐；裸版本号“1.5 flying machine”经用户确认为 MC 1.5 版本指代 | source_experience.md |
| 2026-08-11 | V6HlbpczpDM The Life of Terry Davis - Creator of TempleOS（reflow 语义回填） | 程序员传记（非红石） | 非红石领域知识库/术语表不适用，技术事实以维基 Terry A. Davis/TempleOS 词条为准；专名（TempleOS/LoseThos/HolyC 等）ASR 误识别密集、保留原名不译；reflow 全流程领域无关照常跑通（81 整句/158 cue 全绿） | source_experience.md |
| 2026-08-11 | 22UL5d4G3mY Flying Machine But Pistons Can Only Move 2 Blocks（reflow 语义回填） | 飞行器/推动上限 2 | 0 空隙视频 r01 整段单块补标点、无强制断句点；术语全表既有登记；用户否决 c44 ASR 修正（保持原文）后按字面译；r04 校验须 --allow-estimated（估算切分点合法例外） | source_experience.md |
| 2026-08-12 | uVOFckoMdIU Engineering Minecraft's Fastest Shulker Farm（reflow 语义回填） | 潜影贝农场/实体机制 | 潜影贝主题 ASR 误听密集（shulker/aggro/trash mob/placement chute 等已聚合全局表）；社区农场类型术语按"式"构词直译；reflow 21 碎片裁决：行宽 26 硬限下优先调整切分点而非合并，剩余 17 处语义独立块接受 | source_experience.md |
| 2026-08-13 | QSDpdXT9SPs Chronos SMP - Autocrafting Creeper Storage（reflow 语义回填） | 苦力怕农场/自动合成存储 | 存储 UI/装置术语 16 条视频内定义+用户确认入库；16gt box crafter 为运行周期（正确译名「以 16gt 为周期」，非字面直译）；EN126→ZH121 5 组合句；2 长句碎片因行宽硬限只能接受；c267 "another water" ASR 疑点（疑似 nether water）未裁决 | source_experience.md |
| 2026-08-20 | uVOFckoMdIU Engineering Minecraft's Fastest Shulker Farm（reflow 二次重译，--owned 300） | 潜影贝农场/实体机制 | 二次重译全链跑通：ASR 4 块（400 cue）→ reflow 11 块（300 cue）→ 460 整句；chunk_002 拆半重派（no-think 输出超限中断，拆 Z1-Z49/Z50-Z98 两半各 S 号连续、主会话重编号）成功；补标点 subagent [待审核] 标记泛滥 21 处（复制粘贴前文词致 check_words 连环失配），脚本批量清理重复标记即恢复词序；r03 定点修复 4 轮收敛（task-fix 拆句易破坏互斥，拆半重派根治）；2 处 r02 定稿长句行宽 26.5/27.5 接受 | source_experience.md |
