# 数据源经验沉淀

> 从 `coverage_log.md` 的「发现」提炼的可复用结论，**收敛型**资产（新增递减、越沉淀越精）。
> 阶段〇优先读本文件，了解"哪个数据源擅长哪类知识"。
> 永久指南见 `SOURCE_COVERAGE.md`；流水记录见 `coverage_log.md`。
> 除数据源经验外，本文件兼收**译名/语境裁定**与**流程方法论**（reflow/reflow2 实操教训）；词级裁定的长期落点见 `knowledge/02_mechanic/` 知识卡与 `trap_words.md`。

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
- 当术语是「机制性」的、可整页覆盖多项时 → 一次抓取页面可多收（含教程页），因为 Wiki 页面常包含相关子概念与成体系教程。（案例：下界页一次解决 nether ceiling + 8:1 坐标比；凋灵笼类查教程页解决窒息伤害、蓝色凋灵之首、wither cage）
- 当术语属于「合成/工作台 UI」时 → 查 zh wiki 合成页，因为官方用词是「合成方格」（非「合成网格」）与「合成配方」，「网格」属直觉直译的常见误译。（案例：p-k5MPhBSjk crafting grid / crafting recipe）
- 当红石语境出现 `provide redstone power` / `powered` / `charged` 时 → 查 zh wiki「红石电路/充能与激活」，因为 wiki 严格区分**供能（Powering）/ 激活（Activating）/ 充能（Charging）**，且「充能」只适用于红石导体——非导体（漏斗等）只能被供能/被激活；同一句同含「直接供能」与「经导电方块」时应分别用「供能」「充能」。（案例：ZXGpmaIcMMo c343 漏斗 provide power whether directly or through a conductive block；知识卡 `02_mechanic/power-vs-charge.md`）
- 盲区：Wiki 教程页可能不存在（案例：Tutorials/Item sorter 页面 404）。
- 当正文用 `{{only|<版别>|for=…}}` 修饰某个条件时 → 按版别展开后再读，因为 `only` 只限定括号内那点补充说明、**不否定该条件在其它版别同样成立**；把 `A{{only|be|for=X}}或B{{only|je|for=Y}}` 读成「A 仅 BE、B 仅 JE」会漏掉 JE 的 A 条件。（案例：漏斗「开启的漏斗」节——正确读法 JE=容器或碰撞箱完整方块、BE=容器（饰纹陶罐除外）；知识卡 `02_mechanic/pot.md`）

## _repos/TechMCDocs（Technical Minecraft Wiki）

- 当需要「高端机制细节 / 具体 bug 号 / B36 类边界行为」时 → 查 TechMCDocs 页面，因为它按机制主题成文且含 MC- bug 号。（案例：WorldBorder.md 覆盖 4 个 bug 号；MovingBlock36.md 补 B36 行为）
- 当术语是「社区专有技术」时 → 查 TechMCDocs 而非 Wiki，因为社区技术常只在社区文档成文。（案例：sliced nether portal 源自 UpdateSuppression.md）
- 盲区：部分社区黑科技（1.12 字撕裂等）TechMCDocs 也无直接页面。

## Mojang 官方表

- 当需要「物品/方块标准中文名」时 → 必用 Mojang 官方表，不可自创/覆盖。
- 当需要「官方中文术语」而 zh wiki 与 Mojang 词表均无该词条时 → 查游戏内置字幕键（Mojang 官方 zh_cn 语言文件的 `subtitles.*` 键，由 `scripts/glossary_fetch_mojang.py` 获取，缓存在`.cache/mojang/_download_tmp/lang/zh_cn.json`），因为官方字幕文本同样是 Mojang 官方译名来源，且与 zh wiki 相应小节一致。（案例：edkkLsir9M8 burnout→「烧毁」，社区另作「燃尽」）
- 盲区：快照新增特性、社区术语与俗称、1.12 黑科技概念（falling block 非法形态、字撕裂、safe state 等）不在 Mojang 表收录范围。

