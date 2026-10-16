# 仓库文件索引

本文件记录目录和文件的用途，路径均相对于仓库根目录。

覆盖已跟踪及未被忽略的项目文件，不收录环境、依赖、缓存和构建产物。

原项目位置：`E:\Codes\autodeploykit`。迁移已有功能时，从该目录定位并阅读原实现。

索引维护日期：2026-10-12。条目未单独标注最后同步日期时，以此日期作为初始核对日期；后续修改文件时在用途说明末尾标注最后同步日期。

## 目录用途

| 路径 | 用途 |
| --- | --- |
| `./` | 项目根目录。 |
| `.vscode/` | VS Code 前后端调试与联合启动配置。最后同步：2026-10-13。 |
| `.agents/skills/` | OpenCode 与 Codex 共享的项目适配技能及固定上游技术知识快照。最后同步：2026-10-15。 |
| `.opencode/commands/` | OpenCode 项目规划与只读审核命令入口。最后同步：2026-10-15。 |
| `.opencode/agents/` | OpenCode 项目专用只读审核 Agent。最后同步：2026-10-15。 |
| `scripts/` | 统一存放项目安装与启动脚本。最后同步：2026-10-13。 |
| `backend/` | FastAPI 后端项目。 |
| `backend/app/` | 后端应用包。 |
| `backend/app/api/` | HTTP 接口代码与共用数据库依赖。最后同步：2026-10-10。 |
| `backend/app/api/v1/` | 第一版 API 路由。 |
| `backend/app/api/v1/endpoints/` | 按功能组织的接口端点。 |
| `backend/app/core/` | 应用配置与公共基础设施。 |
| `backend/app/core/migrations/` | SSH 连接与巡检表的可重复启动迁移。最后同步：2026-10-12。 |
| `backend/app/repositories/` | SSH 资产、连接测试、巡检及 AI 配置、会话记录持久化。最后同步：2026-10-12。 |
| `backend/app/services/` | SSH 资产解析、连接与巡检执行，以及模型协议、能力测试和 AI 对话编排。最后同步：2026-10-12。 |
| `backend/app/services/inspection_checks/` | 四类巡检采集器、结果校验与分发。最后同步：2026-10-12。 |
| `backend/app/schemas/` | 接口数据模型。 |
| `backend/tests/` | 已跟踪的主机与分组接口测试及显式放行的巡检检查、任务测试；其他新测试默认被根目录忽略规则排除。最后同步：2026-10-12。 |
| `docs/` | 项目文档及 AI 前端、后端开发约束。最后同步：2026-10-12。 |
| `frontend/` | Vue、TypeScript、Vite 前端项目。 |
| `docs/plans/` | 已授权功能设计、接口契约和实施计划。最后同步：2026-10-12。 |
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
| `.gitignore` | Git 文件忽略配置，忽略运行数据及默认忽略新增的 `backend/tests/*`，例外见 `backend/.gitignore`。最后同步：2026-10-12。 |
| `.gitattributes` | 固定 Windows 启动脚本使用 CRLF、Shell 启动脚本使用 LF，避免跨平台检出造成解析错误。最后同步：2026-10-13。 |
| `AGENTS.md` | 项目 Agent 工作约定，强制执行三份开发规范、技能加载及外部知识边界，包含 README、授权与验证要求。最后同步：2026-10-15。 |
| `FILE_INDEX.md` | 仓库目录与文件用途索引。 |
| `README.md` | 项目介绍与安装、运行、模型对话、巡检及六类服务器运维使用入口和目标系统范围。最后同步：2026-10-14。 |
| `main.py` | 兼容根目录 `uvicorn main:app` 启动方式的入口。 |
| `pyproject.toml` | 配置 pytest 测试目录和 Python 导入路径。 |
| `requirements.txt` | 根目录运行依赖入口，引用后端运行依赖清单。 |
| `requirements-dev.txt` | 根目录开发依赖入口，引用后端开发依赖清单。 |

## VS Code 配置

| 路径 | 用途 |
| --- | --- |
| `.vscode/launch.json` | VS Code F5 在单个终端启动 FastAPI 与 Vite 并合并日志，复用已有依赖，前后端均就绪时打开浏览器，保留分别调试入口。最后同步：2026-10-13。 |

## 脚本文件

