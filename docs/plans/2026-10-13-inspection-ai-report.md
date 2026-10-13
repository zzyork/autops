# 巡检 AI 汇报实施方案

**目标：** 分析本次任务所有已保存的严重、警告发现及错误日志，在巡检记录页展示可追溯的中文汇报，通过独立详情页面分别查看任务内所有服务器记录。

**设计：** 复用现有 FastAPI、SQLAlchemy、模型配置、加密凭据和 AI provider。报告输入按主机、检查及日志来源分批处理，汇总分析结果；任务检查结果与 AI 生成状态分别保存。

**技术栈：** Python、FastAPI、SQLite、SQLAlchemy、httpx、已有 LangGraph、Vue 3、TypeScript、Element Plus。

**状态：** 用户已确认数据库结构变更及自动生成接入；报告持久化、分批分析、自动/手动生成和页面展示已实施。后续补充要求已落实：记录入口默认仅历史列表，点击记录后才显示该记录的 AI 汇报及主机详情入口。无新增第三方依赖、无提交或部署。

## 现有实现与边界

- 原始巡检模型保存任务、服务器执行和检查结果；本次已新增独立 AI 报告表，避免把生成状态混入检查结果。
- `backend/app/services/inspection_checks/logs.py` 保存关键词匹配日志及来源统计。这里的“全部”指本次记录实际保存的数据，不能声称已分析服务器上未采集的全部日志。
- `backend/app/services/ai_provider.py` 支持 OpenAI 兼容和 Anthropic，限制请求上下文、响应与时间；本次新增输出限额参数，聊天保留 1024 token，报告请求显式使用 8192 token。
- `backend/app/services/ai_chat.py` 已使用 LangGraph。报告仅需文本分析，不复用带工具执行与会话副作用的对话流程。
- `backend/app/services/inspection_tasks.py` 在每台主机完成后调用 `summarize_task()`，必须等所有主机进入终态后再生成一次报告。
- `frontend/src/components/InspectionTaskDetail.vue` 已有主机选择、检查详情与原始 Markdown 导出，可以复用。

## 开源方案检索（2026-10-13）