## 数据源路由（三级路由 / 领域预判）

- 当出现「人名/服务器名」时 → 先查 `knowledge/01_terminology/proper_nouns.csv`，直接覆盖则复用。（案例：cubicmetre、Wavetech）
- 当术语属「数字电路/逻辑门」时 → 直接用[数电常识]标准译名，因为数电译名固定、无需网络源。（案例：xyw455piBUE 视频 22 条逻辑门/锁存器/半加器/进位/LSB/MSB/时钟电路全数电常识命中）
- 当术语属「世界生成/噪声/算法/编程」类（Perlin noise、octave、生物群系参数、数据结构等）时 → 查 zh wiki 生物群系页/噪声页，并查 `_repos/techmc-glossary/`（coding 类），因为 1.18+ 世界生成参数与噪声术语有官方中文译名（温度/湿度/大陆性/侵蚀度/奇异性/深度、倍频程、柏林噪声），算法词部分已收在该分类、可省一次网络请求。（案例：p-k5MPhBSjk 69 词 L3 查证中 6 参数 + octave 由 zh wiki 两页覆盖、Perlin Noise/Noise Map 由 coding.csv 命中 2 词）
- 当字幕是「手动转录」（非 YouTube ASR 自动生成）时 → 跳过 ASR 误识别解码，直接按原文语义翻译，因为词汇正确率高、过度“修正”反而破坏原意。（案例：22UL5d4G3mY 用户明确要求保留 Mxi、free pistons 原文拼写）
- 当视频属非 Minecraft 领域（人物传记/科普/纪实）时 → 跳过项目术语表与知识库加载（不适用），技术事实与专名拼写以维基百科等权威网络源为准，且**专名密集时先按权威源建立正确拼写清单再翻译**，因为项目资产只覆盖 Minecraft 技术域、ASR 对专名误识别密集且大小写不可信。（案例：Terry Davis/TempleOS 传记，行数 119,667、ASU 电气工程硕士等从维基词条确认，J Operating System/LoseThos/HolyC 均由词条校正）
- 当术语在三级路由（knowledge → .cache → Wiki）均无权威源、属社区/视频机制专属时 → 以视频内原文定义 + 上下文推断 + 用户确认作锚，因为此类术语常由机制命名、无官方译名，用户确认是最可靠锚点（与数电常识/官方表固定译名形成对照）。（案例：uVOFckoMdIU 潜影贝农场主题 supercharger/social aggro/trash mob/aggro engine 等 16 条社区术语全用户确认；duplication mechanic 用 Wiki 机制确认；f7N4bmqWUco 活塞门类俗称 hipster door / flush 2x2 / Jeb door / vault door 与 updater block、0t、活塞方块流、物品实体对齐 共 8 条经用户裁定为 2×1 下吸门 / 2×2 内吸门 / Jeb 门 / 漏斗门 / 更新方块 / 0t / 活塞方块流 / 物品实体对齐）

## 译名与语境裁定（防误译）

