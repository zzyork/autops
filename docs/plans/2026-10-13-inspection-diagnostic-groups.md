# 巡检日志诊断组实施计划

2026-10-13 更新：输入模板与原文追溯继续沿用本方案；“每个诊断组单独输出一次分析”已由[AI 合并问题方案](2026-10-13-inspection-ai-merge.md)替代。现在由 AI 判断多个诊断组是否共用一份分析，后端只校验编号完整覆盖并关联原文。

目标：本地提取受规则约束的模板，每个诊断组生成一次分析，全部已采集证据可追溯。

架构：保留现有精确证据和报告持久化，在模型请求前增加诊断组构建。使用任务内 Drain3，关闭数字自动泛化，模板只允许明确的 PID/TID、请求与追踪 ID 变化；归一化正文作为最终保护键，其他差异不得合并。不新增数据库或自动失败兜底。

技术栈：现有 FastAPI、Pydantic、Vue、TypeScript、Element Plus；新增固定版本 drain3==0.9.11 用于模板提取。

## 实施步骤

1. 扩展 `schemas/inspection_analysis.py`：可选诊断组信息及原始日志字段，旧报告无需这些字段仍能读取。`inspection_analysis_input.py` 保存原文、来源表位置与结果序号，保持原精确证据粒度。
2. 新增 `services/inspection_analysis_groups.py`：还原证据片段，提取日志头和允许变化的字段，训练后按最终模板分组；保护错误原因、业务数字、目标地址和路径。未识别服务的日志按来源隔离，识别服务的日志可以跨主机、跨来源共用分析。次数为来源观察次数，不宣称唯一事件次数。
3. 修改 `inspection_analysis_engine.py`：一次提交全部诊断组的模板、少量样本和统计，不发送原始行号及全量原文；每个组恰好一个结果，后端将结果关联全部证据。未知日志仍独立分析，超限明确失败、不丢组、不重试。
4. 修改前端类型和 `InspectionAnalysisReport.vue`，复用分页与既有样式。诊断组展示次数、影响主机、来源、时间、模板及分析；原文分页查看和导出，兼容旧报告。
5. 本地测试覆盖 PID/请求 ID 合并、错误码/IP/路径/服务差异、跨主机来源、片段还原、完整映射、确定性、模型输出编号及失败边界、旧报告读取。执行相关 pytest 与 `npm run build`。

## 验收与风险

- 每个符合分析条件的已采集原始日志都进入证据，每条证据恰好归属一个诊断组。
- 模型每个诊断组恰好返回一个结果，缺失、重复、未知编号均失败。
- 代表样本最多三种正文；只省略已明确定义为非诊断字段的差异，其原值保留于原文。
- 正文未发生归一化时，完整模板已提供全部正文信息，不重复发送与模板相同的样本。
- 不降低采集量，不以高频筛选丢掉低频模板，不做泛化数字掩码或语义自动合并。
- nginx 来源的标准 `[等级] PID#TID: *连接编号` 头可提取非诊断标识，等级、错误码、正文和目标资源仍保持区分。无时间头的 journal 正文不剥离 hostname，避免误识别普通报错句子。
- Drain3 采用严格保护边界，初版对未知变量的压缩收益有限；真实日志压缩率、在线 token 和耗时需实际评估。
- 复用现有 JSON 报告列，无表迁移；既有未提交改动继续保留，不提交或推送。

参考：[Drain3](https://github.com/logpai/Drain3)、[Drain 论文](https://doi.org/10.1109/ICWS.2017.13)、[IBM 应用文章](https://developer.ibm.com/blogs/how-mining-log-templates-can-help-ai-ops-in-cloud-scale-data-centers)。本方案替代单次请求方案中的逐精确报错分析粒度，保留单次请求和完整覆盖失败边界。

## 验证记录

- 相关回归命令：`.venv/Scripts/python.exe -m pytest backend/tests/test_analysis_groups.py backend/tests/test_analysis_input_focus.py backend/tests/test_analysis_single_request.py backend/tests/test_inspection_tasks.py -k "analysis or single_request_failure or syslog or timestamp or non_log or result_indices or risks or log_collection or untimed or normal_rows or repeated or nginx" -q`，86 项通过。
- 采集与 AI 调用回归：`.venv/Scripts/python.exe -m pytest backend/tests/test_inspection_checks.py backend/tests/test_ai.py -q`，95 项通过、1 项跳过。
- `frontend` 中执行 `npm run build`，包含 TypeScript 类型检查，通过。`pip check` 与 `git diff --check` 通过；换行格式提示不属于空白错误。
- 合成数据：500 条仅进程/请求标识不同的日志加 1 条独立错误码，精确条目由 501 个降为 2 个诊断组。比较实际序列化模型输入，字符数从 149244 降为 793，减少 99.47%；这是合成数据的字符结果，不是在线 token 或真实巡检效果。
- 浏览器交互与真实模型 token/耗时尚未验证，当前未安装 Playwright/Puppeteer。完整测试集未执行完成，最初组合命令在 60 秒时限处中断，随后分组完成上述相关检查。
- 聚类边界、完整证据映射与失败行为已按两份开发规范自查；新增原文证据会增加本地报告存储和接口传输量，不影响模型输入上限或巡检采集配置。
