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
- 当术语属「数字电路/逻辑门」时 → 直接用[数电常识]标准译名，因为数电译名固定、无需网络源。（案例：xyw455piBUE 视频 22 条逻辑门/锁存器/半加器/进位/LSB/MSB/时钟电路全数电常识命中）
- 当术语属「世界生成/噪声算法」（Perlin noise、octave、生物群系参数等）时 → 查 zh wiki 生物群系页/噪声页，因为 1.18+ 世界生成参数与噪声术语有官方中文译名（温度/湿度/大陆性/侵蚀度/奇异性/深度、倍频程、柏林噪声），一次整页覆盖多项。（案例：p-k5MPhBSjk 69 词 L3 查证中 6 参数 + octave 全由 zh wiki 两页覆盖）
- 当字幕是「手动转录」（非 YouTube ASR 自动生成）时 → 跳过 ASR 误识别解码，直接按原文语义翻译，因为词汇正确率高、过度“修正”反而破坏原意。（案例：22UL5d4G3mY 用户明确要求保留 Mxi、free pistons 原文拼写）
- 当技术语境出现「裸数字版本号修饰词」时 → 先确认指代（1.5 flying machine = “MC 1.5 版本的飞行器”，非数量），译文显式加 “MC” 前缀防止误读成物理/渲染引擎。（案例：22UL5d4G3mY 段 21/50/57）
- 当视频属非 Minecraft 领域（人物传记/科普/纪实）时 → 跳过项目术语表与知识库加载（不适用），技术事实与专名拼写以维基百科等权威网络源为准，因为项目资产只覆盖 Minecraft 技术域。（案例：Terry Davis/TempleOS 传记，TempleOS 行数 119,667、ASU 电气工程硕士等从维基 Terry A. Davis 词条确认）
- 当术语在三级路由（knowledge → .cache → Wiki）均无权威源、属社区/视频机制专属时 → 以视频内原文定义 + 上下文推断 + 用户确认作锚，因为此类术语常由机制命名、无官方译名，用户确认是最可靠锚点（与数电常识/官方表固定译名形成对照）。（案例：uVOFckoMdIU 潜影贝农场主题 supercharger/social aggro/trash mob/aggro engine 等 16 条社区术语全用户确认；duplication mechanic 用 Wiki 机制确认）
- 当人物传记/科普类视频专名密集（人名/作品/OS/语言名）时 → 先按权威源建立正确拼写清单再翻译，因为 ASR 对专名误识别密集且大小写不可信。（案例：cue 31 "J Operating System"、cue 32 "LoseThos"、cue 34/50/69 "TempleOS"、cue 68 "HolyC"，均从维基词条校正）
- 当术语是「OS/编程语言/作品等专有名词」时 → 保留原名不译，因为无通行中文译名、保留原名最准确（与技术 Wiki 站点名保留同类）。（案例：TempleOS/HolyC/LoseThos/J Operating System/printf/Commodore 64/Apple II/VAX/Ring 0 环 0 亦仅取通用译法）
- 当装置名以「数字+gt（游戏刻）」修饰（如 16 gametick box crafter）时 → 先确认该数字指运行周期还是单次耗时，因为装置命名中的 gt 常指每 N 刻循环一次的周期（16gt = 每 0.8s 一个合成循环）而非处理耗时，误读会歪曲机制理解；译名建议「以 16gt 为周期的」而非字面直译「16 游戏刻」。（案例：QSDpdXT9SPs c106 16 gametick box crafter，用户确认 16gt 为周期，通用知识卡 `02_mechanic/box-crafter.md`）
- 当红石语境出现 wire（单复数/组合词 wires、wireless、redstone wire 等）时 → 译「线路」（广义布线/走线）或「红石（粉）线」（狭义 redstone wire），**绝不译「电线」**，因为 Minecraft 红石领域没有电工意义上的电线，wire 只指逻辑线路或红石粉线，译「电线」会窜出游戏语境。（案例：QSDpdXT9SPs r02「不需要那么多电线绕着到处走」系错翻，对应 "don't need as many wires going around the place"（c249），正确应为「线路/布线」）