| 路径 | 用途 |
| --- | --- |
| `scripts/start.bat` | Windows 启动脚本，创建或复用根目录虚拟环境、补齐依赖，调用统一入口在当前终端运行前后端。最后同步：2026-10-13。 |
| `scripts/start.sh` | Linux/macOS Bash 启动脚本，创建或复用根目录虚拟环境、补齐依赖，调用统一入口在当前终端运行前后端。最后同步：2026-10-13。 |
| `scripts/run_dev.py` | F5 与平台脚本共用的启动入口，合并带来源前缀的日志，确认两个服务启动日志及 HTTP 响应后输出就绪标记，并在终止信号或服务退出时清理服务进程树。最后同步：2026-10-13。 |

## 文档文件

| 路径 | 用途 |
| --- | --- |
| `docs/AI-奥卡姆剃刀开发规范.md` | 基于出版论文及工程指南的跨端简约设计约束，定义必要复杂度、合理冗余、拆分合并、Agent 决策流程、审核清单及文献适用边界。最后同步：2026-10-15。 |
| `docs/AI-前端开发约束规范.md` | AI 前端开发约束及项目 UI 实施标准，包含统一测试状态图标与 tooltip 复用要求。最后同步：2026-10-13。 |
| `docs/AI-后端开发约束规范.md` | AI 后端架构、接口、数据库、安全及验证约束。最后同步：2026-10-12。 |
| `docs/AI-编程接入指南.md` | 项目技能路由、固定来源与许可、审核记录、已知差异、使用和更新验收说明。最后同步：2026-10-15。 |
| `docs/plans/2026-10-15-ai-coding-integration.md` | AI 编程规则与技能接入的方案取舍、实施步骤、风险和验收计划。最后同步：2026-10-15。 |
| `docs/plans/2026-10-14-activity-audit-implementation.md` | 依据现行前后端规范优化的操作记录实施方案，包含最小响应与展示契约、事务迁移、模块接入、用户兼容、分阶段验收及规范检查表；尚未实施业务代码。最后同步：2026-10-14。 |

## AI 编程技能与入口

以下条目最后同步：2026-10-15。上游技能快照的来源提交和许可见 `docs/AI-编程接入指南.md`。

| 路径 | 用途 |
| --- | --- |
| `.agents/skills/autops-frontend/SKILL.md` | 前端实施与验证流程，连接项目规范、源码和 Vue 技能。 |
| `.agents/skills/autops-backend/SKILL.md` | 后端实施与验证流程，连接项目规范、源码和 FastAPI 技能。 |
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
| `.agents/skills/fastapi/references/other-tools.md` | 上游工具与库偏好，仅按接入指南选择性参考。 |
| `.agents/skills/fastapi/references/path-operations.md` | 路由与 HTTP 输入输出参考。 |
| `.agents/skills/fastapi/references/pydantic.md` | Pydantic 输入校验与类型参考。 |
| `.agents/skills/fastapi/references/responses.md` | 响应模型与输出过滤参考。 |
| `.agents/skills/fastapi/references/streaming.md` | SSE、JSON Lines 和字节流参考。 |
| `.opencode/commands/autops-plan.md` | `/autops-plan` 规划入口。 |
| `.opencode/commands/autops-review.md` | `/autops-review` 只读审核入口。 |
| `.opencode/agents/autops-auditor.md` | 拒绝编辑、Shell 与任务委派的只读审核 Agent。 |

## 后端文件

