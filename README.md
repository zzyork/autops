# autops

基于 FastAPI + Vue 3 + TypeScript + Element Plus 的运维 Web UI，使用 Vite 开发与构建。当前提供资产管理与 SSH 连接测试，可在页面维护主机、分组、SSH 与跳板机配置，并保存到 SQLite。

## 项目目录

```text
autops/
├── backend/
│   ├── app/
│   │   ├── api/dependencies.py # 共用数据库依赖与事务处理
│   │   ├── api/v1/endpoints/   # 主机、分组与跳板机独立接口
│   │   ├── core/              # 环境配置及公共基础设施
│   │   ├── repositories/      # SSH 资产与测试记录查询
│   │   ├── services/          # SSH 资产解析及后台连接测试
│   │   ├── schemas/           # 请求、响应数据模型
│   │   ├── connection_models.py # 连接测试与主机密钥信任模型
│   │   ├── models.py          # 资产数据库模型
│   │   └── main.py            # 应用工厂与入口
│   ├── runtime/               # 自动生成的数据库和密钥，不纳入版本控制
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
│   │   ├── views/             # 主机、分组与跳板机独立管理页面
│   │   ├── App.vue
│   │   └── main.ts
│   ├── .env.example
│   ├── package.json
│   ├── package-lock.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── docs/                      # 开发规范与 SSH 连接使用说明
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

- 前端入口：http://127.0.0.1:5173（直接进入主机管理）
- 主机管理：http://127.0.0.1:5173/assets/hosts
- 分组管理：http://127.0.0.1:5173/assets/groups
- 跳板机管理：http://127.0.0.1:5173/assets/jump-hosts
- 版本化健康检查：http://127.0.0.1:8000/api/v1/health
- Swagger 文档：http://127.0.0.1:8000/docs
- ReDoc 文档：http://127.0.0.1:8000/redoc
- 兼容接口：`/` 和 `/health`；兼容启动命令：`uvicorn main:app --reload`。

打开前端根路径会直接进入主机管理。开发时 `/api` 请求由 Vite 代理至 `http://127.0.0.1:8000`，可通过 `API_PROXY_TARGET` 修改。

## 资产管理

主机、分组、跳板机和 SSH 密钥通过独立页面管理，共用控制台导航。主机与跳板机列表中的“连接测试”使用已保存的凭据验证 SSH 身份和登录，支持直连、VIP 及单层跳板机。首次连接或服务器主机密钥变化时，须独立核对指纹并确认信任，再重新测试。详细流程见 [SSH 连接与测试](docs/ssh-connections.md)。

后端首次启动自动创建：

- `backend/runtime/assets.db`：SQLite 数据库。
- `backend/runtime/secrets/fernet.key`：Fernet 加密密钥，后续启动自动读取，无需手动配置。

可通过后端 `AUTOPS_DATA_DIR` 指定绝对数据目录，建议自定义目录位于仓库外。Windows 下需要 PowerShell 5.1，程序用运行账号的 ACL 保护密钥目录和文件；Linux 下目录权限为 `0700`、密钥文件为 `0600`。权限设置失败会阻止启动。

备份时先停止本地后端服务，再同时复制数据库与对应密钥；迁移后以目标服务账号运行。已有加密凭据时，密钥丢失、损坏或不匹配会阻止启动，不会生成替代密钥。默认运行目录已被 Git 忽略。

当前不包含身份认证、操作审计、权限控制、hosts 批量导入或部署与巡检模块。

连接测试不执行远程命令或 sudo 操作。记录保存到 SQLite，关闭弹窗不取消后端测试，重启后未完成记录标记为中断。当前只支持单实例、单 Uvicorn worker，请勿使用 `--workers` 扩展；多人共享或网络开放前需完成身份认证和权限控制。

## 验证与构建

```powershell
.\.venv\Scripts\python.exe -m pytest
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

构建命令包含类型检查，产物位于 `frontend/dist/`。可使用 `npm --prefix frontend run preview` 查看产物；预览服务不提供开发代理，接口联通需要配置实际后端地址及对应 CORS 来源。

生产环境使用静态服务器提供 `dist/`，将 `/api` 反向代理至 FastAPI；Vue history 路由需回退到 `index.html`。当前资产管理使用单实例 SQLite。