## 时间戳对齐（方法论）

- 当合并/断句后的段文本与原字幕时间错位（表现为字幕比语音快/慢）时 → 用「段英文文本在原字幕文本流中顺序匹配 + cue 内线性插值」重算每段时间戳，因为流匹配定位到文本真实位置、比按 cue 粗分准确；单词级 fallback 可容忍单复数等小差异。（案例：22UL5d4G3mY 114 段全量对齐，段 51 core components/component 用 fallback）

## 语义回填（reflow 方法论）

- 当 reflow 整句锚定在原文中非唯一命中时 → 把该整句并入相邻整句作带字母后缀的独立子单元，依靠「整句锚定区间内顺序搜索」定位，因为非唯一整句独立成句会误吸附首个匹配处。（案例：S61 "So." 75 处命中→并入 S60 作 S60e；S70 "um, no." 2 处→并入 S69b）若非唯一但第一处即自身位置（如整句是后文整句的前缀子串）→ 无需并入，直接接受取第一处即可，因为第一处就是本句正确位置。（案例：QSDpdXT9SPs S47 "It's actually a really nice system." 为 S73 前缀，取第一处即 S47 自身；uVOFckoMdIU amazing./perfect./so we're going to do. 三处并入相邻整句后 r04 时间重叠消除）

- 当长句碎片对应 EN cue 物理极短（<500ms，如 "time."/"fails." 本身仅 ~300ms）时 → 只能选「接受」，因为 EN cue 时长是物理约束、行宽 26 硬限又禁止并入相邻单元，非切分不当。（案例：uVOFckoMdIU S75c "住。" 300ms、S169e "线。" 311ms——对应英文 "time."/"fails."）

- 当 `check_words` 报 01 与 r01 词序列不一致且差异含撇号时 → 检查 01 中的弯引号（U+2019）并统一替换为 ASCII `'`，因为 check_words 按 `[a-z0-9']+` 分词、弯引号与 ASCII 撇号是不同的 token。（案例：22UL5d4G3mY cue 73 "Mxi's and Myren's" 弯引号致 word 229 失配，替换后 1458/1458 通过）
- 当 r04 回填后校验段边界时 → `srt_check_segments.py` 必须加 `--allow-estimated`，因为 reflow 的中间断句估算切分点（共享 cue 按字符比例切）与 100ms 预测点合法地不在原边界集，属受控例外降级为告警。（案例：22UL5d4G3mY 254 处新造时间点全部为估算切分点、降级告警后通过）
- 当用户对 r03 断句提出调整意见（如把 1:4 改为 1:2 两段式）时 → 直接按意见改 r03 并重跑 check-r03 + reflow 全链，因为用户断句偏好优先于默认切分；改后若仍过互斥/行宽/忠实三查即可（S58 改 1:2 后 151 cue 全绿）。
- 当用户否决 ASR 修正（如"those like free pistons 保持原文"）时 → 还原 01 原文、译文按字面直译（「那些像自由活塞」）、02 术语表标注「已还原」，因为用户对原文有明确意图、ASR 推测修正不作数。（案例：22UL5d4G3mY c44 修正「five pistons」被否）
- 当补标点 subagent 在 ASR 噪声词上打 `[待审核: X]` 标记泛滥（同一块十几处）时 → 写脚本批量清理「标记文本与前文重复」的标记（subagent 复制粘贴前文词所致），因为这类标记把无效文本注入 r01 致 check_words 连环失配；清理后词序列即恢复与 01 一致。（案例：uVOFckoMdIU chunk_002 21 个 [待审核] 标记删 17 个重复后 check_words 通过）
- 当 reflow 分句任务输出超限（no-think 模型整块 90+ 整句中断）时 → 按 Z 组数拆半重派（各半 S 号从 1 连续），主会话脚本合并 + 后半 S 号 +n1 重编号，因为单块输出 token 超 max_output 是派发级硬中断、内容错误无法通过重试修复；拆半后各半输出量减半即可成功。（案例：uVOFckoMdIU chunk_002 94 整句拆 Z1-Z49/Z50-Z98 两半后成功）
- 当 task-fix 定点修 r03 拆句子单元（行宽重切）时 → 慎用——子单元拆分改动易破坏 EN/ZH 互斥拼接（task-fix 重写子单元时与整句对不齐），收敛慢；若同块错误密集（拆句互斥 + 行宽 + 锚定混合）→ 直接整块重派（C 档），因为定点修复在结构性问题前 token 反超、收敛不可控。（案例：uVOFckoMdIU chunk_002 前 2 轮 task-fix 修出 6 组新互斥破坏，拆半重派根治；chunk_004 跨块句/占位等结构问题 task-fix 两次修乱开头与末尾，改主会话脚本精确替换 6 处一次通过——结构修复脚本优于逐处定点）

