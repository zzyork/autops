# autops

基于 FastAPI + Vue 3 + TypeScript + Element Plus 的运维 Web UI，使用 Vite 开发与构建。当前提供资产管理，可在页面维护主机、分组、SSH 与跳板机配置，并保存到 SQLite。

## 项目目录

```text
autops/
├── backend/
│   ├── app/
│   │   ├── api/dependencies.py # 共用数据库依赖与事务处理
│   │   ├── api/v1/endpoints/   # hosts.py 与 host_groups.py 分别管理主机、分组接口
│   │   ├── core/              # 环境配置及公共基础设施
│   │   ├── schemas/           # 请求、响应数据模型
│   │   ├── models.py          # 主机与分组数据库模型
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
│   │   ├── views/             # HostsView.vue 与 HostGroupsView.vue 独立管理页面
│   │   ├── App.vue
│   │   └── main.ts
│   ├── .env.example
│   ├── package.json
│   ├── package-lock.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── docs/frontend-ui-spec.md    # 前端 UI 规范
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
- 原资产入口：http://127.0.0.1:5173/assets（重定向至主机管理）
- 版本化健康检查：http://127.0.0.1:8000/api/v1/health
- Swagger 文档：http://127.0.0.1:8000/docs
- ReDoc 文档：http://127.0.0.1:8000/redoc
- 兼容接口：`/` 和 `/health`；兼容启动命令：`uvicorn main:app --reload`。

打开前端根路径会直接进入主机管理。开发时 `/api` 请求由 Vite 代理至 `http://127.0.0.1:8000`，可通过 `API_PROXY_TARGET` 修改。

## 资产管理

资产管理下的主机管理与分组管理使用独立页面，通过左侧主导航切换，无需登录。先在分组管理中新增分组，再到主机管理新增主机；主机页面内的分组栏仅用于筛选，列表支持名称与地址搜索。分组页面维护名称、备注，并显示主机数量。两页通过 `AssetsLayout.vue` 复用控制台导航和布局。主机可配置密码或私钥路径认证，以及可选跳板机、VIP 和备注。私钥路径是后端机器上的路径，本阶段只保存配置，不连接服务器或检查文件是否存在。

编辑时密码不回显，留空保留原密码；修改地址、用户名或端口时需要重新填写对应密码。切换为私钥认证会清除旧密码，关闭跳板机会清除其配置。主机编辑使用版本检查，旧表单不能覆盖已更新的数据。有主机的分组不能直接删除；删除资产仅删除本地数据库记录。

后端首次启动自动创建：

- `backend/runtime/assets.db`：SQLite 数据库。
- `backend/runtime/secrets/fernet.key`：Fernet 加密密钥，后续启动自动读取，无需手动配置。

可通过后端 `AUTOPS_DATA_DIR` 指定绝对数据目录，建议自定义目录位于仓库外。Windows 下需要 PowerShell 5.1，程序用运行账号的 ACL 保护密钥目录和文件；Linux 下目录权限为 `0700`、密钥文件为 `0600`。权限设置失败会阻止启动。

备份时先停止本地后端服务，再同时复制数据库与对应密钥；迁移后以目标服务账号运行。已有加密凭据时，密钥丢失、损坏或不匹配会阻止启动，不会生成替代密钥。默认运行目录已被 Git 忽略。

资产接口为 `/api/v1/host-groups` 和 `/api/v1/hosts`，分别由 `host_groups.py` 与 `hosts.py` 提供并独立注册路由，支持增删改查；主机列表接受 `q`、`group_id` 筛选参数。接口不会返回密码或密文，校验错误也不会回显提交的密码。主机更新需携带查询响应中的 `version`。

当前不包含身份认证、操作审计、权限控制、hosts 批量导入或部署与巡检模块。

## 验证与构建

```powershell
.\.venv\Scripts\python.exe -m pytest
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

构建命令包含类型检查，产物位于 `frontend/dist/`。可使用 `npm --prefix frontend run preview` 查看产物；预览服务不提供开发代理，接口联通需要配置实际后端地址及对应 CORS 来源。

生产环境使用静态服务器提供 `dist/`，将 `/api` 反向代理至 FastAPI；Vue history 路由需回退到 `index.html`。当前资产管理使用单实例 SQLite。
