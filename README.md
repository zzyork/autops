# autops

Linux 主机资产与只读巡检控制台。

## 功能亮点 / 截图

资产、分组、跳板机与 SSH 密钥管理；连接测试；四类巡检；报告导出。

## 快速开始

安装后，在仓库根目录的两个 PowerShell 终端分别执行：

```powershell
py -3.13 -m uvicorn backend.app.main:app
```

```powershell
npm --prefix frontend run dev
```

访问 http://127.0.0.1:5173 。

## 安装说明

需 Python 3.13、Node.js 20.19+（20.x）或 22.12+；仓库根目录执行：

```powershell
py -3.13 -m pip install -r requirements.txt
npm --prefix frontend ci
```

## 使用示例

添加主机与凭据，测试连接并核对指纹，再创建巡检任务、查看记录并导出报告。

## 许可证

尚未提供许可证。
