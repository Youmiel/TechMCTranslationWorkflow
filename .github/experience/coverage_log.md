# 数据源覆盖范围日志（流水）

> 每次翻译任务后由 Agent 在阶段三追加**简短流水**（日期|视频|领域|一句话关键结论|指针）。
> 可复用结论**提炼**到 `source_experience.md`（收敛型经验沉淀）；本文件只留流水，
> 不再堆入查询数字表格与长"发现"段。永久指南见 `SOURCE_COVERAGE.md`。
> 结论列保持**一句话**（修复链/过程细节不入表）；先提炼进 `source_experience.md`，本表只留要点与指针。
> **视频列写法**：`<视频 ID> 〈标题〉`（ID 必写、前置；见 `maintain-knowledge`「来源规范」）。

| 日期 | 视频 | 领域 | 一句话关键结论 | 指针 |
|------|------|------|----------------|------|
| 2026-07-31 | wG5Zqi1DD1I Solving Minecraft's Storage Problem | 存储 | TechMC 术语表为主源；Mojang 表盲区（快照新特性）由 Wiki 兜底 | source_experience.md |
| 2026-08-01 | wG5Zqi1DD1I Solving Minecraft's Storage Problem（审核循环修订） | 存储 | main storage→全物品仓库（TechMC 专有名词）纠正直译；filter→分类器 | source_experience.md |
| 2026-08-01 | 76uNUrHFxJE The Minecraft World Border - Technical Analysis | 世界边界/活塞机制 | TechMCDocs 为主源；world border 取 Mojang 官方译名「世界边界」 | source_experience.md |
| 2026-08-03 | YXFAM1heNOU We Caged 52 Withers to Make This Farm | 凋灵笼/黑曜石农场 | Wiki 补机制术语；proper_nouns/storage 术语表直接覆盖人名与全物品仓库 | source_experience.md |
| 2026-08-04 | 6sPS4yqC72I SciCraft Getting Command Blocks In Survival | 1.12.2 黑科技/落沙/命令方块 | 1.12.2_magic.csv 主源；ASR 114 条（人名/落沙/命令主题误识别密集） | source_experience.md |
| 2026-08-05 | kxHpyV95rB0 How to Trap the Ender Dragon Forever in Survival Minecraft | 末影龙 AI 寻路机制 | node/pathfind 无公开源→视频内定义+上下文推断+用户确认；Mojang 表覆盖末影龙/末地水晶等标准名 | source_experience.md |
| 2026-08-06 | xyw455piBUE How 4 Blocks Revolutionized Computational Redstone | 即时红石/数电 | 数电术语 22 条全由[数电常识]覆盖、无需网络源；更新抑制/即时红石 jargon 靠 Wiki 教程页 + 视频内定义 | source_experience.md |
| 2026-08-07 | 22UL5d4G3mY Flying Machine But Pistons Can Only Move 2 Blocks | 飞行器/推动上限 2 | 手动转录免 ASR 解码；时间戳错位用文本流匹配重算；裸版本号经用户确认为 MC 1.5 指代 | source_experience.md |
| 2026-08-11 | V6HlbpczpDM The Life of Terry Davis - Creator of TempleOS（reflow 语义回填） | 程序员传记（非红石） | 非红石领域项目资产不适用（事实以维基为准、专名保留原名不译），reflow 照常跑通 | source_experience.md |
| 2026-08-11 | 22UL5d4G3mY Flying Machine But Pistons Can Only Move 2 Blocks（reflow 语义回填） | 飞行器/推动上限 2 | 0 空隙视频单块补标点、术语全表既有；用户否决 c44 ASR 修正后按字面译，r04 校验须 --allow-estimated | source_experience.md |
| 2026-08-12 | uVOFckoMdIU Engineering Minecraft's Fastest Shulker Farm（reflow 语义回填） | 潜影贝农场/实体机制 | 潜影贝主题 ASR 误听密集（已聚合全局表）；社区农场术语按“式”构词直译；21 碎片裁决优先调整切分点而非合并 | source_experience.md |
| 2026-08-13 | QSDpdXT9SPs Chronos SMP - Autocrafting Creeper Storage（reflow 语义回填） | 苦力怕农场/自动合成存储 | 存储 UI/装置术语 16 条视频内定义+用户确认入库；16gt box crafter 为运行周期；长句碎片受行宽硬限只能接受 | source_experience.md |
| 2026-08-20 | uVOFckoMdIU Engineering Minecraft's Fastest Shulker Farm（reflow 二次重译，--owned 300） | 潜影贝农场/实体机制 | 全链重跑成功；chunk_002 拆半重派、[待审核] 标记脚本清理后 r03 收敛 | source_experience.md |
| 2026-08-22 | uVOFckoMdIU Engineering Minecraft's Fastest Shulker Farm（reflow 三次重译，--owned 300/200 混合） | 潜影贝农场/实体机制 | 术语库全复用；修复链（块解析、时间码恢复、STITCH_RE、r03 脚本替换）全落地；跨块句 5 处受控例外放行 | source_experience.md |
| 2026-08-25 | p-k5MPhBSjk I Made the World's Smallest Minecraft Server（reflow 语义回填，首次 5-2 脚本断句路径） | 世界生成/嵌入式服务器 | 首次 5-2 路径匹配全覆盖、机械填回 205 整句，仅行宽/引号 2 轮定点修复；worldgen 术语由 zh wiki 两页覆盖 | source_experience.md |
| 2026-09-10 | p-k5MPhBSjk I Made the World's Smallest Minecraft Server（**reflow2 首跑**·时间轴源头固化；旧 reflow 产物已备份 `_oldflow_backup_20260825`） | 世界生成/嵌入式服务器 | reflow2 首跑全链贯通（280 cue / 210 E / 198 Z 锚定对齐零失败），4 处行宽经 r02 精简清零 | source_experience.md |
| 2026-09-13 | ZXGpmaIcMMo A Closer Look at Minecraft's Storage Blocks（PRR 5）（reflow2） | 存储元件（投掷器/发射器/漏斗/物品分类器） | 541 cue 全绿；拆段缺句末标点致跨句粘连（脚本已修）；充能三级辨析新建知识卡 | source_experience.md |
| 2026-09-16 | edkkLsir9M8 Minecraft Redstone Is Easier Than You Think（PRR 1）（reflow2） | 红石基础元件（红石粉/火把/拉杆/按钮/压力板/游戏刻） | 155 cue 全绿；修切句器小数点与拆段句末标点两处脚本坑；原字幕 meme 缺字由用户补齐 | source_experience.md |
| 2026-09-17 | LyU6a4PuDjo What You Don't Know About Minecraft's Diodes（PRR 2）（reflow2） | 中继器/比较器（红石元件、信号机制、容器检测） | 350 cue 全绿（原字幕高质量、0 处 ASR 修正）；13 处词级改动复用 align 即收敛；power level/signal strength 统一「信号强度」 | source_experience.md |
