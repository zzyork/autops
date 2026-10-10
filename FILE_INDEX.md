# 仓库文件索引

本文件用于帮助 Agent 按功能定位目录和文件。路径均相对于仓库根目录。需要阅读文件内容时，先查本索引定位，再读取相关文件的实际内容。

覆盖范围为 Git 已跟踪文件及尚未跟踪、但未被 Git 忽略的项目文件，以及它们所在的目录。不收录 `.git/` 内部数据、虚拟环境、依赖安装目录、缓存及构建产物；Git 不保存空目录。每次修改任何项目文件，都须同步核对并更新对应条目；用途未变时更新条目的最后同步日期。新增、删除或移动文件时，同步调整路径及目录条目。

索引维护日期：2026-10-10。条目未单独标注最后同步日期时，以此日期作为初始核对日期；后续修改文件时在用途说明末尾标注最后同步日期。

## 目录用途

| 路径 | 用途 |
| --- | --- |
| `./` | 项目根目录，存放工作约定、文件索引、项目说明和兼容入口。 |
| `backend/` | FastAPI 后端项目。 |
| `backend/app/` | 后端应用包。 |
| `backend/app/api/` | HTTP 接口代码。 |
| `backend/app/api/v1/` | 第一版 API 路由。 |
| `backend/app/api/v1/endpoints/` | 按功能组织的接口端点。 |
| `backend/app/core/` | 应用配置与公共基础设施。 |
| `backend/app/schemas/` | 接口数据模型。 |
| `backend/tests/` | 后端接口测试。 |
| `docs/` | 项目文档及前端 UI 规范。最后同步：2026-10-10。 |
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
| `.gitignore` | 排除虚拟环境、缓存、环境配置、构建产物及 backend/runtime 数据库和密钥。最后同步：2026-10-10。 |
| `AGENTS.md` | 规定 Agent 的沟通、定位、实现、验证及 Git 操作行为，要求前端任务遵守 UI 规范、修改文件同步维护索引，兜底策略须展示并经用户明确同意后实现。最后同步：2026-10-10。 |
| `FILE_INDEX.md` | 记录仓库目录与文件职责，作为 Agent 阅读文件前的定位入口。 |
| `README.md` | 项目介绍、环境要求、安装启动、资产管理操作、数据库与密钥备份及验证部署说明。最后同步：2026-10-10。 |
| `main.py` | 兼容根目录 `uvicorn main:app` 启动方式的入口。 |
| `pyproject.toml` | 配置 pytest 测试目录和 Python 导入路径。 |
| `requirements.txt` | 根目录运行依赖入口，引用后端运行依赖清单。 |
| `requirements-dev.txt` | 根目录开发依赖入口，引用后端开发依赖清单。 |

## 文档文件

| 路径 | 用途 |
| --- | --- |
| `docs/architecture.md` | 记录前后端边界、架构决策、开发代理和 SQLite 资产管理、凭据加密及验证约定。最后同步：2026-10-10。 |
| `docs/asset-management-plan.md` | 说明 hosts 管理迁为 Web UI 与数据库资产管理的范围及步骤，记录首版实施状态、入口和自动密钥管理约定。最后同步：2026-10-10。 |
| `docs/frontend-ui-spec.md` | 前端页面、组件和样式必须遵守的 UI 规范，定义独立配色及禁止照搬其他产品色板的规则、颜色变量与对比度要求，以及布局、组件、响应式和验收要求。最后同步：2026-10-10。 |

## 后端文件

