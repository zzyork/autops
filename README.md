# autops

管理主机资产，验证 SSH 连接，执行只读巡检。

autops 是面向运维人员的 Web 控制台，将主机配置、连接测试和巡检记录集中保存在本地，方便从资产维护一路完成主机检查与报告导出。前端使用 Vue 3、TypeScript、Element Plus 和 Vite，后端使用 FastAPI 与 SQLite。

## 当前功能

- **资产管理**：独立管理主机、分组、跳板机和 SSH 密钥。
- **连接测试**：验证 SSH 登录，支持直连、VIP 和单层跳板机，并确认服务器主机密钥。
- **主机巡检**：检查系统基础信息、系统资源、服务状态和网络信息；可编辑后续任务使用的统一规则。
- **结果留存**：查看任务进度与历史检查结果，导出包含本次规则快照的 Markdown 报告；可确认删除已结束的记录。
- **凭据保护**：使用 Fernet 加密保存凭据，限制本地密钥目录与文件权限。

当前适合本地、单实例使用，仅支持单个 Uvicorn worker。项目尚未提供身份认证、权限控制和操作审计；多人共享或开放网络访问前，需要先落实访问控制。

## 快速开始

以下命令使用 **Windows PowerShell**，均从仓库根目录执行。请先将源码放到本地并进入项目目录。

环境要求：

- Python 3.13（当前开发环境版本）。
- Node.js 20.19+（20.x）或 22.12+，推荐 Node.js 24 LTS；npm。
- Windows 下的密钥权限设置需要 PowerShell 5.1。

### 1. 安装依赖

已有 `.venv` 时跳过第一条命令。

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
npm --prefix frontend ci
```

### 2. 启动服务

默认配置可直接启动，无需先创建 `.env`。在两个终端分别运行：

```powershell
# 终端 1：后端
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

```powershell
# 终端 2：前端
npm --prefix frontend run dev
```

### 3. 打开控制台

