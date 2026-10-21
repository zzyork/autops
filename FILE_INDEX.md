# 仓库文件索引

本文件记录目录和文件的用途，路径均相对于仓库根目录。

覆盖已跟踪及未被忽略的项目文件，不收录环境、依赖、缓存和构建产物。

原项目位置：`E:\Codes\autodeploykit`。迁移已有功能时，从该目录定位并阅读原实现。

## 目录用途

| 路径 | 用途 |
| --- | --- |
| `./` | 项目根目录。 |
| `.vscode/` | VS Code 调试与启动配置。 |
| `.agents/skills/` | 项目适配技能与技术参考。 |
| `.opencode/commands/` | OpenCode 项目命令入口。 |
| `.opencode/agents/` | OpenCode 项目审核 Agent。 |
| `scripts/` | 项目安装与启动脚本。 |
| `backend/` | FastAPI 后端项目。 |
| `backend/app/` | 后端应用包。 |
| `backend/app/api/` | HTTP 接口与共用依赖。 |
| `backend/app/api/v1/` | 第一版 API 路由。 |
| `backend/app/api/v1/endpoints/` | 按功能组织的接口端点。 |
| `backend/app/core/` | 应用配置与公共基础设施。 |
| `backend/app/core/migrations/` | 数据库结构迁移。 |
| `backend/app/repositories/` | 业务数据查询与持久化。 |
| `backend/app/services/` | 业务服务与任务执行。 |
| `backend/app/services/inspection_checks/` | 主机巡检采集与结果校验。 |
| `backend/app/schemas/` | 接口数据模型。 |
| `docs/` | 项目说明与开发规范。 |
| `docs/templates/` | 工程文档模板。 |
| `profiles/` | 技术栈与界面专项规范。 |
| `frontend/` | Vue、TypeScript、Vite 前端项目。 |
| `docs/plans/` | 执行中的功能设计与实施方案。 |
| `frontend/src/` | 前端应用源码。 |
| `frontend/src/api/` | HTTP 请求封装及 API 调用。 |
| `frontend/src/components/` | 可复用 UI 组件。 |
| `frontend/src/router/` | 前端路由配置。 |
| `frontend/src/styles/` | 全局样式。 |
| `frontend/src/types/` | 前端 API 类型定义。 |
| `frontend/src/views/` | 页面视图。 |

## 根目录文件

| 路径 | 用途 |
| --- | --- |
| `.gitignore` | Git 文件忽略配置。 |
| `.gitattributes` | Git 文件属性与换行符配置。 |
| `AGENTS.md` | 项目 AI 智能体工作约定。 |
| `FILE_INDEX.md` | 仓库目录与文件用途索引。 |
| `项目配置.md` | 项目技术基线、配置选择与接入记录。 |
| `SECURITY.md` | 安全披露与敏感信息处理约定。 |
| `opencode.json` | OpenCode 项目配置。 |
| `main.py` | 兼容根目录 `uvicorn main:app` 启动方式的入口。 |
| `pyproject.toml` | 配置 pytest 测试目录和 Python 导入路径。 |
| `requirements.txt` | 根目录运行依赖入口，引用后端运行依赖清单。 |
| `requirements-dev.txt` | 根目录开发依赖入口，引用后端开发依赖清单。 |

## VS Code 配置

| 路径 | 用途 |
| --- | --- |
| `.vscode/launch.json` | VS Code 前后端调试与联合启动配置。 |

## 脚本文件

| 路径 | 用途 |
| --- | --- |
| `scripts/start.bat` | Windows 环境准备与项目启动脚本。 |
| `scripts/start.sh` | Linux/macOS 环境准备与项目启动脚本。 |
| `scripts/run_dev.py` | 前后端开发服务的统一启动与进程管理。 |

## 文档文件

