---
term: directional
aliases: [directionality, 方向性, 有方向性的]
category: mechanical
source: 人工审核（用户总结）+ 交叉查证（_repos/techmc-glossary/ general 类、_repos/storage-archive/dictionary/）
version: [通用]
status: 已确认
license: 社区通用
---

# Directional（方向性）

## 要点

directional 在红石/技术向内容里有两个互相独立的层面，翻译前先判语境：

1. **方块属性义——方块具有方向**
   描述方块时，directional 指该方块带有朝向（facing）属性、可朝六个面之一放置，例如投掷器/发射器、活塞、观察者、中继器等。
   - 典型句式：`X is a … block that is directional and can face any of its six sides`（…方块具有方向属性，六个面都能朝向）

2. **装置特质义——装置只在特定朝向下正常工作**
   描述机器/装置时，directional 指该装置对摆放朝向敏感：只在某一朝向（如朝 +X、朝 -Z、沿 Z 轴）才能正常工作；严格定义即**旋转或镜像后行为不同**。
   - 典型句式：`the downside to this grinder is that it's directional …`（这台处死装置的缺点是有方向性）

## 与「位置性」（locational）的区别

- **locational（位置性）** 指装置对**世界坐标**敏感——同一朝向、不同位置建造时行为不同（多因红石粉更新顺序依赖坐标哈希，或推动黏液结构时拆除方块的更新顺序）。
- 两者**无必然联系**（用户强调）：装置可以只有方向性、只有位置性、两者兼有，或两者都无（如 KD 刷冰机 SIFv3「没有方向性和位置性」）。
- 判据：**旋转/镜像后变** → 方向性；**换位置后变** → 位置性。

## 翻译注意事项

- 两个义项都译「方向性」；方块语境亦作「带有朝向属性」，必要时展开为「可朝向六个面」。
- 依据：`.cache/glossary/general.csv`（TechMC: Directional=方向性、Locational=位置性）、`_repos/storage-archive/dictionary/`（Directional / Locational 词条）。
- 勿与「朝向」混用——「朝向」是方块状态属性名（facing / orientation），「方向性」是方块或装置的性质。

## 备注

- 交叉查证来源：
  - TechMC Glossary（`_repos/techmc-glossary/`，general 类）：`Directional`=方向性、`Locational`=位置性
  - storage-archive 词典（`_repos/storage-archive/dictionary/`）：`Directional` / `Locational` 词条（均 APPROVED）
- 视频用例（方块属性义）：A Closer Look at Minecraft's Storage Blocks - PRR 5（ZXGpmaIcMMo）00:00:26（Dropper）；Minecraft's Observers are More Powerful Than You Think - PRR 3（xh511sviyXc）（Observer）；Minecraft's Pistons are probably The BEST Addition To The Game - PRR 4（f7N4bmqWUco）（Piston）
- 视频用例（装置特质义）：The Scaffolding Shulker Farm V3（aZP9LXhakZY）00:09:36（grinder）
- 中文用例：`_repos/tree-hole/存档&原理图/02. 方块/冰/KD的刷冰机/SIF_v3/SIFv3使用指南.txt`
- 关联：`target.md`（同类多义辨析卡）；`locational`（位置性）暂未单独建卡，见本卡对照小节。