- 当术语是「OS/编程语言/作品/技术站点名等专有名词」时 → 保留原名不译，因为无通行中文译名、保留原名最准确。（案例：TempleOS/HolyC/LoseThos/printf/Commodore 64/Apple II/VAX/Ring 0；Technical Minecraft Wiki 不译“技术 Wiki”）
- 当技术语境出现「裸数字版本号修饰词」时 → 先确认指代（1.5 flying machine = “MC 1.5 版本的飞行器”，非数量），译文显式加 “MC” 前缀防止误读成物理/渲染引擎。（案例：22UL5d4G3mY 段 21/50/57）
- 当装置名以「数字+gt（游戏刻）」修饰（如 16 gametick box crafter）时 → 先确认该数字指运行周期还是单次耗时，因为装置命名中的 gt 常指每 N 刻循环一次的周期（16gt = 每 0.8s 一个合成循环）而非处理耗时；译「以 16gt 为周期的」而非字面直译「16 游戏刻」。（案例：QSDpdXT9SPs c106 用户确认 16gt 为周期；知识卡 `02_mechanic/box-crafter.md`）
- 当红石语境出现 wire（单复数/组合词 wires、wireless、redstone wire 等）时 → 译「线路」（广义布线/走线）或「红石（粉）线」（狭义），**绝不译「电线」**，因为红石领域没有电工意义上的电线、wire 只指逻辑线路或红石粉线。（案例：QSDpdXT9SPs c249 “don't need as many wires going around the place”，曾错译为「电线绕着到处走」）
- 当术语指「网络传输 packet」（客户端-服务端通信）时 → 译「网络包」，因为游戏内 `data pack` 已占用「数据包」这一译名，同译会造成两类概念混淆（单说「封包」虽可区分但非项目约定）。（案例：p-k5MPhBSjk 用户裁定 packet→网络包，data pack→数据包）
- 当机器名/分类器名可被拆出「普通英文词」但实为**玩家 ID 词源**时（impulse sorter / Impulse Style Item Filter）→ 不按字面词义直译，常见语境译其功能名、提及作者时用原名，因为词源是人名（Impulse SV），字面直译会把机制语义带偏。（案例：ZXGpmaIcMMo c460 用户裁定「经典物品分类器」，**禁用「脉冲式分类器」**，提及作者处作「Impulse 分类器」；`trap_words.md` storage）
- 已纠正的误判：`world border` 取 Mojang zh_cn.json `commands.worldborder.*` 官方译名「世界边界」。
- 当字幕译文含数字（数量 / 分数 / 信号强度档位）时 → 套项目**数字体例**：数值与分数用阿拉伯数字（`3 个格子`、`1/3`、`2 档信号强度`），千分位**不加逗号**（`9000`），序数与虚指保留中文（`第一格`、`一件物品`）；同一概念的单位词须统一（不可一处「3 格」一处「2 档」），因为中文数字与阿拉伯数字混用会被判体例不一致，且分数与相邻数值需成对改（只改一半留残留）。（案例：ZXGpmaIcMMo 用户裁定 23 处；知识卡 `02_mechanic/subtitle-number-style.md`）
- 当译文出现半角引号，或某词需按语境**保留原文**（Discord 频道标签、`/tick rate` 等命令语法）时 → 中文引号统一「」；保留原文的条目写进 `02_terms.md`「语境例外」，因为 `srt_check_terms.py` 按译名机械匹配会持续报 ⚠️，标注后属预期告警、复核放行。（案例：edkkLsir9M8 3 处半角引号 →「」；`practical redstone tag`、`/tick rate` 两条语境例外）

## 时间戳对齐（方法论）

- 当合并/断句后的段文本与原字幕时间错位（表现为字幕比语音快/慢）时 → 用「段英文文本在原字幕文本流中顺序匹配 + cue 内线性插值」重算每段时间戳，因为流匹配定位到文本真实位置、比按 cue 粗分准确；单词级 fallback 可容忍单复数等小差异。（案例：22UL5d4G3mY 114 段全量对齐，段 51 core components/component 用 fallback）

## reflow / reflow2 方法论

> 条目按环节分组；已固化的脚本坑见本节末注记。

### 锚定与切分