| 路径 | 用途 |
| --- | --- |
| `docs/AI-奥卡姆剃刀开发规范.md` | 简约设计与必要复杂度约束。 |
| `docs/AI-前端开发约束规范.md` | 通用前端开发与交互约束。 |
| `docs/AI-后端开发约束规范.md` | 通用后端开发与资源管理约束。 |
| `docs/AI-工程治理与需求规范.md` | 需求、工程决策与文档治理约束。 |
| `docs/AI-接口与安全规范.md` | 接口契约与安全约束。 |
| `docs/AI-测试与交付规范.md` | 验证、审核与交付约束。 |
| `docs/AI-规范合并说明.md` | 规范包接入与合并记录。 |
| `docs/AI-编程接入指南.md` | AI 编程客户端与技能接入指南。 |
| `docs/AI-项目初始化清单.md` | 项目接入前的核查清单。 |
| `docs/AI-接入流程.md` | 开发规范包接入流程。 |
| `docs/AI-编程工程实践参考.md` | AI 编程工程实践与来源参考。 |
| `docs/templates/需求说明模板.md` | 需求说明模板。 |
| `docs/templates/开发任务模板.md` | 开发任务模板。 |
| `docs/templates/架构决策记录模板.md` | 架构决策记录模板。 |
| `docs/templates/缺陷报告模板.md` | 缺陷报告模板。 |
| `docs/templates/合并请求模板.md` | 合并请求说明模板。 |
| `docs/前端样式推荐表.md` | 前端组件样式候选参考。 |

## 技术栈与界面专项

专项启用范围见 `项目配置.md`。

| 路径 | 用途 |
| --- | --- |
| `profiles/Vue3前端技术栈规范.md` | Vue、TypeScript、Vite 与 Element Plus 专项规范。 |
| `profiles/FastAPI技术栈规范.md` | FastAPI 技术栈专项规范。 |
| `profiles/UI规范样板.md` | 本项目界面样式、交互与组件组合规范。 |

## AI 编程技能与入口

技能来源与适用范围见 `项目配置.md`，加载与审核要求见 `docs/AI-编程接入指南.md`。

| 路径 | 用途 |
| --- | --- |
| `.agents/skills/autops-frontend/SKILL.md` | 项目前端实施与验证流程。 |
| `.agents/skills/autops-backend/SKILL.md` | 项目后端实施与验证流程。 |
| `.agents/skills/autops-review/SKILL.md` | 变更、接口、安全与验证审核流程。 |
| `.agents/skills/vue/SKILL.md` | 固定版本的上游 Vue 技能入口。 |
| `.agents/skills/vue/GENERATION.md` | 上游 Vue 文档生成来源记录。 |
| `.agents/skills/vue/LICENSE.md` | 上游 MIT 许可。 |
| `.agents/skills/vue/references/script-setup-macros.md` | Vue 组件宏与类型参考。 |
| `.agents/skills/vue/references/core-new-apis.md` | Vue 响应式与生命周期参考。 |
| `.agents/skills/vue/references/advanced-patterns.md` | Vue 内置组件、指令与进阶模式参考。 |
| `.agents/skills/fastapi/SKILL.md` | 固定版本的 FastAPI 官方技能入口。 |
| `.agents/skills/fastapi/LICENSE` | 上游 MIT 许可。 |
| `.agents/skills/fastapi/references/dependencies.md` | 依赖注入、生命周期和资源清理参考。 |
| `.agents/skills/fastapi/references/other-tools.md` | FastAPI 相关工具与库参考。 |
| `.agents/skills/fastapi/references/path-operations.md` | 路由与 HTTP 输入输出参考。 |
| `.agents/skills/fastapi/references/pydantic.md` | Pydantic 输入校验与类型参考。 |
| `.agents/skills/fastapi/references/responses.md` | 响应模型与输出过滤参考。 |
| `.agents/skills/fastapi/references/streaming.md` | SSE、JSON Lines 和字节流参考。 |
| `.opencode/commands/autops-plan.md` | `/autops-plan` 规划入口。 |
| `.opencode/commands/autops-review.md` | `/autops-review` 只读审核入口。 |
| `.opencode/agents/autops-auditor.md` | 项目只读审核 Agent。 |

