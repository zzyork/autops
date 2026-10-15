---
description: 按项目规范分析需求并编写可验收的实施计划
agent: plan
---

请为以下需求制定实施方案：

$ARGUMENTS

先完整阅读 AGENTS.md 指定的三份规范，再阅读 docs/AI-编程接入指南.md、FILE_INDEX.md 和相关源码。按任务加载 autops-frontend/vue 或 autops-backend/fastapi，跨端加载两组。

说明目标与非目标、现有实现、涉及文件、行为与接口契约、最小完整方案、风险和验证命令。较大任务按 docs/AI-编程接入指南.md 的计划结构输出可保存到 docs/plans/ 的内容。

本命令只规划，不实施业务代码，不安装依赖，不提交或推送。计划模式若不允许写文件，直接输出计划正文和建议路径，不提升权限写入。用户后续授权实施后按计划继续。
