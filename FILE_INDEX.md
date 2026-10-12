# 仓库文件索引

本文件记录目录和文件的用途，路径均相对于仓库根目录。

覆盖已跟踪及未被忽略的项目文件，不收录环境、依赖、缓存和构建产物。

原项目位置：`E:\Codes\autodeploykit`。迁移已有功能时，从该目录定位并阅读原实现。

索引维护日期：2026-10-12。条目未单独标注最后同步日期时，以此日期作为初始核对日期；后续修改文件时在用途说明末尾标注最后同步日期。

## 目录用途

| 路径 | 用途 |
| --- | --- |
| `./` | 项目根目录。 |
| `backend/` | FastAPI 后端项目。 |
| `backend/app/` | 后端应用包。 |
| `backend/app/api/` | HTTP 接口代码与共用数据库依赖。最后同步：2026-10-10。 |
| `backend/app/api/v1/` | 第一版 API 路由。 |
| `backend/app/api/v1/endpoints/` | 按功能组织的接口端点。 |
| `backend/app/core/` | 应用配置与公共基础设施。 |
| `backend/app/core/migrations/` | SSH 连接相关新增表的可重复启动迁移。最后同步：2026-10-12。 |
| `backend/app/repositories/` | SSH 资产、主机密钥信任与连接测试记录查询。最后同步：2026-10-12。 |
| `backend/app/services/` | SSH 资产解析、连接测试执行与主机密钥确认。最后同步：2026-10-12。 |
| `backend/app/schemas/` | 接口数据模型。 |
| `backend/tests/` | 主机与分组接口测试，纳入版本管理。最后同步：2026-10-10。 |
| `docs/` | 项目文档及 AI 前端、后端开发约束规范。最后同步：2026-10-12。 |
| `frontend/` | Vue、TypeScript、Vite 前端项目。 |
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
| `.gitignore` | Git 文件忽略配置，保留后端测试文件供版本管理。最后同步：2026-10-10。 |
| `AGENTS.md` | 项目 Agent 工作约定，要求设计、编码及审核时严格执行 docs 下的前端、后端开发规范。最后同步：2026-10-12。 |
| `FILE_INDEX.md` | 仓库目录与文件用途索引。 |
| `README.md` | 项目介绍与安装、运行和使用说明。最后同步：2026-10-10。 |
| `main.py` | 兼容根目录 `uvicorn main:app` 启动方式的入口。 |
| `pyproject.toml` | 配置 pytest 测试目录和 Python 导入路径。 |
| `requirements.txt` | 根目录运行依赖入口，引用后端运行依赖清单。 |
| `requirements-dev.txt` | 根目录开发依赖入口，引用后端开发依赖清单。 |

## 文档文件

| 路径 | 用途 |
| --- | --- |
| `docs/AI-前端开发约束规范.md` | AI 前端开发约束及项目 UI 实施标准。最后同步：2026-10-12。 |
| `docs/AI-后端开发约束规范.md` | AI 后端架构、接口、数据库、安全及验证约束。最后同步：2026-10-12。 |
| `docs/ssh-connections.md` | SSH 连接测试、主机密钥信任、接口和单实例运行说明。最后同步：2026-10-12。 |

## 后端文件

| 路径 | 用途 |
| --- | --- |
| `backend/.env.example` | 后端环境变量模板。最后同步：2026-10-10。 |
| `backend/__init__.py` | 声明后端 Python 包。 |
| `backend/requirements.txt` | 后端运行依赖清单，包含 Paramiko SSH 连接依赖。最后同步：2026-10-12。 |
| `backend/requirements-dev.txt` | 后端开发与测试依赖清单。 |
| `backend/app/__init__.py` | 声明后端应用包。 |
| `backend/app/main.py` | FastAPI 应用入口及连接测试执行器生命周期管理。最后同步：2026-10-12。 |
| `backend/app/connection_models.py` | 连接测试记录与服务器主机密钥信任数据库模型。最后同步：2026-10-12。 |
| `backend/app/models.py` | 主机、分组、跳板机与 SSH 密钥数据库模型。最后同步：2026-10-10。 |
| `backend/app/api/__init__.py` | 声明 HTTP 接口包。 |
| `backend/app/api/dependencies.py` | 共用数据库会话依赖、事务提交与分组查询。最后同步：2026-10-10。 |
| `backend/app/api/v1/__init__.py` | 声明第一版 API 包。 |
| `backend/app/api/v1/router.py` | v1 API 路由汇总，注册资产与 SSH 连接测试接口。最后同步：2026-10-12。 |
| `backend/app/api/v1/endpoints/ssh_connections.py` | SSH 连接测试提交、查询与主机密钥确认接口。最后同步：2026-10-12。 |
| `backend/app/api/v1/endpoints/__init__.py` | 声明接口端点包。 |
| `backend/app/api/v1/endpoints/health.py` | 提供 v1 健康检查接口。 |
| `backend/app/api/v1/endpoints/hosts.py` | 主机管理及跳板机关联接口。最后同步：2026-10-10。 |
| `backend/app/api/v1/endpoints/jump_hosts.py` | 独立跳板机管理接口。 |
| `backend/app/api/v1/endpoints/credentials.py` | 主机与跳板机共用凭据处理。 |
| `backend/app/api/v1/endpoints/ssh_keys.py` | 独立 SSH 密钥管理与引用查询接口。 |
| `backend/app/api/v1/endpoints/host_groups.py` | 分组管理接口及组内主机计数。最后同步：2026-10-10。 |
| `backend/app/core/__init__.py` | 声明配置及公共基础设施包。 |
| `backend/app/core/config.py` | 后端应用配置。最后同步：2026-10-10。 |
| `backend/app/core/storage.py` | 资产数据库、凭据密钥管理及旧配置迁移，调用连接表迁移。最后同步：2026-10-12。 |
| `backend/app/core/ssh.py` | SSH 直连、单层跳板、内存私钥解析与身份校验。最后同步：2026-10-12。 |
| `backend/app/core/ssh_network.py` | DNS 与 TCP 建连、整体超时及网络资源清理。最后同步：2026-10-12。 |
| `backend/app/core/migrations/__init__.py` | 声明数据库迁移包。最后同步：2026-10-12。 |
| `backend/app/core/migrations/ssh_connections.py` | 幂等创建连接测试与主机密钥信任表。最后同步：2026-10-12。 |
| `backend/app/repositories/__init__.py` | 声明仓储包。最后同步：2026-10-12。 |
| `backend/app/repositories/ssh_connections.py` | SSH 资产、密钥、信任与测试历史查询及重启状态更新。最后同步：2026-10-12。 |
| `backend/app/services/__init__.py` | 声明业务服务包。最后同步：2026-10-12。 |
| `backend/app/services/ssh_assets.py` | SSH 连接配置解析、凭据解密及资产版本快照。最后同步：2026-10-12。 |
| `backend/app/services/ssh_connections.py` | 有界后台连接测试、持久化结果与事务化主机密钥确认。最后同步：2026-10-12。 |
| `backend/app/core/ssh_keys.py` | SSH 公私钥内容与配对校验、指纹生成。最后同步：2026-10-10。 |
| `backend/app/schemas/__init__.py` | 声明接口数据模型包。 |
| `backend/app/schemas/health.py` | 定义健康检查响应模型。 |
| `backend/app/schemas/assets.py` | 资产管理接口数据模型。最后同步：2026-10-10。 |
| `backend/app/schemas/jump_hosts.py` | 跳板机接口数据模型。 |
| `backend/app/schemas/ssh_keys.py` | SSH 密钥与引用接口数据模型。 |
| `backend/app/schemas/ssh_connections.py` | SSH 连接测试请求、状态、身份挑战与响应模型。最后同步：2026-10-12。 |
| `backend/tests/test_assets.py` | 使用 TestClient 验证主机、分组的 CRUD、筛选及异常路径。最后同步：2026-10-10。 |