## 后端文件

| 路径 | 用途 |
| --- | --- |
| `backend/.env.example` | 后端环境变量模板。 |
| `backend/__init__.py` | 声明后端 Python 包。 |
| `backend/requirements.txt` | 后端运行依赖清单。 |
| `backend/requirements-dev.txt` | 后端开发与测试依赖清单。 |
| `backend/app/__init__.py` | 声明后端应用包。 |
| `backend/app/main.py` | FastAPI 应用入口与任务执行器生命周期管理。 |
| `backend/app/connection_models.py` | SSH 服务器信任与身份挑战数据库模型。 |
| `backend/app/inspection_models.py` | 巡检任务、执行结果与 AI 报告数据库模型。 |
| `backend/app/models.py` | 主机、分组、跳板机与 SSH 密钥数据库模型。 |
| `backend/app/ai_models.py` | AI 模型连接、会话与巡检计划数据库模型。 |
| `backend/app/core/migrations/ai.py` | AI 业务数据库结构迁移。 |
| `backend/app/schemas/ai.py` | AI 配置、会话与操作接口数据模型。 |
| `backend/app/repositories/ai.py` | AI 配置、会话与巡检计划持久化。 |
| `backend/app/services/ai_provider.py` | OpenAI 兼容与 Anthropic 模型调用协议适配。 |
| `backend/app/services/ai_chat.py` | AI 对话与运维工具调用编排。 |
| `backend/app/services/ai_feature_models.py` | AI 对话与巡检汇报的模型配置管理。 |
| `backend/app/api/v1/endpoints/ai.py` | AI 模型配置、会话与操作管理接口。 |
| `backend/app/api/__init__.py` | 声明 HTTP 接口包。 |
| `backend/app/api/dependencies.py` | 接口共用数据库依赖与查询辅助。 |
| `backend/app/api/v1/__init__.py` | 声明第一版 API 包。 |
| `backend/app/api/v1/router.py` | v1 API 路由汇总。 |
| `backend/app/api/v1/endpoints/ssh_connections.py` | SSH 连接测试接口。 |
| `backend/app/api/v1/endpoints/inspections.py` | 巡检规则、任务与报告管理接口。 |
| `backend/app/api/v1/endpoints/__init__.py` | 声明接口端点包。 |
| `backend/app/api/v1/endpoints/health.py` | 提供 v1 健康检查接口。 |
| `backend/app/api/v1/endpoints/hosts.py` | 主机管理接口。 |
| `backend/app/api/v1/endpoints/jump_hosts.py` | 独立跳板机管理接口。 |
| `backend/app/api/v1/endpoints/credentials.py` | 主机与跳板机共用凭据处理。 |
| `backend/app/api/v1/endpoints/ssh_keys.py` | 独立 SSH 密钥管理与引用查询接口。 |
| `backend/app/api/v1/endpoints/host_groups.py` | 主机分组管理接口。 |
| `backend/app/core/__init__.py` | 声明配置及公共基础设施包。 |
| `backend/app/core/config.py` | 后端应用配置。 |
| `backend/app/core/storage.py` | 数据库初始化、迁移与凭据加密密钥管理。 |
| `backend/app/core/ssh.py` | SSH 连接、认证与服务器公钥探测。 |
| `backend/app/core/ssh_commands.py` | SSH 单命令执行与输出采集。 |
| `backend/app/core/ssh_workflows.py` | SSH 多步骤命令流程编排。 |
| `backend/app/core/ssh_network.py` | SSH 网络解析与连接。 |
| `backend/app/core/migrations/__init__.py` | 声明数据库迁移包。 |
| `backend/app/core/migrations/ssh_connections.py` | SSH 连接与身份信任数据库结构迁移。 |
| `backend/app/core/migrations/inspections.py` | 巡检业务数据库结构迁移。 |
| `backend/app/core/migrations/retired_features.py` | 已退役业务数据库表清理。 |
| `backend/app/repositories/__init__.py` | 声明仓储包。 |
| `backend/app/repositories/assets.py` | 资产筛选与分页查询。 |
| `backend/app/repositories/pagination.py` | 共用数据库分页查询。 |
| `backend/app/repositories/ssh_connections.py` | SSH 连接资产与信任查询及连接状态持久化。 |
| `backend/app/repositories/inspections.py` | 巡检任务与执行记录持久化。 |
| `backend/app/services/__init__.py` | 声明业务服务包。 |
| `backend/app/services/ssh_assets.py` | SSH 资产连接配置与凭据解析。 |
| `backend/app/services/ssh_connections.py` | SSH 连接测试与状态更新。 |
| `backend/app/services/host_basic_info.py` | 主机基础信息采集与连接快照复核。 |
| `backend/app/services/inspection_tasks.py` | 后台主机巡检任务执行与取消管理。 |
| `backend/app/services/inspection_rules.py` | 巡检规则配置读取与保存。 |
| `backend/app/services/inspection_reports.py` | 巡检 Markdown 报告生成与归档导出。 |
| `backend/app/schemas/inspection_analysis.py` | 巡检 AI 分析报告与证据数据模型。 |
| `backend/app/repositories/inspection_analysis.py` | 巡检 AI 报告与生成状态持久化。 |
| `backend/app/services/inspection_analysis.py` | 巡检 AI 报告生成任务管理。 |
| `backend/app/services/inspection_analysis_input.py` | 巡检风险与日志证据提取。 |
| `backend/app/services/inspection_analysis_groups.py` | 巡检日志模板分组与证据映射。 |
| `backend/app/services/inspection_log_display.py` | 巡检详情日志的分组展示适配。 |
| `backend/app/services/inspection_analysis_engine.py` | 巡检 AI 诊断与报告结果校验。 |
| `backend/app/services/inspection_checks/__init__.py` | 巡检检查项注册、分发与共用校验。 |
| `backend/app/services/inspection_checks/basic.py` | 主机基础信息采集与解析。 |
| `backend/app/services/inspection_checks/resources.py` | 主机资源指标采集与阈值判定。 |
| `backend/app/services/inspection_checks/services.py` | systemd 服务状态采集与判定。 |
| `backend/app/services/inspection_checks/network.py` | 主机网络地址与监听信息采集。 |
| `backend/app/services/inspection_checks/logs.py` | 主机错误日志采集与过滤。 |
| `backend/app/services/inspection_checks/log_window.py` | 巡检日志时间窗口过滤。 |
| `backend/app/core/ssh_keys.py` | SSH 密钥校验与指纹生成。 |
| `backend/app/schemas/__init__.py` | 声明接口数据模型包。 |
| `backend/app/schemas/pagination.py` | 共用分页参数与响应数据模型。 |
| `backend/app/schemas/health.py` | 定义健康检查响应模型。 |
| `backend/app/schemas/assets.py` | 资产管理接口数据模型。 |
| `backend/app/schemas/host_basic_info.py` | 主机基础信息采集与定向更新接口数据模型。 |
| `backend/app/schemas/jump_hosts.py` | 跳板机接口数据模型。 |
| `backend/app/schemas/ssh_keys.py` | SSH 密钥与引用接口数据模型。 |
| `backend/app/schemas/ssh_connections.py` | SSH 连接测试请求与响应数据模型。 |
| `backend/app/schemas/inspections.py` | 巡检规则、任务与结果接口数据模型。 |

