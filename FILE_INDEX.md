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
| `docs/` | 架构和设计文档。 |
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
| `.gitignore` | 排除虚拟环境、缓存、环境配置及构建产物等文件。 |
| `AGENTS.md` | 规定 Agent 的沟通、定位、实现、验证及 Git 操作行为，要求每次修改文件同步维护索引，兜底策略须展示并经用户明确同意后实现。最后同步：2026-10-10。 |
| `FILE_INDEX.md` | 记录仓库目录与文件职责，作为 Agent 阅读文件前的定位入口。 |
| `README.md` | 项目介绍、环境要求、安装启动、验证和部署说明。 |
| `main.py` | 兼容根目录 `uvicorn main:app` 启动方式的入口。 |
| `pyproject.toml` | 配置 pytest 测试目录和 Python 导入路径。 |
| `requirements.txt` | 根目录运行依赖入口，引用后端运行依赖清单。 |
| `requirements-dev.txt` | 根目录开发依赖入口，引用后端开发依赖清单。 |

## 文档文件

| 路径 | 用途 |
| --- | --- |
| `docs/architecture.md` | 记录前后端边界、架构决策、开发代理、环境配置与扩展约定。 |

## 后端文件

| 路径 | 用途 |
| --- | --- |
| `backend/.env.example` | 后端应用与 CORS 环境配置模板。 |
| `backend/__init__.py` | 声明后端 Python 包。 |
| `backend/requirements.txt` | 固定 FastAPI、Uvicorn 和配置管理相关运行依赖版本。 |
| `backend/requirements-dev.txt` | 引入运行依赖并固定测试所需开发依赖版本。 |
| `backend/app/__init__.py` | 声明后端应用包。 |
| `backend/app/main.py` | 创建 FastAPI 应用、配置 CORS、注册版本化及兼容路由，导出应用实例。 |
| `backend/app/api/__init__.py` | 声明 HTTP 接口包。 |
| `backend/app/api/v1/__init__.py` | 声明第一版 API 包。 |
| `backend/app/api/v1/router.py` | 汇总并注册 v1 接口路由。 |
| `backend/app/api/v1/endpoints/__init__.py` | 声明接口端点包。 |
| `backend/app/api/v1/endpoints/health.py` | 提供 v1 健康检查接口。 |
| `backend/app/core/__init__.py` | 声明配置及公共基础设施包。 |
| `backend/app/core/config.py` | 定义环境配置模型并缓存配置读取结果。 |
| `backend/app/schemas/__init__.py` | 声明接口数据模型包。 |
| `backend/app/schemas/health.py` | 定义健康检查响应模型。 |
| `backend/tests/test_health.py` | 验证健康接口、根路由、OpenAPI 文档及 CORS 来源边界。 |

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
| `frontend/src/api/http.ts` | 封装 GET 请求、API 前缀、超时及 HTTP 错误处理。 |
| `frontend/src/components/ServiceStatus.vue` | 展示后端连接状态、检查时间、错误提示和重试操作。 |
| `frontend/src/env.d.ts` | 补充 Vite 环境变量的 TypeScript 类型声明。 |
| `frontend/src/main.ts` | 加载样式与路由，创建并挂载 Vue 应用。 |
| `frontend/src/router/index.ts` | 配置首页路由和未知路径重定向。 |
| `frontend/src/styles/main.css` | 定义全局视觉样式、组件布局及窄屏适配。 |
| `frontend/src/types/api.ts` | 定义健康检查响应的 TypeScript 类型。 |
| `frontend/src/views/HomeView.vue` | 实现工作台首页布局并组合服务状态组件。 |