## 前端文件

| 路径 | 用途 |
| --- | --- |
| `frontend/.env.example` | 前端环境变量模板。 |
| `frontend/index.html` | 前端 HTML 入口。 |
| `frontend/package.json` | 前端依赖与运行脚本配置。 |
| `frontend/package-lock.json` | npm 依赖版本锁定文件。 |
| `frontend/tsconfig.json` | TypeScript 编译与类型检查配置。 |
| `frontend/vite.config.ts` | Vite 开发与构建配置。 |
| `frontend/src/App.vue` | 应用根组件，承载路由视图。 |
| `frontend/src/api/health.ts` | 健康检查接口调用。 |
| `frontend/src/api/http.ts` | 通用 HTTP 请求封装。最后同步：2026-10-10。 |
| `frontend/src/api/assets.ts` | 资产管理接口调用。最后同步：2026-10-10。 |
| `frontend/src/api/jump_hosts.ts` | 跳板机管理接口调用。 |
| `frontend/src/api/ssh_keys.ts` | SSH 密钥管理接口调用。 |
| `frontend/src/api/ssh_connections.ts` | SSH 连接测试提交、历史、状态与信任接口调用。最后同步：2026-10-12。 |
| `frontend/src/components/SSHConnectionDialog.vue` | 主机与跳板机共用连接测试、结果查询和身份信任弹窗。最后同步：2026-10-12。 |
| `frontend/src/components/HostSSHStatus.vue` | 主机列表统一 SSH 状态图标，查询最近测试、跟踪未完成测试并提供状态说明。最后同步：2026-10-12。 |
| `frontend/src/components/ServiceStatus.vue` | 后端连接状态展示组件。 |
| `frontend/src/components/feedback.ts` | 共用消息提示。 |
| `frontend/src/components/AssetsLayout.vue` | 资产页面共用控制台布局、导航和面包屑。最后同步：2026-10-10。 |
| `frontend/src/env.d.ts` | 补充 Vite 环境变量的 TypeScript 类型声明。 |
| `frontend/src/main.ts` | Vue 应用启动入口。 |
| `frontend/src/router/index.ts` | 主机、分组、跳板机与 SSH 密钥独立页面路由。最后同步：2026-10-10。 |
| `frontend/src/styles/main.css` | 全局基础样式与 Element Plus 组件主题，统一维护字体和公共交互状态。最后同步：2026-10-10。 |
| `frontend/src/styles/assets.css` | 主机、分组管理的共用布局与业务样式，包含导航选中态和分组表格样式。最后同步：2026-10-10。 |
| `frontend/src/types/api.ts` | 资产及 SSH 连接测试接口 TypeScript 类型定义。最后同步：2026-10-12。 |
| `frontend/src/views/HostsView.vue` | 主机管理、跳板机关联选择与 SSH 连接测试入口。最后同步：2026-10-12。 |
| `frontend/src/views/HostGroupsView.vue` | 独立分组管理页面，含分组列表、主机计数和分组增删改。最后同步：2026-10-10。 |
| `frontend/src/views/JumpHostsView.vue` | 独立跳板机管理页面及 SSH 连接测试入口。最后同步：2026-10-12。 |
| `frontend/src/views/SSHKeysView.vue` | 独立 SSH 密钥管理页面。 |