## 前端文件

| 路径 | 用途 |
| --- | --- |
| `frontend/.env.example` | 前端环境变量模板。 |
| `frontend/index.html` | 前端 HTML 入口。 |
| `frontend/package.json` | 前端依赖与运行脚本配置。 |
| `frontend/package-lock.json` | npm 依赖版本锁定文件。 |
| `frontend/tsconfig.json` | TypeScript 编译与类型检查配置。 |
| `frontend/vite.config.ts` | Vite 开发与构建配置。 |
| `frontend/src/App.vue` | 应用根组件与工作区装配。 |
| `frontend/src/api/health.ts` | 健康检查接口调用。 |
| `frontend/src/api/http.ts` | 共用 HTTP 请求、下载与 SSE 客户端。 |
| `frontend/src/api/assets.ts` | 资产管理接口调用。 |
| `frontend/src/api/host_basic_info.ts` | 主机基础信息采集与保存接口调用。 |
| `frontend/src/api/jump_hosts.ts` | 跳板机管理接口调用。 |
| `frontend/src/api/ssh_keys.ts` | SSH 密钥管理接口调用。 |
| `frontend/src/api/ssh_connections.ts` | SSH 连接测试接口调用。 |
| `frontend/src/api/inspections.ts` | 巡检规则、任务与报告接口调用。 |
| `frontend/src/api/ai.ts` | AI 配置、会话与操作接口调用。 |
| `frontend/src/types/ai.ts` | AI 模型、会话与操作类型定义。 |
| `frontend/src/components/ChatProposalCard.vue` | AI 巡检计划展示与确认卡片。 |
| `frontend/src/components/ChatTaskCard.vue` | 对话关联巡检任务的状态与报告入口卡片。 |
| `frontend/src/components/DisclosurePanel.vue` | 共用可展开详情面板。 |
| `frontend/src/components/ModelConnectionDialog.vue` | 模型连接新增与编辑弹窗。 |
| `frontend/src/components/FeatureModelsForm.vue` | AI 对话与巡检汇报模型配置表单。 |
| `frontend/src/views/ChatView.vue` | AI 会话管理与流式对话页面。 |
| `frontend/src/views/ModelConnectionsView.vue` | 模型连接管理与能力测试页面。 |
| `frontend/src/styles/ai.css` | AI 对话与模型配置样式。 |
| `frontend/src/components/sshConnectionTest.ts` | 单台 SSH 连接测试流程与行内状态管理。 |
| `frontend/src/components/BatchSSHConnectionDialog.vue` | 批量 SSH 连接测试弹窗。 |
| `frontend/src/components/HostSSHStatus.vue` | 主机 SSH 连接状态展示。 |
| `frontend/src/components/HostForm.vue` | 主机连接信息、基本信息与备注表单展示。 |
| `frontend/src/components/HostBasicInfoDialog.vue` | 主机基础信息采集预览、地址选择与保存弹窗。 |
| `frontend/src/components/hostDisplay.ts` | 主机名称与连接地址的显示标识。 |
| `frontend/src/components/TestStatus.vue` | 共用测试状态图标、可选图文标签及状态说明。 |
| `frontend/src/components/sshTestDisplay.ts` | SSH 测试状态与提示文案映射。 |
| `frontend/src/types/testStatus.ts` | 共用测试展示状态类型。 |
| `frontend/src/types/executionStatus.ts` | 五类执行状态的前端展示键类型。 |
| `frontend/src/components/ChatMessageItem.vue` | 对话消息及已确认结果与待确认状态的纯展示组件。 |
| `frontend/src/components/ChatMarkdownContent.vue` | AI 回复的安全 Markdown 渲染与表格展示。 |
| `frontend/src/components/InspectionConfigForm.vue` | 巡检规则配置表单。 |
| `frontend/src/components/InspectionCreateDialog.vue` | 巡检任务创建弹窗。 |
| `frontend/src/components/InspectionTaskDetail.vue` | 主机巡检详情、检查结果与报告导出展示。 |
| `frontend/src/components/inspectionDisplay.ts` | 巡检状态、结论与结果展示映射。 |
| `frontend/src/components/timeDisplay.ts` | 共用日期时间展示工具。 |
| `frontend/src/components/ServiceStatus.vue` | 后端连接状态展示组件。 |
| `frontend/src/components/feedback.ts` | 共用请求错误与导航阻断消息反馈。 |
| `frontend/src/components/FieldError.vue` | 共用表单字段错误提示。 |
| `frontend/src/components/formFeedback.ts` | 共用表单错误定位与可访问性辅助。 |
| `frontend/src/components/ListPagination.vue` | 共用列表分页控件。 |
| `frontend/src/components/pagination.ts` | 共用分页配置与本地数组分页。 |
| `frontend/src/components/serverPagination.ts` | 共用服务端分页请求与状态管理。 |
| `frontend/src/components/ConsoleLayout.vue` | 控制台共用顶栏、侧栏与内容布局。 |
| `frontend/src/components/WorkspaceTabs.vue` | 工作区标签栏与页面面板。 |
| `frontend/src/components/WorkspacePage.vue` | 工作区页面路由与可见状态容器。 |
| `frontend/src/components/workspace.ts` | 工作区标签、导航与页面状态管理。 |
| `frontend/src/env.d.ts` | 补充 Vite 环境变量的 TypeScript 类型声明。 |
| `frontend/src/main.ts` | Vue 应用启动入口。 |
| `frontend/src/router/index.ts` | 前端页面路由配置。 |
| `frontend/src/styles/main.css` | 全局样式变量与 Element Plus 样式覆盖。 |
| `frontend/src/styles/console.css` | 控制台布局与工作区样式。 |
| `frontend/src/styles/ui.css` | 业务共用界面组件样式。 |
| `frontend/src/styles/assets.css` | 资产管理业务样式。 |
| `frontend/src/styles/inspections.css` | 巡检配置、详情与分析报告样式。 |
| `frontend/src/types/api.ts` | 资产与 SSH 连接测试接口类型定义。 |
| `frontend/src/types/hostBasicInfo.ts` | 主机基础信息采集与保存接口类型定义。 |
| `frontend/src/types/inspections.ts` | 巡检配置、任务、结果与报告类型定义。 |
| `frontend/src/views/HostsView.vue` | 主机管理与 SSH 连接测试页面。 |
| `frontend/src/views/HostGroupsView.vue` | 主机分组管理页面。 |
| `frontend/src/views/JumpHostsView.vue` | 跳板机管理与 SSH 连接测试页面。 |
| `frontend/src/views/SSHKeysView.vue` | SSH 密钥管理页面。 |
| `frontend/src/views/InspectionsView.vue` | 巡检任务创建与进度页面。 |
| `frontend/src/views/InspectionRecordsView.vue` | 巡检历史记录与报告概览页面。 |
| `frontend/src/views/InspectionRecordDetailView.vue` | 服务器巡检记录详情页面。 |
| `frontend/src/components/InspectionRecordSummary.vue` | 巡检记录概览与风险统计。 |
| `frontend/src/components/InspectionAnalysisReport.vue` | 巡检 AI 分析报告生成、展示与导出。 |
| `frontend/src/components/InspectionAnalysisEvidence.vue` | 巡检分析证据筛选与展示。 |
| `frontend/src/components/InspectionAnalysisIssue.vue` | 巡检分析问题与建议展示。 |
| `frontend/src/components/inspectionAnalysisDisplay.ts` | 巡检分析报告与日志证据展示转换。 |
| `frontend/src/views/InspectionRulesView.vue` | 巡检规则管理页面。 |
| `frontend/src/components/InspectionTaskList.vue` | 巡检任务与历史记录共用列表。 |

## 独立 SSH 身份确认

| 路径 | 用途 |
| --- | --- |
| `backend/app/api/v1/endpoints/ssh_identities.py` | SSH 服务器身份检查与信任确认接口。 |
| `backend/app/schemas/ssh_identities.py` | SSH 服务器身份检查与确认数据模型。 |
| `backend/app/services/ssh_identities.py` | SSH 服务器身份探测与信任管理。 |
| `frontend/src/types/sshIdentity.ts` | SSH 服务器身份检查与确认类型定义。 |
| `frontend/src/api/ssh_identities.ts` | SSH 服务器身份接口调用与响应校验。 |
| `frontend/src/api/sshIdentity.ts` | SSH 身份检查与确认流程协调。 |
| `frontend/src/components/SSHIdentityDialog.vue` | 共用 SSH 服务器身份确认弹窗。 |
