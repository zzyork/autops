# autops

FastAPI + Vue 3 + TypeScript + Element Plus 基础工程，使用 Vite 开发与构建。

## 项目目录

```text
autops/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/   # 按业务组织接口
│   │   ├── core/              # 环境配置及公共基础设施
│   │   ├── schemas/           # 请求、响应数据模型
│   │   └── main.py            # 应用工厂与入口
│   ├── tests/                 # 接口测试
│   ├── .env.example
│   ├── requirements.txt
│   └── requirements-dev.txt
├── frontend/
│   ├── src/
│   │   ├── api/               # 请求封装与接口调用
│   │   ├── components/        # 复用组件
│   │   ├── router/            # 页面路由
│   │   ├── styles/            # 全局样式
│   │   ├── types/             # TypeScript 数据类型
│   │   ├── views/             # 页面
│   │   ├── App.vue
│   │   └── main.ts
│   ├── .env.example
│   ├── package.json
│   ├── package-lock.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── docs/architecture.md       # 架构决策与扩展约定
├── main.py                    # 原启动方式的兼容入口
├── requirements*.txt          # 指向后端依赖的兼容入口
└── pyproject.toml             # 测试配置
```

## 环境要求

- Python 3.13（当前开发环境）。
- Node.js 20.19+ 或 22.12+，推荐 Node.js 24 LTS；npm。
- 以下命令使用 Windows PowerShell，后端命令均在仓库根目录执行。

## 安装依赖

已有 `.venv` 时跳过创建步骤：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
npm --prefix frontend ci
```

默认配置可以直接启动。需要调整时复制模板：

```powershell
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env
```

后端固定从 `backend/.env` 读取配置；前端从 `frontend/.env` 读取配置。后端跨域来源采用 JSON 数组。`VITE_` 变量会进入浏览器，不能存放密钥。

## 本地启动

在两个终端分别运行：

```powershell
# 终端 1：后端
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

```powershell
# 终端 2：前端
npm --prefix frontend run dev
```

- 前端工作台：http://127.0.0.1:5173
- 版本化健康检查：http://127.0.0.1:8000/api/v1/health
- Swagger 文档：http://127.0.0.1:8000/docs
- ReDoc 文档：http://127.0.0.1:8000/redoc
- 兼容接口：`/` 和 `/health`；兼容启动命令：`uvicorn main:app --reload`。

首页自动检查后端状态，支持手动重试。开发时 `/api` 请求由 Vite 代理至 `http://127.0.0.1:8000`，可通过 `API_PROXY_TARGET` 修改。

## 验证与构建

```powershell
.\.venv\Scripts\python.exe -m pytest
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

构建命令包含类型检查，产物位于 `frontend/dist/`。可使用 `npm --prefix frontend run preview` 查看产物；预览服务不提供开发代理，接口联通需要配置实际后端地址及对应 CORS 来源。

生产环境使用静态服务器提供 `dist/`，将 `/api` 反向代理至 FastAPI；Vue history 路由需回退到 `index.html`。本次初始化未包含数据库、认证或具体业务模块，后续扩展约定见 [架构说明](docs/architecture.md)。