| 方案 | 能力 | 本项目适用性 |
| --- | --- | --- |
| 现有 provider，必要时复用 LangGraph（MIT） | 模型调用与分步编排 | 推荐；已有依赖及配置，适合对保存的巡检快照做批次分析和汇报。仍需实现业务输入、覆盖校验及展示。 |
| [HolmesGPT](https://github.com/HolmesGPT/holmesgpt)（Apache-2.0） | 运维故障调查，支持日志、指标、告警及自定义 REST 数据源 | 适合之后接入 Loki、Prometheus 等实时调查；本次需独立部署及自定义巡检数据适配，成本较高。 |
| [Drain3](https://github.com/logpai/Drain3)（MIT） | 流式日志模板挖掘、归类、参数提取 | 适合大量重复日志的前处理，本身不生成中文根因分析或任务汇报；当前不新增依赖。 |
| LogAI（BSD-3-Clause） | 日志聚类、统计与机器学习异常检测 | 偏向日志分析平台，不直接满足本次报告需求；原始 Salesforce 仓库本轮访问返回 404，不作为实施依赖。 |

核对来源：

- [HolmesGPT 项目说明与许可](https://github.com/HolmesGPT/holmesgpt)
- [Drain3 项目说明](https://github.com/logpai/Drain3)及[许可](https://raw.githubusercontent.com/logpai/Drain3/master/LICENSE.txt)
- [LangGraph 许可](https://raw.githubusercontent.com/langchain-ai/langgraph/main/LICENSE)
- [LogAI 论文](https://arxiv.org/abs/2301.13415)及[可访问分支的项目说明](https://raw.githubusercontent.com/marclatour/sflogai/main/README.md)；分支不代表原项目当前维护状态。

AutoGLM 检索的本地凭据服务连接失败，本轮搜索使用可用的网络搜索工具，并阅读上述项目说明和许可；没有安装或运行这些开源项目，未验证其部署兼容性。

## 推荐产品行为

1. 新巡检任务整体结束后，自动使用当时已通过对话测试的主模型生成报告；纯分析无需工具调用能力。记录模型名称和版本快照，不自动切换备用模型。
2. 历史任务不批量自动补跑；在记录页提供“生成 AI 汇报”入口，成功后保存。已有成功报告可手动重新分析，生成失败保留上一份成功报告并明确区分本次失败状态。
3. 主模型未配置或未通过测试时状态为“不可用”，不调用模型；巡检本身继续按原有规则完成。
4. 生成失败、中断、超时或任何分批失败都不发布本轮报告；不自动重试、不返回规则拼接的替代报告。用户可手动再次生成。
5. 报告包括任务范围与采集时间、总体风险、严重问题、警告问题、错误日志分类及证据、可能原因、建议排查顺序和未完成检查。根因推断与已确认事实分开；建议只供查看，不执行远程操作。
6. 记录页展示汇报和“巡检记录详情”按钮。详情页 `/inspections/records/:taskId` 可选择本次任意服务器查看检查结果，保留原始报告导出及返回按钮。

## 任务一：报告模型、迁移与仓储

涉及文件：

- `backend/app/inspection_models.py`
- `backend/app/core/migrations/inspections.py`
- `backend/app/repositories/inspections.py`
- `backend/app/schemas/inspections.py`
- 新增 `backend/app/repositories/inspection_analysis.py`

建议新增独立 `inspection_ai_reports` 表，以 `task_id` 唯一关联巡检任务，任务删除时级联删除。存储生成状态、生成批次标识、模型名称/版本快照、成功报告内容、证据覆盖信息、开始/结束时间及受控错误代码，不保存模型密钥。

状态使用 `unavailable / queued / running / completed / failed / interrupted`；无报告记录表示未生成。生成批次与成功报告分开维护，重新生成失败不能让旧报告冒充本轮结果。通过事务认领和批次标识避免重复生成、过期结果覆盖及删除后写回。

迁移仅幂等创建新表，不修改既有主机检查 payload，不批量生成历史报告。启动时将未结束生成标为中断，不自动补跑。沿用已有数据库外键及级联约定。模型资格检查和生成认领在同一事务中完成，受理后固定模型快照；删除任务时取消该任务分析，已发送的数据无法追回，后续批次停止。

## 任务二：输入、分批分析及覆盖校验

涉及文件：

- 新增 `backend/app/services/inspection_analysis.py`
- 新增 `backend/app/services/inspection_analysis_input.py`
- `backend/app/services/ai_provider.py`

步骤：

1. 从结束任务读取完整快照，为每条严重/警告 finding 及日志来源、已保存结果中的序号分配稳定证据 ID，保留主机和检查关联。现有采集未保存服务器文件的原始行号，不把结果序号标为文件行号。检查结论有异常但无 finding 时也加入分析输入。
2. 收集所有已保存的错误日志行、来源状态、匹配数、资源指标和服务状态，并记录失败、跳过、中断的检查及主机。正常主机只需保存覆盖摘要，避免无关数据挤占上下文。
3. 按实际序列化请求大小分批；所有记录进入批次，不静默截断。单批过大进一步按日志行划分。模型上下文限制仍明确报错。
4. 在 provider 增加经过校验的输出 token 参数，普通聊天保持既有参数，报告使用显式限额。保持正常结束验证，长度终止不能算成功。
5. 对每批要求结构化输出，服务端校验证据引用范围和必需发现的覆盖。日志内容只作为不可信数据，禁用工具；拒绝日志中的指令及模型请求执行动作。
6. 汇总所有批次结果；总输入仍超限时分层汇总。最终报告保留每条严重/警告的关联和日志分析明细，不能仅凭模型声明认定全量覆盖。所有批次成功且验证通过才保存新报告。
7. 通过 Vue 文本插值和结构化区域渲染，不使用不可信 HTML。分析输入不会包含 SSH 凭据；日志原文会发送到已配置模型的服务端，此数据流应在功能说明中明确。

## 任务三：生成触发、生命周期与接口

涉及文件：

- `backend/app/services/inspection_tasks.py`
- `backend/app/main.py`
- `backend/app/api/v1/endpoints/inspections.py`
- `backend/app/schemas/inspections.py`

增加受限的报告后台执行器，模型网络请求不占用巡检线程；沿用本项目单实例运行方式，不新增队列软件。任务整体终态后提交生成，事务认领保证多个主机并发收尾仅触发一次。AI 失败不改写巡检任务的成功/失败状态。关闭时停止新生成并取消未执行项，将未完成生成明确标为中断。

接口契约：

- `GET /tasks/{task_id}/analysis`：读取报告及生成状态；任务不存在返回 404，尚未生成返回明确的未生成响应，不伪装成空成功报告。
- `POST /tasks/{task_id}/analysis`：对结束任务生成或重新生成，成功认领返回 202；巡检未结束或正在生成返回 409；模型不可用拒绝生成；队列不可用返回 503。
- 保留原有 `GET /tasks/{task_id}/report` 作为原始巡检 Markdown 导出，AI 汇报另提供结构化显示和内容下载。

队列满或模型不可用要保存实际生成状态，不隐式重试。内部错误仅保存受控错误代码；请求错误在前端统一使用 `showSystemError()`，不展示后端异常原文。

## 任务四：记录页报告与详情页

已实施文件：

- 新增 `frontend/src/components/InspectionRecordSummary.vue`：输入 `TaskDetail`，展示全任务发现数量及详情跳转；依赖既有状态映射、Element Plus 与 router，可复用于任务记录概览。
- 新增 `frontend/src/views/InspectionRecordDetailView.vue`：输入路由任务 ID，调用现有 API 加载并轮询，输出服务器选择及检查详情；依赖已有 `InspectionTaskDetail`，属于独立页面。
- 修改 `frontend/src/components/InspectionTaskList.vue` 和 `frontend/src/router/index.ts`。

AI 接入实施文件：

- `frontend/src/api/inspections.ts`
- `frontend/src/types/inspections.ts`
- 新增 `frontend/src/components/InspectionAnalysisReport.vue`
- `frontend/src/components/InspectionRecordSummary.vue`
- `frontend/src/styles/inspections.css`

报告组件输入任务 ID 和执行状态，通过 API 层读写报告，输出中文分区汇报、生成状态及生成按钮。加载、生成、失败状态独立维护；仅活跃生成轮询，路由切换或卸载后停止，失效请求不弹错误或更新页面。沿用现有主题与桌面布局，不新增 Store、样式系统或渲染依赖。

## 任务五：验证与文档

- 更新 `docs/inspections.md`、`FILE_INDEX.md`，不修改规则文件。
- 在已有 `backend/tests/test_inspection_tasks.py` 增加有意义的报告测试：32 主机输入覆盖、所有严重/警告及日志进入批次、跨批证据对应、模型不可用、模型响应/超限/超时失败、并发认领、任务删除竞争、历史迁移幂等、重启中断。
- 模型调用使用模拟 provider 验证正常和异常流程，不以模拟测试宣称真实模型效果已验证。
- 运行 `python -m pytest backend/tests/test_inspection_checks.py backend/tests/test_inspection_tasks.py`，并按 provider 修改范围运行现有 AI 测试。
- 在 `frontend` 运行 `npm run build`（含 `vue-tsc --noEmit`）。项目无 Lint 脚本，不宣称已通过 Lint。
- 具备浏览器条件时用 1440px 桌面窗口检查记录选择、详情跳转、直接访问、刷新、返回、服务器切换、长日志、加载失败与 AI 状态；真实模型和真实服务器流程另记录是否实际执行。

## 确认范围

用户已明确同意推荐方案：新增报告表与幂等迁移、任务完成后用主模型自动生成、历史任务手动生成、全量分批分析及持久化展示。无自动备用模型切换、无自动重试。上述数据库结构和后台生成生命周期已按确认范围实施。