访问 [http://127.0.0.1:5173](http://127.0.0.1:5173)，默认进入主机管理。首次后端启动会自动创建数据库和加密密钥。

后端验证入口：

- [健康检查](http://127.0.0.1:8000/api/v1/health)
- [Swagger API 文档](http://127.0.0.1:8000/docs)
- [ReDoc API 文档](http://127.0.0.1:8000/redoc)

## 完成一次主机巡检

1. 首次使用时先在“分组管理”创建分组，再在“主机管理”保存目标主机及 SSH 凭据；需要跳板连接时，先在“跳板机管理”保存跳板机并关联到主机。SSH 密钥可在独立页面维护。
2. 对目标主机及所用跳板机执行“连接测试”。首次连接或服务器主机密钥变化时，独立核对指纹并确认信任，再重新测试。
3. 可先在“巡检规则”编辑并保存统一规则（阈值、时限及服务配置）；保存只影响之后创建的任务，历史快照不变。打开“巡检任务”创建任务，选择 1–32 台主机及至少一类检查；创建时不能单独调整规则。
4. 在任务列表查看进度，在“巡检记录”查看执行状态、风险结论与主机检查概览；检查项可折叠。任务结束后可导出 Markdown 报告，或在确认影响后删除记录及关联结果；详情页不展示规则配置，报告仍包含本次配置。

连接测试只验证 SSH 身份和登录，不执行远程命令或 `sudo`。巡检面向 Linux 主机，执行固定只读命令，不自动使用 `sudo`；目标账号须有相应命令的执行权限。

**执行完成不代表主机健康正常。** 检查失败、跳过或中断时，不能据此判定健康正常。关闭弹窗不取消后台任务；服务重启后未完成记录标记为中断。

完整检查口径、默认阈值、执行限制、接口和故障处理见 [主机巡检说明](docs/inspections.md)。

### 页面入口

| 页面 | 路径 |
| --- | --- |
| 主机管理 | `/assets/hosts` |
| 分组管理 | `/assets/groups` |
| 跳板机管理 | `/assets/jump-hosts` |
| SSH 密钥管理 | `/assets/ssh-keys` |
| 巡检任务 | `/inspections` |
| 巡检记录 | `/inspections/records` |
| 巡检规则 | `/inspections/rules` |

## 配置

需要调整配置时，复制模板后编辑；已有 `.env` 时直接编辑，避免覆盖现有配置。

```powershell
if (-not (Test-Path -LiteralPath backend/.env)) { Copy-Item backend/.env.example backend/.env }
if (-not (Test-Path -LiteralPath frontend/.env)) { Copy-Item frontend/.env.example frontend/.env }
```

后端固定读取 `backend/.env`，前端读取 `frontend/.env`。

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `AUTOPS_APP_NAME` | `autops API` | 后端应用名称 |
| `AUTOPS_DEBUG` | `false` | 后端调试模式 |
| `AUTOPS_DATA_DIR` | `backend/runtime`（项目内的绝对路径） | 数据与密钥目录；自定义时指定绝对路径，建议放在仓库外 |
| `AUTOPS_CORS_ORIGINS` | `["http://localhost:5173","http://127.0.0.1:5173"]` | 允许的跨域来源，使用 JSON 数组 |
| `VITE_API_BASE_URL` | `/api/v1` | 浏览器请求的 API 前缀 |
| `API_PROXY_TARGET` | `http://127.0.0.1:8000` | Vite 开发代理的后端地址 |

开发时 Vite 将 `/api` 请求代理至后端。`VITE_` 变量会进入浏览器，不能存放密钥；`API_PROXY_TARGET` 仅用于开发代理。

## 数据与备份

默认运行数据位于 `backend/runtime/`，该目录已被 Git 忽略：

| 文件 | 内容 |
| --- | --- |
| `assets.db` | 资产、连接测试、SSH 主机密钥信任和巡检记录 |
| `inspection-rules.json`（保存规则后生成） | 后续巡检任务使用的统一规则；与数据库分别保存 |
| `secrets/fernet.key` | 凭据加密密钥，首次启动创建，后续启动自动读取 |

备份前先停止后端服务，再复制数据库、已有的规则文件与对应密钥。迁移后以目标服务账号运行；已有加密凭据时，密钥丢失、损坏或不匹配会阻止启动，不会生成替代密钥。

Windows 使用运行账号的 ACL 保护密钥目录和文件；Linux 下目录权限为 `0700`、密钥文件为 `0600`。权限设置失败会阻止启动。数据库和报告包含运维信息，应限制访问。

## 开发与验证

### 项目结构

```text
autops/
├── backend/
│   ├── app/
│   │   ├── api/           # HTTP 接口与共用依赖
│   │   ├── core/          # 配置、存储、迁移与 SSH 基础能力
│   │   ├── repositories/  # 数据访问
│   │   ├── services/      # 连接测试、巡检执行与报告
│   │   └── schemas/       # 请求与响应模型
│   ├── runtime/           # 自动生成的数据库和密钥
│   └── tests/             # 后端测试
├── frontend/
│   └── src/
│       ├── api/           # 请求封装与业务接口
│       ├── components/    # 共用组件
│       ├── router/        # 页面路由
│       ├── styles/        # 样式
│       ├── types/         # TypeScript 类型
│       └── views/         # 资产与巡检页面
├── docs/                  # 开发规范与功能文档
├── AGENTS.md              # AI 编程助手工作约定
└── FILE_INDEX.md          # 完整文件用途索引
```

完整文件定位见 [仓库文件索引](FILE_INDEX.md)。根目录 `main.py` 和 `requirements*.txt` 保留启动与依赖安装的兼容入口；兼容启动命令为 `uvicorn main:app --reload`，兼容接口为 `/` 和 `/health`。

### 检查命令

```powershell
.\.venv\Scripts\python.exe -m pytest
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

`build` 已包含类型检查，产物位于 `frontend/dist/`。使用 `npm --prefix frontend run preview` 可预览构建产物；预览服务不提供开发代理，接口联通需要配置实际后端地址及对应 CORS 来源。

### 参与开发

修改前阅读 [Agent 工作约定](AGENTS.md)、[前端开发规范](docs/AI-前端开发约束规范.md)和[后端开发规范](docs/AI-后端开发约束规范.md)，按索引定位并阅读相关源码。复用现有实现，保持改动聚焦，并执行与修改相关的检查。

功能、配置或启动方式变化时同步更新文档。AI 生成代码须经人工审核，提交、推送与合并按授权执行。

## 部署边界

构建后由静态服务器提供 `frontend/dist/`，将 `/api` 反向代理至 FastAPI。Vue 使用 history 路由，静态服务器需将页面路由回退到 `index.html`。

SQLite 与后台任务队列当前只支持单后端实例、单 Uvicorn worker，请勿使用 `--workers` 或让多个实例共享数据库来扩容。

当前没有 hosts 批量导入、部署管理、Docker 管理或日志采集模块。巡检中的 Docker 服务状态检查仅检查服务状态。

## 许可证

当前仓库未提供许可证文件，尚未声明开源授权条款。
