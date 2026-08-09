---
name: redstone-finalize
description: 数据源效果总结（阶段三）——coverage_log 流水 + source_experience 经验提炼。
---

# 数据源效果总结（redstone-finalize）

> 定位：翻译/回填完成并确认后的收尾——写数据源覆盖流水 + 提炼可复用经验。

## 阶段三：数据源效果总结

翻译/回填完成且用户确认后：

1. **写流水**：向 `.github/experience/coverage_log.md` 追加简短流水（`日期|视频|领域|一句话关键结论|指针`），不再堆入查询数字表格与长"发现"段
2. **提炼经验**：从本视频「发现」提炼可复用结论，按 [maintain-knowledge#经验提炼规则](../maintain-knowledge/SKILL.md#经验提炼规则) 合并写入 `.github/experience/source_experience.md`（IF-THEN 句式、重复结论去重、新增递减）

目的：让"哪个数据源擅长哪类知识"沉淀为**收敛型经验**，供后续 Agent 在阶段〇优先读 `source_experience.md`（而非整个日志）。