- 当整句在原文中非唯一命中时 → 并入相邻整句作带字母后缀的独立子单元（靠「整句锚定区间内顺序搜索」定位），因为独立成句会误吸附首个匹配处；若非唯一但第一处即自身位置（整句是后文整句的前缀子串）→ 无需并入，直接取第一处。（案例：S61 "So." 75 处→S60e、S70 "um, no."→S69b；QSDpdXT9SPs S47 为 S73 前缀；uVOFckoMdIU 三处并入后 r04 时间重叠消除）
- 当长句碎片对应 EN cue 物理极短（<500ms，如 "time."/"fails." 仅 ~300ms）时 → 只能选「接受」，因为 cue 时长是物理约束、行宽 26 硬限又禁止并入相邻单元，非切分不当。（案例：uVOFckoMdIU S75c「住。」300ms、S169e「线。」311ms）
- 当出现片边界跨块句（块 k【延伸句】≡ 块 k+1【承接句】）时 → **先跑完三连校验、再做衔接归位**；两侧都补全时删一侧内容、**保留裸标记**（check_words 靠「有标记 + 子集」放行，删标记会报措辞不一致）；归位后两侧各报 1 处词序分歧属预期、不重跑不打回。
- 当 **reflow2** 出现片边界跨块句（块 k【延伸句】≡ 块 k+1【承接句】）时 → 按 **01 cue 归属逐词精确切分**（前块 OWNED 尾部的词留前块并去掉标记、其余删除；后块只保留其 OWNED 起点起的词），**两侧都不留标记**，因为 reflow2 的 E 句固化要求 r01 措辞与 01 **逐词一致**（锚定失败 = 0 的前提），reflow 那套「保留裸标记 + check_words 子集放行」会致 `en_timeline` 锚定失败；归属判据 = 该词的 01 cue 落在哪一块的 OWNED 区，**不能只看「哪块补全」**。（案例：ZXGpmaIcMMo c198-c200 / c399-c401 两处，第一轮留错侧致 check_words 报 3 块词序分歧，按 cue 归属重切后归零）该句块内锚定必失败 → 全文命中验证后放行，`en_timeline` 标 `(global)` 并与前一 E 交叠，`backfill` 的「时间重叠顺延」兜底。（案例：LyU6a4PuDjo 两片各 1 处分歧；uVOFckoMdIU 五处、p-k5MPhBSjk S142 全文命中放行）
- 当 en_timeline 出现时间为 `-` 的空 E 句（行注「剥离标记后为空」）时 → align 不得引用该 E，改为只引用有文本的 E，否则回填报「Z 组引用的 E 组在 en_timeline 缺失」；根因是句末省略号 `. . .` 被句末标点切分出空句。（案例：LyU6a4PuDjo E28/E29，`Z27 = E27+E28+E29` → `Z27 = E27`）
- 当为 reflow2 选 `--owned` 时 → 先看 01 相邻 cue 是否句中断、让块边界落在**句子边界**，因为边界切在句中会产生跨块句：虽有「裸标记 + 受控分歧」兜底，但归位后一侧只剩半个句子（“...Start with” / “a 2x2, ...”），中文跨块拼接语义断裂；改 `--owned`（如 200→199）使边界贴句末即归零、免归位。（案例：f7N4bmqWUco 213 cue，200 切成 c200/c201 句中 → 改 199 后 0 跨块句）

### 拆段与行宽

- 当回填打包时 → 句末标点（。！？…）是**显示段硬边界**（逐句独立成段，禁为凑宽度跨句拼合），否则 `pack_candidates` 会把「A。B，」拼进同一行（一行内夹句号，用户明确否决）；句内超宽才按「，；：→—→、」降级拆。（案例：edkkLsir9M8 用户裁定；ZXGpmaIcMMo 两段跨句粘连，加句末级后分别断为 2 段 / 3 段）
- 当某 Z 句单句内无任何句内标点（或候选子句无可切标点）且宽度 > 26 时 → 回 r02 补句内标点 / 删词（宽度先用宽度函数核验，勿心算），因为回填只能按标点切、切不动只能保留超宽；改动**保持 Z 句数不变**（不动 `。！？…`）即可复用既有 `align/`，重跑 zsent → backfill。（案例：ZXGpmaIcMMo Z76 30 字无逗号）
- 当用户要求「分号前后内容隔开」（并列项不挤在同一屏段）时 → 分号（；）**不作跨拼合点**（已固化于 `srt_reflow2_backfill.py` 的 `pack_no_cross_semicolon`），因为 `pack_candidates` 贪心填满会把分号两侧拼进同一显示段；分号因此成为显示段边界。（案例：xh511sviyXc 00:01:49–01:59 四类更新并列句，用户裁定 2026-09-17）