| 路径 | 用途 |
| --- | --- |
| `backend/.env.example` | 后端应用、CORS 和可选资产数据目录配置模板。最后同步：2026-10-10。 |
| `backend/__init__.py` | 声明后端 Python 包。 |
| `backend/requirements.txt` | 固定 FastAPI、Uvicorn、配置管理、SQLAlchemy 及 cryptography 运行依赖版本。最后同步：2026-10-10。 |
| `backend/requirements-dev.txt` | 引入运行依赖并固定测试所需开发依赖版本。 |
| `backend/app/__init__.py` | 声明后端应用包。 |
| `backend/app/main.py` | 创建 FastAPI 应用、配置 CORS、注册路由，在 lifespan 初始化资产存储并脱敏校验错误响应。最后同步：2026-10-10。 |
| `backend/app/models.py` | 定义主机与分组 SQLAlchemy 模型、关联及唯一约束和主机版本检查。最后同步：2026-10-10。 |
| `backend/app/api/__init__.py` | 声明 HTTP 接口包。 |
| `backend/app/api/v1/__init__.py` | 声明第一版 API 包。 |
| `backend/app/api/v1/router.py` | 汇总并注册 v1 健康检查与资产管理接口路由。最后同步：2026-10-10。 |
| `backend/app/api/v1/endpoints/__init__.py` | 声明接口端点包。 |
| `backend/app/api/v1/endpoints/health.py` | 提供 v1 健康检查接口。 |
| `backend/app/api/v1/endpoints/assets.py` | 提供主机与分组 CRUD、搜索筛选、关联校验、凭据更新及版本冲突处理。最后同步：2026-10-10。 |
| `backend/app/core/__init__.py` | 声明配置及公共基础设施包。 |
| `backend/app/core/config.py` | 定义环境配置和资产运行数据目录，并缓存配置读取结果。最后同步：2026-10-10。 |
| `backend/app/core/storage.py` | 初始化 SQLite、保护密钥目录与文件权限、原子创建 Fernet 密钥及校验已有凭据。最后同步：2026-10-10。 |
| `backend/app/schemas/__init__.py` | 声明接口数据模型包。 |
| `backend/app/schemas/health.py` | 定义健康检查响应模型。 |
| `backend/app/schemas/assets.py` | 定义资产请求响应、地址及连接配置校验和 UTC 时间戳输出。最后同步：2026-10-10。 |
| `backend/tests/test_health.py` | 在独立临时数据库下验证健康接口、根路由、OpenAPI 文档及 CORS 来源边界。最后同步：2026-10-10。 |
| `backend/tests/test_assets.py` | 验证资产 CRUD、筛选及约束、密文及重启保留、密钥异常、凭据切换、版本冲突及错误响应脱敏。最后同步：2026-10-10。 |

## 前端文件

| 路径 | 用途 |
| --- | --- |
| `frontend/.env.example` | 前端 API 前缀及 Vite 开发代理配置模板。 |
| `frontend/index.html` | HTML 入口，定义页面元信息和 Vue 挂载节点。 |
| `frontend/package.json` | 声明依赖、Node.js 版本要求及开发、检查、构建和预览脚本。 |
| `frontend/package-lock.json` | npm 生成的依赖解析锁文件，用于复现安装版本。 |
| `frontend/tsconfig.json` | 配置 TypeScript 严格检查、模块解析、路径别名及检查范围。 |
| `frontend/vite.config.ts` | 配置 Vue 插件、源码别名、开发服务器和 API 代理。 |
| `frontend/src/App.vue` | 应用根组件，承载路由视图。 |
| `frontend/src/api/health.ts` | 调用后端健康检查接口并关联响应类型。 |
| `frontend/src/api/http.ts` | 封装通用 JSON 请求、204 处理、超时、受控业务错误及字段校验提示，保持 GET 兼容。最后同步：2026-10-10。 |
| `frontend/src/api/assets.ts` | 封装主机与分组 CRUD、主机搜索及分组筛选接口。最后同步：2026-10-10。 |
| `frontend/src/components/ServiceStatus.vue` | 展示后端连接状态、检查时间、错误提示和重试操作。 |
| `frontend/src/env.d.ts` | 补充 Vite 环境变量的 TypeScript 类型声明。 |
| `frontend/src/main.ts` | 加载样式与路由，创建并挂载 Vue 应用。 |
| `frontend/src/router/index.ts` | 配置资产管理路由，根路径及未知路径直接重定向至资产管理。最后同步：2026-10-10。 |
| `frontend/src/styles/main.css` | 定义全局视觉样式、首页资产入口及窄屏适配。最后同步：2026-10-10。 |
| `frontend/src/styles/assets.css` | 定义全宽后台布局、固定顶栏和侧边菜单、面包屑、白色分组与列表卡片及响应式表单样式。最后同步：2026-10-10。 |
| `frontend/src/types/api.ts` | 定义健康检查、主机分组及主机请求响应的 TypeScript 类型。最后同步：2026-10-10。 |
| `frontend/src/views/AssetsView.vue` | 实现后台顶栏、可收起导航、面包屑及资产卡片，提供分组与主机 CRUD、搜索刷新、密码保留和版本提交。最后同步：2026-10-10。 |
