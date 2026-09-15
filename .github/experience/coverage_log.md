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
| 2026-08-22 | uVOFckoMdIU Engineering Minecraft's Fastest Shulker Farm（reflow 三次重译，--owned 300/200 混合） | 潜影贝农场/实体机制 | 术语库全复用（shulker_farm.csv 18 条 + proper_nouns 全量）；修复链：块 SRT 缺空行致 join 解析失败、en-preprocess subagent 改 3 处时间码（cue-exact 抓到、按块恢复）、STITCH_RE 半句跨块标记剥离 bug（分型+DOTALL 修复）、r03 定点修复（占位去标记/行宽拆分/感叹词合并/S7 互斥/S36 措辞，脚本精确替换优于 task-fix）、非唯一短句并入相邻；lazy loader 用户确认丢弃直译（可变时序装载机）；check-r03 跨块句锚定失败 5 处受控例外放行 | source_experience.md |
| 2026-08-25 | p-k5MPhBSjk I Made the World's Smallest Minecraft Server（reflow 语义回填，首次 5-2 脚本断句路径） | 世界生成/嵌入式服务器 | 首次 5-2 路径：匹配覆盖完整（未匹配 Z/E 均 0）、build-r03 机械填回 205 整句、check-r03 互斥/忠实天然满足，仅行宽 5 处 + 引号不配对 2 处定点修复 2 轮收敛；worldgen 术语全由 zh wiki 生物群系页/噪声页覆盖（6 参数 + 倍频程/柏林噪声）；dedotated wam 梗保留原文+注释；跨块句 S142 全文命中验证放行 | source_experience.md |
| 2026-09-10 | p-k5MPhBSjk I Made the World's Smallest Minecraft Server（**reflow2 首跑**·时间轴源头固化；旧 reflow 产物已备份 `_oldflow_backup_20260825`） | 世界生成/嵌入式服务器 | reflow2 全链贯通：280 cue / 210 E 句锚定失败 0 / 198 Z 句对齐 0 遗漏；片边界跨块句归后片（前片留裸标记，check_words 走「有标记+子集」放行），其 global 锚定与前一 E 交叠 5.2s → backfill 🔀 顺延兜底；4 处行宽 >26 经 r02 精简（加逗号/删词）2 轮清零；crafting grid 取 wiki 官方「合成方格」（非「合成网格」）；packet 用户裁定「网络包」（区别 data pack） | source_experience.md |
| 2026-09-13 | ZXGpmaIcMMo A Closer Look at Minecraft's Storage Blocks（PRR 5）（reflow2） | 存储元件（投掷器/发射器/漏斗/物品分类器） | 541 cue / 161 E 句锚定 0 失败 / 168 Z 句对齐 0 遗漏 / 336 显示单元；**发现回填拆段标点缺句末标点**致跨句粘连（脚本已修：拆段升级为「。！？… 优先」）；impulse sorter 裁「经典物品分类器」（禁「脉冲式分类器」，词源人名 Impulse SV）；pots→陶罐（非花盆）；storage tech 用户裁定「存储技术」/「储电」并存（x电 社区缩写体系，非机翻）；MD→Emdy（作者名）；wiki 充能页确立供能/激活/充能三级辨析（新建知识卡） | source_experience.md |
| 2026-09-16 | edkkLsir9M8 Minecraft Redstone Is Easier Than You Think（PRR 1）（reflow2） | 红石基础元件（红石粉/火把/拉杆/按钮/压力板/游戏刻） | 155 cue / 116 E 句锚定 0 失败 / 109 Z 句对齐 0 遗漏 / 211 显示单元；**切句器小数点 bug**（`1.21` 被 `.` 切断成两句）已修（`is_en_sentence_end` 加数字保护）；**用户裁定回填拆段须以句末标点为显示段硬边界**（禁跨句宽度拼合，`srt_reflow2_backfill` 已改逐句独立成段）；原字幕开头 meme 引用片段缺字（jazziRed/CraftyMasterman 对白，c2 覆盖 00:10–00:19 无文本）由用户提供原文补齐（152→155 cue，块 1 全链重跑、块 2 复用）；burnout→烧毁（游戏内置字幕键）；conductive block 用户裁定「红石导体」、hitbox 项目统一「碰撞箱」（Mojang 界面作「判定箱」）；Rexxstone→RexxStone（专有名词大小写，用户裁定） | source_experience.md |