### 校验与受控例外

- 当 `check_words` 报 01 与 r01 词序列不一致时 → 写临时脚本按上下文窗口精确定位替换、恢复 01 原词，迭代重跑到一致（分歧常连环出现、修一处才暴露下一处）；差异含撇号时先查 01 的弯引号（U+2019）并统一为 ASCII `'`，因为 check_words 按 `[a-z0-9']+` 分词、两者是不同 token。（案例：22UL5d4G3mY cue 73 弯引号致 word 229 失配，替换后 1458/1458 通过）
- 当 r04 回填后校验段边界时 → `srt_check_segments.py` 必须加 `--allow-estimated`，因为中间断句估算切分点（共享 cue 按字符比例切）与 100ms 预测点合法地不在原边界集，属受控例外降级为告警。（案例：22UL5d4G3mY 254 处新造时间点全为估算切分点）
- 当判定空隙点与相邻语音的关系时 → 先剔除纯标记 cue 再在剩余语音 cue 上取相邻对，因为标记 cue 会切断相邻关系、漏掉跨标记的空隙。
- 当 `check_breaks` 报空隙点缺句末标点、而该空隙经复核属语义停顿（引导语归前句句尾）时 → 作受控例外放行（须 r03 不跨空隙成单元，并在 `r01_breaks.md` 复核字段注明依据），因为语义本就连贯、不属剪辑跳转。
- 当编写 `02_terms.md` 的译名列时 → 只写**纯译名**（不带 `**粗体**`、括号注释、说明文字），因为 `srt_check_terms.py` 直读该列与译文做字面匹配，带修饰会把已正确落地的译名报成「未见确认译名」。（案例：f7N4bmqWUco 6 条裁定项因 `**…**` 报 8 处假未命中）

### 产物与输入处理

- 当补标点 subagent 打 `[待审核: X]` 标记泛滥（同一块十几处，系复制粘贴前文词）时 → 脚本批量清理「标记文本与前文重复」的标记，因为无效文本注入 r01 会致 check_words 连环失配。（案例：uVOFckoMdIU chunk_002 21 处删 17）
- 当 reflow 分句任务输出超限（no-think 模型整块 90+ 整句中断）时 → 按 Z 组数拆半重派（各半 S 号从 1 连续），主会话脚本合并 + 后半 S 号 +n 重编号，因为超 max_output 是派发级硬中断、重试无法修复。（案例：uVOFckoMdIU chunk_002 94 整句拆两半成功）
- 当原字幕某段时间缺字（引用片段/meme 对白、内嵌字幕被 ASR 跳过）时 → 请用户提供原文补齐并全链重跑（改动只影响所在块、其余块可复用），补入行**必须带句末标点**，否则会与下一句粘成同一 E 句。（案例：edkkLsir9M8 c2 152→155 cue）
- 当 ASR 预整理 subagent 产物跑 `srt_check_segments --cue-exact` 报时间错位时 → 从原始 SRT 按 cue 顺序一一恢复时间码（块文件 + 合并后 01 同步），因为 01 必须保留原时间轴；勿按「前 N 个时间行」替换（块内 cue 号偏移会误改其它 cue）。（案例：uVOFckoMdIU cue 361/362/939）
- 当某块整块仅含 ASR 噪音残片时 → 补标点保留原词、翻译**输出空文件**，因为无实义可译；空内容在校验脚本中正常通过、不视为缺产物。

### 用户协作