| 路径 | 用途 |
| --- | --- |
| `backend/.env.example` | 后端环境变量模板。最后同步：2026-10-10。 |
| `backend/.gitignore` | 从根目录测试忽略规则中放行巡检检查、任务及列表分页正式回归测试。最后同步：2026-10-14。 |
| `backend/__init__.py` | 声明后端 Python 包。 |
| `backend/requirements.txt` | 后端运行依赖清单，包含 Paramiko SSH 连接与 Drain3 日志模板提取依赖。最后同步：2026-10-13。 |
| `backend/requirements-dev.txt` | 后端开发与测试依赖清单。 |
| `backend/app/__init__.py` | 声明后端应用包。 |
| `backend/app/main.py` | FastAPI 入口及连接测试、巡检、AI 对话、巡检报告和运维执行器生命周期管理。最后同步：2026-10-14。 |
| `backend/app/connection_models.py` | 服务器公钥信任与独立一次性身份挑战数据库模型。最后同步：2026-10-15。 |
| `backend/app/inspection_models.py` | 巡检任务、主机执行、检查结果及独立 AI 报告数据库模型。最后同步：2026-10-13。 |
| `backend/app/models.py` | 主机、分组、跳板机与 SSH 密钥数据库模型。最后同步：2026-10-10。 |
| `backend/app/ai_models.py` | 模型连接、会话、消息、批次工具历史与待确认巡检计划模型。最后同步：2026-10-12。 |
| `backend/app/core/migrations/ai.py` | AI 表及批次历史、执行中状态的幂等迁移。最后同步：2026-10-12。 |
| `backend/app/schemas/ai.py` | 模型配置、会话消息、计划与决策接口校验。最后同步：2026-10-12。 |
| `backend/app/repositories/ai.py` | 模型连接、会话、消息、工具历史、计划持久化与中断标记。最后同步：2026-10-12。 |
| `backend/app/services/ai_provider.py` | OpenAI 兼容及 Anthropic 流式协议适配、可校验输出限额和正常终止验证。最后同步：2026-10-13。 |
| `backend/app/services/ai_chat.py` | LangGraph 对话编排、能力验证、资产与巡检工具、会话互斥。最后同步：2026-10-12。 |
| `backend/app/services/ai_feature_models.py` | AI 对话与巡检汇报独立模型配置读取、连接校验、原子保存及选模；未指定时沿用主模型。最后同步：2026-10-14。 |
| `backend/app/api/v1/endpoints/ai.py` | 模型连接、会话、SSE 回复及巡检计划确认接口。最后同步：2026-10-12。 |
| `backend/app/api/__init__.py` | 声明 HTTP 接口包。 |
| `backend/app/api/dependencies.py` | 共用数据库会话依赖、事务提交与分组查询。最后同步：2026-10-10。 |
| `backend/app/api/v1/__init__.py` | 声明第一版 API 包。 |
| `backend/app/api/v1/router.py` | v1 API 路由汇总，注册资产、SSH 连接测试、巡检、AI 和服务器运维接口。最后同步：2026-10-14。 |
| `backend/app/api/v1/endpoints/ssh_connections.py` | 同步 SSH 连接测试接口，仅返回本次结果，不提供历史查询。最后同步：2026-10-15。 |
| `backend/app/api/v1/endpoints/inspections.py` | 巡检规则、任务创建/历史分页/详情/删除、原始 Markdown 报告、逐主机报告 ZIP 下载及 AI 报告读取/生成接口。最后同步：2026-10-13。 |
| `backend/app/api/v1/endpoints/__init__.py` | 声明接口端点包。 |
| `backend/app/api/v1/endpoints/health.py` | 提供 v1 健康检查接口。 |
| `backend/app/api/v1/endpoints/hosts.py` | 主机管理及跳板机关联接口。最后同步：2026-10-10。 |
| `backend/app/api/v1/endpoints/jump_hosts.py` | 独立跳板机管理接口。 |
| `backend/app/api/v1/endpoints/credentials.py` | 主机与跳板机共用凭据处理。 |
| `backend/app/api/v1/endpoints/ssh_keys.py` | 独立 SSH 密钥管理与引用查询接口。 |
| `backend/app/api/v1/endpoints/host_groups.py` | 分组管理接口及组内主机计数。最后同步：2026-10-10。 |
| `backend/app/core/__init__.py` | 声明配置及公共基础设施包。 |
| `backend/app/core/config.py` | 后端应用配置。最后同步：2026-10-10。 |
| `backend/app/core/storage.py` | 资产数据库、凭据密钥管理及旧配置迁移，调用连接、巡检、AI 和运维表迁移。最后同步：2026-10-14。 |
| `backend/app/core/ssh.py` | SSH 直连、单层跳板、私钥解析、严格身份校验与无目标认证的公钥探测，移除自动信任回调。最后同步：2026-10-14。 |
| `backend/app/core/ssh_commands.py` | 有时限与输出上限的固定巡检 SSH 命令执行、双流读取及通道清理。最后同步：2026-10-12。 |
| `backend/app/core/ssh_network.py` | DNS 与 TCP 建连、整体超时及网络资源清理。最后同步：2026-10-12。 |
| `backend/app/core/migrations/__init__.py` | 声明数据库迁移包。最后同步：2026-10-12。 |
| `backend/app/core/migrations/ssh_connections.py` | 保留信任与身份挑战表，补齐主机连接状态字段、收敛重启状态并删除旧测试历史表。最后同步：2026-10-15。 |
| `backend/app/core/migrations/inspections.py` | 幂等创建巡检任务、主机执行、检查结果和 AI 报告表。最后同步：2026-10-13。 |
| `backend/app/repositories/__init__.py` | 声明仓储包。最后同步：2026-10-12。 |
| `backend/app/repositories/assets.py` | 主机、分组、跳板机与密钥的筛选及数据库分页查询。最后同步：2026-10-14。 |
| `backend/app/repositories/pagination.py` | 共用列表计数与 limit/offset 查询，兼容原数组查询。最后同步：2026-10-14。 |
| `backend/app/repositories/ssh_connections.py` | SSH 资产、密钥、信任查询及不改变资产版本和更新时间的连接状态写入。最后同步：2026-10-15。 |
| `backend/app/repositories/inspections.py` | 巡检任务与执行记录持久化、分页、终态删除、状态汇总和中断恢复。最后同步：2026-10-12。 |
| `backend/app/services/__init__.py` | 声明业务服务包。最后同步：2026-10-12。 |
| `backend/app/services/ssh_assets.py` | SSH 连接配置解析、凭据解密及资产版本快照。最后同步：2026-10-12。 |
| `backend/app/services/ssh_connections.py` | 有界同步严格身份连接测试，将本次状态写入主机字段，并复核配置变更和资产身份。最后同步：2026-10-15。 |
| `backend/app/services/inspection_tasks.py` | 有界后台主机巡检、SSH 会话、逐项执行与失败/关闭处理。最后同步：2026-10-12。 |
| `backend/app/services/inspection_rules.py` | 从数据目录读取巡检规则，并以临时文件和原子替换保存生效配置。最后同步：2026-10-12。 |
| `backend/app/services/inspection_reports.py` | 从巡检详情生成 Markdown 报告并转义动态内容，按原项目 IP_hostname.md 命名和分组/月目录打包逐主机报告；缺少远端 hostname 时使用资产名称。最后同步：2026-10-13。 |
| `backend/app/schemas/inspection_analysis.py` | AI 报告状态、进度、原始日志证据及位置、诊断组与来源观察统计、问题和响应模型，兼容历史报告。最后同步：2026-10-13。 |
| `backend/app/repositories/inspection_analysis.py` | AI 报告事务认领、批次状态更新、成功报告保留及重启中断标记。最后同步：2026-10-13。 |
| `backend/app/services/inspection_analysis.py` | 有界 AI 报告执行器，主模型事务资格检查、配置快照、自动/手动生成、当前生成批次进度与耗时日志和按任务取消。最后同步：2026-10-13。 |
| `backend/app/services/inspection_analysis_input.py` | 提取日志与巡检风险，按主机、来源表及忽略行首时间戳的正文精确合并，保留全部原文、表位置、结果序号、次数与时间。最后同步：2026-10-13。 |
| `backend/app/services/inspection_analysis_groups.py` | 任务内 Drain3 模板提取、显式非诊断标识归一化、精确保护键和来源边界，构建紧凑模型输入与全部证据映射。最后同步：2026-10-13。 |
| `backend/app/services/inspection_analysis_engine.py` | 单次请求由 AI 合并诊断组并分析，校验每个组编号恰好被覆盖一次，关联全部模板与原始证据；非日志问题保留巡检事实。最后同步：2026-10-13。 |
| `backend/app/services/inspection_checks/__init__.py` | 检查目录、结果表限制、公共校验与四类检查分发。最后同步：2026-10-12。 |
| `backend/app/services/inspection_checks/basic.py` | 系统基础信息与 IP 地址解析。最后同步：2026-10-12。 |
| `backend/app/services/inspection_checks/resources.py` | CPU、负载、内存、Swap、磁盘和进程指标采集及阈值判定。最后同步：2026-10-12。 |
| `backend/app/services/inspection_checks/services.py` | systemd 候选服务状态采集、未安装服务结果隐藏与必需服务告警。最后同步：2026-10-12。 |
| `backend/app/services/inspection_checks/network.py` | 网卡地址、本机 TCP/UDP 监听信息采集与回环监听过滤。最后同步：2026-10-12。 |
| `backend/app/services/inspection_checks/logs.py` | journal 与 /var/log 下文件错误日志筛选、权限及真实路径校验，复用巡检结果和报告。最后同步：2026-10-12。 |
| `backend/app/core/ssh_keys.py` | SSH 公私钥内容与配对校验、指纹生成。最后同步：2026-10-10。 |
| `backend/app/schemas/__init__.py` | 声明接口数据模型包。 |
| `backend/app/schemas/pagination.py` | 分页响应泛型、页码上限及 10/20/50/100 数量校验，默认每页 10 条。最后同步：2026-10-15。 |
| `backend/app/schemas/health.py` | 定义健康检查响应模型。 |
| `backend/app/schemas/assets.py` | 资产管理接口数据模型。最后同步：2026-10-10。 |
| `backend/app/schemas/jump_hosts.py` | 跳板机接口数据模型。 |
| `backend/app/schemas/ssh_keys.py` | SSH 密钥与引用接口数据模型。 |
| `backend/app/schemas/ssh_connections.py` | SSH 连接测试输入与最小必要结果响应模型，过滤策略、旧挑战及内部异常。最后同步：2026-10-14。 |
| `backend/app/schemas/inspections.py` | 巡检输入校验、规则配置、结果及任务/报告响应模型；历史响应过滤未安装服务与回环监听。最后同步：2026-10-12。 |
| `backend/tests/test_assets.py` | 使用 TestClient 验证主机、分组的 CRUD、筛选及异常路径。最后同步：2026-10-10。 |
| `backend/tests/test_list_pagination.py` | 六类列表分页、筛选、输入边界、最小响应和旧数组契约回归测试。最后同步：2026-10-14。 |
| `backend/tests/test_ssh_connection_status.py` | 主机连接状态字段、同步测试契约、并发配置变更、身份确认与旧历史表迁移回归测试。最后同步：2026-10-15。 |
| `backend/tests/test_inspection_checks.py` | 使用模拟命令结果验证四类巡检采集、阈值、服务和回环监听过滤。最后同步：2026-10-12。 |
| `backend/tests/test_inspection_tasks.py` | 使用隔离数据库与 TestClient 验证巡检规则、任务/报告接口、终态删除、历史过滤及执行边界。最后同步：2026-10-12。 |