- 当 ASR 预整理（en-preprocess）subagent 产物跑 `srt_check_segments --cue-exact` 报时间错位时 → 从原始 SRT 按 cue 顺序一一恢复时间码（块文件 + 合并后 01 同步），因为 subagent 可能改了时间码而 01 必须保留原时间轴；勿按「前 N 个时间行」顺序替换（块内 cue 号偏移会误改其它 cue）。（案例：uVOFckoMdIU cue 361/362/939 被改成 00:12:19,480 等新造点，按 cue 一一恢复后 1327 cue 全绿）
- 当 check-r03 报整句锚定失败（块内未找到）时 → 先验证该句 EN 在 01 全文是否命中：全文命中 = 衔接归位后的跨块句（句子 cue 跨块边界、块内锚定结构必然失败），受控例外放行直接回填，因为回填按全文锚定、非块内。（案例：uVOFckoMdIU S72/S63/S58+59/S54/S85+86 五处跨块句全文命中验证后放行，r04 无锚定错误）
- 当 r01 跨块句补全是无句末标点的半句（如【承接句】「…to have」接本块「a single cell…create two cells.」）时 → 检查 `STITCH_RE` 是否按标记分型剥离（【延伸句】必到句号、【承接句】句号或行尾、DOTALL 跨显示折行），因为非贪婪 + MULTILINE `$` 会在换行处提前截断、半句补全无法剥离致 check_words 词序污染。（案例：uVOFckoMdIU chunk_004 半句【承接句】剥离失败 r01=1560 词，分型 DOTALL 修复后一致）
- 当 reflow 走 5-2 脚本断句路径时 → check-r03 的互斥/忠实天然满足（build-r03 机械填回、模板子句段复用），主要违规集中在「行宽超限 + 引号不配对」两类（机械按宽度比例切 EN 会切进引号/引号归属漂移），task-fix 定点修复 1-2 轮可收敛、无需拆半重派；共享 cue 中间断句大量出现属 5-2 预期（受控例外）；行宽 22-26 软预警多为预设区间特征。（案例：p-k5MPhBSjk 首次 5-2——205 整句，行宽 5 处 + 引号 2 处，round1 修 5 处 + round2 修 1 处后 chunk_002 全绿；未匹配 Z/E 均 0）

## 已纠正的误判（防止重犯）

- `world border` 取 Mojang zh_cn.json `commands.worldborder.*` 官方译名「世界边界」。
- ASR 高发主题：人名密集视频（SciCraft 成员、嘉宾）与"落沙/命令方块"主题误识别会爆发（单视频 114 条），此类视频需重点准备人名库与主题词集；实体机制讲解视频中机制词会被误听为常见词（末影龙主题：note/notes/endnote/i know/red nose/screen notes→node/nodes/green nodes、pat find/path finds→pathfind、gender dragon→ender dragon、iceland→island、play blocks→place blocks、by level→y level、pallet→valid path、third→dirt、logs→blocks、carry→cut it 剪辑用语；潜影贝农场主题：sugar/shoulder/shocker/choker→shulker、agreeing/agree on/I grow→aggro、trash Muppets→trash mob、social I grow→social aggro、replacement shoes→placement chute、title ability→tileability、red coder→redstone coder、an ilmango um→omega long pulse extender）；误识别映射已按正确词聚合到 `asr_fixes.md`，翻译前先查