- 当用户提出断句/译文意见时 → 直接照改并重跑受影响链路（用户偏好优先于默认切分）；用户否决 ASR 修正时还原 01 原文、按字面直译、02 标「已还原」；审核意见为**纯词级替换**（不改句末标点、不增删句）时在 r02 定点改 → 重切 Z（编号不变）→ **复用既有 align** 重跑 backfill，无需重派 task-match。（案例：22UL5d4G3mY c44 修正被否；LyU6a4PuDjo 3 轮 13 处全走此路径、0 次重派；xh511sviyXc 首轮 6 处词级改动同样复用 align 收敛）
- 当用户参与审阅时 → 每次改 r02 **前重读文件**、改**后复核关键串是否落地**，因为用户可能同时手动编辑该文件（人工编辑与脚本写入相互覆盖），按旧内容替换会 MISS 或覆盖用户改动。（案例：LyU6a4PuDjo 用户手删「（信号）」、把「允许下降」改「就下降」，复核才发现未落地）
- 当审核意见要求加「括号译注」时 → 先确认注文**归属**再动手：切句对括号内有配平保护（括号内标点不触发切句）——注文放句末句号**之后**会被并入下一 Z 句开头，放括号内也无法独立成句；若要注文独立成段，须让句末标点落在右括号**之外**（Z 句数 +1 → 必须重跑 task-match），否则注文只能与相邻句同段且常超宽。（案例：xh511sviyXc 03:09 两轮未达预期、用户裁定回退；**回退时直接复用归档 align** 重跑 backfill，无需重跑对齐）

### 修复策略

- 当 task-fix 定点修 r03 拆句子单元（行宽重切）时 → 慎用（易破坏 EN/ZH 互斥拼接、收敛慢）；同块错误密集（拆句互斥 + 行宽 + 锚定混合）→ 直接整块重派；结构性修复（跨块句/占位）→ 主会话脚本精确替换优于逐处定点。（案例：uVOFckoMdIU chunk_002 前 2 轮 task-fix 修出 6 组新互斥破坏→拆半重派根治；chunk_004 脚本替换 6 处一次通过）
- 当 reflow 走 5-2 脚本断句路径时 → check-r03 的互斥/忠实天然满足（build-r03 机械填回、模板子句段复用），违规集中在「行宽超限 + 引号不配对」，task-fix 1-2 轮可收敛、无需拆半重派；共享 cue 中间断句大量出现与行宽 22-26 软预警属预期。（案例：p-k5MPhBSjk 205 整句，行宽 5 处 + 引号 2 处两轮清零，未匹配 Z/E 均 0）

> **已固化于脚本**（再现即回归）：回填拆段以句末标点优先；EN 切句保护小数点（`1.21`/`1.20.4` 不被 `.` 切半，`srt_reflow_presplit.is_en_sentence_end`）；`STITCH_RE` 按标记分型 + DOTALL 剥离跨折行半句（【延伸句】到句号、【承接句】句号或行尾）。（案例：edkkLsir9M8 修复后 E 句 119→113；uVOFckoMdIU chunk_004 半句剥离失败致 r01=1560 词）

## ASR 误识别（防重犯）

- 当字幕出现「不像词」的短语时 → 先查 `.github/experience/asr_fixes.md`（跨视频通用、按正确词聚合），未命中再查 `_work/<视频名>/asr_fixes.md`。误听高度集中于少数主题：人名密集视频（SciCraft 成员/嘉宾）与「落沙/命令方块」主题可单视频爆发上百条，需重点准备人名库与主题词集；机制讲解视频中机制词会被误听为常见词（末影龙：note→node、pat find→pathfind、gender dragon→ender dragon、by level→y level、pallet→valid path、third→dirt、carry→cut it；潜影贝农场：sugar→shulker、I grow→aggro、trash Muppets→trash mob、replacement shoes→placement chute、title ability→tileability、red coder→redstone coder、an ilmango um→omega long pulse extender）。