## 服务器运维新增文件

| 路径 | 用途 |
| --- | --- |
| `backend/app/operation_models.py` | 运维计划、主机、步骤及人工核对数据库模型。最后同步：2026-10-14。 |
| `backend/app/core/migrations/operations.py` | 运维表及核对字段的幂等启动迁移。最后同步：2026-10-14。 |
| `backend/app/schemas/operations.py` | 目录、读取、计划、确认、核对及当前任务详情契约。最后同步：2026-10-14。 |
| `backend/app/repositories/operations.py` | 运维计划、确认认领、逐步记录、持久阻塞与重启中断。最后同步：2026-10-14。 |
| `backend/app/services/operations.py` | SSH 预检、权限、计划、确认、主机互斥与有界调度。最后同步：2026-10-14。 |
| `backend/app/services/operation_execution.py` | 资产/状态复核、逐步骤执行与核验、失败和未知结果持久化。最后同步：2026-10-14。 |
| `backend/app/services/operation_commands/` | 六类固定操作目录、严格参数校验及预检/执行/核验脚本；common、hostname、packages、firewall、kernel、system、disk 按职责分文件。最后同步：2026-10-14。 |
| `backend/app/api/v1/endpoints/operations.py` | 运维目录、现状、计划、确认、当前任务详情及人工核对接口。最后同步：2026-10-14。 |
| `frontend/src/types/operations.ts` | 六模块目录、表单、任务状态及核对类型。最后同步：2026-10-14。 |
| `frontend/src/api/operations.ts` | 运维 API 调用及对应时限。最后同步：2026-10-14。 |
| `frontend/src/components/OperationsWorkbench.vue` | 运维页面请求、独立身份确认前置流程、轮询、当前计划与核对。最后同步：2026-10-14。 |
| `frontend/src/components/OperationSetup.vue` | 主机选择、免密 sudo、目录驱动参数表单及本地校验。最后同步：2026-10-14。 |
| `frontend/src/components/OperationTaskDetail.vue` | 计划预览、确认弹窗、逐主机步骤和未知结果人工核对。最后同步：2026-10-14。 |
| `frontend/src/components/operationDisplay.ts` | 运维任务、主机和步骤的状态中文与语义色映射。最后同步：2026-10-14。 |
| `frontend/src/styles/operations.css` | 复用控制台变量的运维表单、详情、输出及任务布局。最后同步：2026-10-14。 |
| `frontend/src/components/HostnameOperationDialog.vue` | 简单主机名编辑弹窗，自动读取当前名称，输入新名称后保存；复用身份校验、运维执行及异常结果核对。最后同步：2026-10-14。 |
| `frontend/src/views/PackagesOperationsView.vue` | 软件包与仓库管理独立页面。最后同步：2026-10-14。 |
| `frontend/src/views/FirewallOperationsView.vue` | 防火墙管理独立页面。最后同步：2026-10-14。 |
| `frontend/src/views/KernelOperationsView.vue` | 内核参数与资源限制独立页面。最后同步：2026-10-14。 |
| `frontend/src/views/SystemOperationsView.vue` | 系统优化独立页面。最后同步：2026-10-14。 |
| `frontend/src/views/DiskOperationsView.vue` | 磁盘管理独立页面。最后同步：2026-10-14。 |

