# autops

基于 Vue 3、FastAPI、SQLite 的对话式运维控制台。

## 功能亮点

- 模型实时对话、历史会话和加密 API Key。
- 主机、分组、跳板机、SSH 密钥管理。
- AI 查询资产、生成待确认巡检计划及报告。
- 主机名、软件包、仓库、防火墙、内核、系统及磁盘运维，提供预检、确认和实时输出。

## 快速开始

在两个 PowerShell 终端启动：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
npm --prefix frontend run dev
```

配置并测试模型后创建会话。

## 安装说明

需要 Python 3.13、Node.js 20.19+ 或 22.12+。

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
npm --prefix frontend ci
```

## 使用示例

登记主机后输入“巡检 production 分组”，确认后执行，单任务最多 32 台。未信任或变化的 SSH 指纹须明确确认，取消则停止。

主机行“更多 → 服务器运维”提供写操作，AI 暂不调用。系统识别支持具有 DNF 的 RHEL 系与 openEuler，仍须通过工具、配置和权限预检；不支持常规 CentOS 7。

对话及巡检数据会发送给模型。仅限单 worker；无用户认证和多人权限。

## 配置选项

配置见前后端 `.env.example`。备份前停服，保存完整 `backend/runtime/`。

## API 文档

后端 `/docs` 提供接口文档。

## 贡献指南

阅读 [工作约定](AGENTS.md)和三份开发规范；代码须人工审核。测试仅本地验证，不纳入 Git。

## 许可证

本仓库尚未声明开源授权条款。
