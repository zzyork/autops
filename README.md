# autops

对话式 AI 运维控制台，使用 Vue 3、FastAPI 和 SQLite，支持自选模型、资产管理、SSH 测试与只读巡检。

## 功能亮点

- 首页对话、多轮历史、实时回复。
- 自定义 OpenAI 兼容或 Anthropic 模型连接，API Key 加密保存。
- AI 查询资产、生成巡检计划，用户确认后执行；展示进度与报告。
- 管理主机、分组、跳板机、SSH 密钥。

## 快速开始

安装依赖后，在两个 PowerShell 终端从仓库根目录启动：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
npm --prefix frontend run dev
```

打开前端地址，进入“模型配置”，保存并测试连接，再在首页选择模型创建会话。

## 安装说明

需要 Python 3.13、Node.js 20.19+ 或 22.12+。

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
npm --prefix frontend ci
```

## 使用示例

先登记主机并完成 SSH 指纹信任，输入“帮我巡检 production 分组的所有服务器”，核对计划后确认。单任务最多 32 台。当前尚未接入安装工具。

模型收到对话及必要资产和巡检结果；本项目当前适合本地单实例、单 worker 使用，尚无身份认证和多人权限控制。

## 配置选项

环境变量模板见 `backend/.env.example`、`frontend/.env.example`。运行数据默认位于 `backend/runtime/`，备份时停止服务并同时保存数据库、规则和加密密钥。

模型地址、能力验证、会话和数据边界见 [AI 对话说明](docs/ai-chat.md)，巡检口径见 [巡检说明](docs/inspections.md)。

## API 文档

后端启动后访问 `/docs`。AI 接口前缀为 `/api/v1/ai`。

## 贡献指南

开发前阅读 [工作约定](AGENTS.md)及两份开发规范，通过 [文件索引](FILE_INDEX.md)定位源码。

```powershell
.\.venv\Scripts\python.exe -m pytest
npm --prefix frontend run build
```

AI 生成代码需人工审核。

## 许可证

本仓库尚未声明开源授权条款。