## 前端文件

| 路径 | 用途 |
| --- | --- |
| `frontend/.env.example` | 前端环境变量模板。 |
| `frontend/index.html` | 前端 HTML 入口。 |
| `frontend/package.json` | 前端依赖与运行脚本配置。 |
| `frontend/package-lock.json` | npm 依赖版本锁定文件。 |
| `frontend/tsconfig.json` | TypeScript 编译与类型检查配置。 |
| `frontend/vite.config.ts` | Vite 开发与构建配置。 |
| `frontend/src/App.vue` | 应用根组件，创建工作区状态并承载唯一控制台布局与页面标签。最后同步：2026-10-13。 |
| `frontend/src/api/health.ts` | 健康检查接口调用。 |
| `frontend/src/api/http.ts` | 通用 HTTP 请求封装、二进制下载、可配置超时与 SSE 事件读取和错误转换。最后同步：2026-10-13。 |
| `frontend/src/api/assets.ts` | 资产管理接口调用。最后同步：2026-10-10。 |
| `frontend/src/api/jump_hosts.ts` | 跳板机管理接口调用。 |
| `frontend/src/api/ssh_keys.ts` | SSH 密钥管理接口调用。 |
| `frontend/src/api/ssh_connections.ts` | 同步 SSH 连接测试调用，复用独立身份确认及专用请求时限。最后同步：2026-10-15。 |
| `frontend/src/api/inspections.ts` | 巡检规则、任务创建/历史分页/详情/删除、原始报告及 AI 汇报读取/生成接口调用。最后同步：2026-10-13。 |
| `frontend/src/api/ai.ts` | AI 配置、会话、流事件校验和计划决策接口调用。最后同步：2026-10-12。 |
| `frontend/src/types/ai.ts` | 模型能力、会话消息状态及巡检计划类型。最后同步：2026-10-12。 |
| `frontend/src/components/ChatProposalCard.vue` | 待确认时显示计划执行范围并发出确认或拒绝事件，决策后仅保留名称和状态。最后同步：2026-10-14。 |
| `frontend/src/components/ChatTaskCard.vue` | 轮询关联巡检任务与 AI 报告状态，展示执行摘要及本次报告、巡检记录的工作区跳转入口。最后同步：2026-10-14。 |
| `frontend/src/components/DisclosurePanel.vue` | 单项详情共用展开入口，接收名称、可选上下文、双向展开状态与内容插槽，使用中性描边按钮、左侧状态箭头和唯一内容关联；按需挂载详情。最后同步：2026-10-14。 |
| `frontend/src/components/ModelConnectionDialog.vue` | 模型连接新增编辑表单及密钥输入。最后同步：2026-10-12。 |
| `frontend/src/components/FeatureModelsForm.vue` | 独立功能模型表单，接收连接列表及加载状态，读取和保存对话、巡检汇报模型并发出配置状态事件。最后同步：2026-10-14。 |
| `frontend/src/views/ChatView.vue` | 对话首页，会话历史、首次发送自动使用主模型创建会话、流式输入输出和计划决策。最后同步：2026-10-12。 |
| `frontend/src/views/ModelConnectionsView.vue` | 模型连接管理及能力测试独立页面。最后同步：2026-10-12。 |
| `frontend/src/styles/ai.css` | 复用控制台主题的对话、模型配置和任务卡片样式。最后同步：2026-10-12。 |
| `frontend/src/components/SSHConnectionDialog.vue` | 单台连接测试，仅展示本次结果，身份阻断接入独立确认并发出状态变更事件。最后同步：2026-10-15。 |
| `frontend/src/components/BatchSSHConnectionDialog.vue` | 批量范围、逐身份显式确认、有界同步测试及停止后续提交；输入所选主机，展示本次结果并发出状态变更事件。最后同步：2026-10-15。 |
| `frontend/src/components/HostSSHStatus.vue` | 纯展示主机记录中的连接状态，复用统一测试图标，无额外请求及轮询。最后同步：2026-10-15。 |
| `frontend/src/components/TestStatus.vue` | 各类测试共用圆形状态图标、语义颜色、tooltip 与键盘焦点，接收状态、说明及可聚焦选项。最后同步：2026-10-13。 |
| `frontend/src/components/sshTestDisplay.ts` | 主机列表、单台与批量 SSH 测试共用状态映射及提示文案。最后同步：2026-10-13。 |
| `frontend/src/types/testStatus.ts` | 共用测试展示状态类型。最后同步：2026-10-13。 |
| `frontend/src/components/InspectionConfigForm.vue` | 巡检阈值、时限及服务配置表单与本地校验。最后同步：2026-10-12。 |
| `frontend/src/components/InspectionCreateDialog.vue` | 巡检任务创建弹窗，加载目录与资产、选择主机/检查并提交。最后同步：2026-10-12。 |
| `frontend/src/components/InspectionTaskDetail.vue` | 巡检主机概览、可折叠检查结果与风险、报告导出展示；详情不展示配置。最后同步：2026-10-12。 |
| `frontend/src/components/inspectionDisplay.ts` | 巡检执行状态、结论和时间的前端显示映射。最后同步：2026-10-12。 |
| `frontend/src/components/ServiceStatus.vue` | 后端连接状态展示组件。 |
| `frontend/src/components/feedback.ts` | 共用消息提示。 |
| `frontend/src/components/ListPagination.vue` | 共用列表分页控件，接收总数、加载可用状态及紧凑布局选项，双向绑定页码与每页数量，统一提供 10、20、50、100 条选择。最后同步：2026-10-15。 |
| `frontend/src/components/pagination.ts` | 共用分页数量配置与本地数组分页逻辑，维护当前页、数量切换重置及数据减少后的页码校正。最后同步：2026-10-13。 |
| `frontend/src/components/serverPagination.ts` | 六类管理列表共用后端分页状态与请求，处理请求失效、页长重置及末页校正。最后同步：2026-10-14。 |
| `frontend/src/components/AssetsLayout.vue` | AI、资产、巡检、六类服务器运维及配置管理共用控制台外壳，提供唯一顶栏、侧栏与内容插槽。最后同步：2026-10-14。 |
| `frontend/src/components/WorkspaceTabs.vue` | 工作区标签栏与页面面板，接收注入的标签状态并切换、关闭页面，复用 Element Plus 的键盘与溢出导航。最后同步：2026-10-13。 |
| `frontend/src/components/WorkspacePage.vue` | 标签页面路由容器，接收独立路由快照，为业务页面隔离路由参数与查询条件。最后同步：2026-10-13。 |
| `frontend/src/components/workspace.ts` | 布局内工作区状态与注入契约，管理标签去重、导航、关闭、滚动恢复及弹窗切页限制。最后同步：2026-10-13。 |
| `frontend/src/env.d.ts` | 补充 Vite 环境变量的 TypeScript 类型声明。 |
| `frontend/src/main.ts` | Vue 应用启动入口。 |
| `frontend/src/router/index.ts` | 对话、配置、资产、巡检及五个独立运维页面路由；旧主机名地址转到主机管理。最后同步：2026-10-14。 |
| `frontend/src/styles/main.css` | 全局基础样式与 Element Plus 组件主题，统一维护字体和公共交互状态。最后同步：2026-10-10。 |
| `frontend/src/styles/assets.css` | 主机、分组管理的共用布局与业务样式，包含导航选中态和分组表格样式。最后同步：2026-10-10。 |
| `frontend/src/styles/inspections.css` | 巡检创建、任务详情与结果列表样式。最后同步：2026-10-12。 |
| `frontend/src/types/api.ts` | 资产及 SSH 连接测试接口 TypeScript 类型定义。最后同步：2026-10-12。 |
| `frontend/src/types/inspections.ts` | 巡检请求、配置、执行状态、检查结果及报告 TypeScript 类型。最后同步：2026-10-12。 |
| `frontend/src/views/HostsView.vue` | 主机管理、跳板机关联选择、单台/批量连接测试及行内“更多 → 更改主机名”入口。最后同步：2026-10-14。 |
| `frontend/src/views/HostGroupsView.vue` | 独立分组管理页面，含分组列表、主机计数和分组增删改。最后同步：2026-10-10。 |
| `frontend/src/views/JumpHostsView.vue` | 独立跳板机管理页面及 SSH 连接测试入口。最后同步：2026-10-12。 |
| `frontend/src/views/SSHKeysView.vue` | 独立 SSH 密钥管理页面。 |
| `frontend/src/views/InspectionsView.vue` | 独立巡检任务页面，提供创建、任务进度与记录跳转。最后同步：2026-10-12。 |
| `frontend/src/views/InspectionRecordsView.vue` | 独立巡检记录入口，默认历史列表，选择记录后展示任务概览、AI 汇报和主机详情入口。最后同步：2026-10-13。 |
| `frontend/src/views/InspectionRecordDetailView.vue` | 独立服务器巡检记录详情页面，通过任务路由参数读取、轮询并复用主机检查详情与报告导出；提供返回记录入口。最后同步：2026-10-13。 |
| `frontend/src/components/InspectionRecordSummary.vue` | 巡检记录概览，接收任务详情，展示全任务严重/警告统计及详情跳转，复用状态与时间显示映射。最后同步：2026-10-13。 |
| `frontend/src/components/InspectionAnalysisReport.vue` | 经巡检 API 层生成、读取及轮询报告，展示巡检风险和精简错误分析，向问题组件传递日志证据并导出完整原文，兼容旧报告。最后同步：2026-10-13。 |
| `frontend/src/components/InspectionAnalysisEvidence.vue` | 接收报告证据与可选编号筛选，展示原文和来源表/结果行位置，复用 10/20/50 条分页，发出清除筛选事件；可复用于巡检报告证据查看。最后同步：2026-10-13。 |
| `frontend/src/components/InspectionAnalysisIssue.vue` | 接收问题、主机说明与日志证据，展示等级、名称、影响主机、原因和建议，折叠分页展示具体报错、主机、可用路径及时间次数。最后同步：2026-10-13。 |
| `frontend/src/components/inspectionAnalysisDisplay.ts` | 报告与问题组件共用的严重程度映射、诊断信息读取及新旧分段日志证据的具体报错详情转换。最后同步：2026-10-13。 |
| `frontend/src/views/InspectionRulesView.vue` | 独立巡检规则页面，展示检查项、当前阈值、时限与服务判定，并编辑保存规则。最后同步：2026-10-12。 |
| `frontend/src/components/InspectionTaskList.vue` | 任务与记录共用分页列表；历史页默认终态分页列表，点击后仅显示记录概览与 AI 汇报，支持返回列表、删除和活跃执行轮询。最后同步：2026-10-13。 |

## 独立 SSH 身份确认

| 路径 | 用途 |
| --- | --- |
| `backend/app/api/v1/endpoints/ssh_identities.py` | 身份检查及显式信任 HTTP 入口。最后同步：2026-10-14。 |
| `backend/app/schemas/ssh_identities.py` | 身份目标、确认及最小必要挑战响应，内部公钥类型、有效期和校验状态不对外输出。最后同步：2026-10-14。 |
| `backend/app/services/ssh_identities.py` | 无目标认证探测、挑战有效期、确认重探测及事务化信任更新。最后同步：2026-10-14。 |
| `frontend/src/types/sshIdentity.ts` | 身份目标、挑战、检查结果及取消边界类型。最后同步：2026-10-14。 |
| `frontend/src/api/ssh_identities.ts` | 独立身份接口调用与响应验证。最后同步：2026-10-14。 |
| `frontend/src/api/sshIdentity.ts` | 跨入口身份检查队列、确认桥接、取消与本次任务识别，不缓存信任状态。最后同步：2026-10-14。 |
| `frontend/src/components/SSHIdentityDialog.vue` | 全应用共用身份询问弹窗，显示服务器及新旧指纹，显式确认或取消。最后同步：2026-10-14。 |
