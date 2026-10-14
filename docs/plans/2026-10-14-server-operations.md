# 服务器运维迁移实施计划

目标：将原 server_ops 的主机名、软件包与仓库、防火墙、内核参数、系统优化、磁盘管理迁移为六个独立页面；本期不接 AI、不迁移 OpenSSL。

架构：沿用 Vue 3、Element Plus、FastAPI、SQLite、SQLAlchemy、Paramiko。页面经 API 层访问后端；后端分 Schema、Repository、Service、路由层。复用现有资产解析、SSH 信任及命令执行，不引入依赖。

## 已确认决策

- 页面优先；共用“读取现状→准备计划→人工确认→后台执行→结果核验→历史记录”。
- 一份计划对应一种操作，可选多台主机。确认绑定计划 ID 和明确的影响确认；执行前重新检查资产和远端状态。
- 执行记录逐步持久化。失败停止该主机后续步骤；连接或命令中断标记结果未知，不自动重试、不自动回滚。
- 非 root 使用明确选择的免密 sudo；不索取 sudo 密码，不自动切换权限。预检失败终止。
- 配置修改管理指定参数和专属配置；不整体覆盖 sysctl.conf。磁盘参数全部提前收集；禁止复用有分区、签名、挂载或系统用途的设备。
- 现有本地单实例使用边界不变；本期不新增认证系统。

## 实施任务

1. `backend/app/schemas/operations.py` 定义目录、读取、计划、确认、记录模型；`operation_models.py`、`core/migrations/operations.py`、`repositories/operations.py` 持久化计划和逐步骤结果。
2. `services/operation_commands/` 按职责定义六类固定操作，校验参数，生成预检、执行、核验命令。配置文件不接受任意路径，动态参数严格校验和 shell 转义。
3. `services/operations.py` 实现有界后台执行、主机互斥、重启中断标记、计划时效、快照复核；`api/v1/endpoints/operations.py` 提供目录、读取、准备、确认、分页历史和详情接口。在入口与存储注册生命周期和迁移。
4. `frontend/src/types/operations.ts`、`api/operations.ts`、共用工作台组件及六个独立页面，增加导航和路由。复用现有分页、错误反馈、工作区。
5. 使用隔离数据库和模拟 SSH 验证校验、确认防重、状态变化、失败停止、逐步记录和重启行为；执行现有后端测试与前端构建。未经授权不连接实际主机执行写操作。

## 统一接口契约

- `GET /api/v1/operations/catalog`：`{modules: [{id,title,actions:[{id,title,description,destructive,fields:[{key,label,kind,required,options?,default?}]}]}]}`。kind 为 text、textarea、number、boolean、select；options 为 label/value。
- `POST /api/v1/operations/inspect`：`{module,host_id,sudo}` → `{host_id,host_name,module,output}`。
- `POST /api/v1/operations/plans`：`{module,action,host_ids,params,sudo}` → 任务详情。
- `POST /api/v1/operations/tasks/{id}/confirm`：`{confirmation: id,impact_ack: true}` → 任务详情。计划参数不可在确认时修改。
- `GET /api/v1/operations/tasks?module=...&page=1&page_size=20` → `{items,total,page,page_size}`。
- `GET /api/v1/operations/tasks/{id}` → 任务详情。
- 任务详情：`{id,module,action,title,status,created_at,confirmed_at,completed_at,params,sudo,hosts:[{host_id,host_name,address,status,before,after,error,steps:[{title,status,stdout,stderr,exit_status}]}]}`。
- 任务状态 planned/queued/running/succeeded/failed/partial/unknown/interrupted/expired；主机状态 planned/queued/running/succeeded/failed/unknown/interrupted；步骤状态 pending/running/succeeded/failed/unknown。
- 未解除的 unknown 主机持久阻止后续写任务；`POST /tasks/{id}/hosts/{host_id}/resolve` 接收 confirmation、remote_stopped=true、note，人工带外核对后仅解除阻塞。主机响应增加 resolved_at、resolution_note，历史仍为 unknown。
- 请求错误沿用统一“系统异常”反馈；远端操作结果属于任务事实，详情展示经过限制的标准输出、错误输出和失败阶段，不回传凭据及内部异常堆栈。

## 验收

六个页面均能读取现状、填写明确参数、预览计划、确认执行和分页查看历史；破坏性操作明确展示影响。运行效果、类型、构建和后端测试如实记录；真实主机验证需在用户指定测试主机后进行。

## 实施边界补充

目标为具备 DNF 和对应工具的 RHEL 系主机，不新增包管理器兼容层。sysctl 支持数值及数值向量，先由内核校验应用再持久化；chrony 需已安装并保留原时间源。具体操作限制和失败语义见 `docs/server-operations.md`。

## 本地验证结果

- `python -m pytest backend/tests/test_operations.py -q`：87 项通过。覆盖隔离 HTTP/SQLite、模拟 SSH、全部 27 动作的 Bash 语法、独立 shell 服务移除保护、sysctl 失败停止、磁盘 fstab 前置条件和 chrony 同步核验。
- `python -m pytest backend/tests/test_assets.py -q`：28 项通过。
- `python -m pytest backend/tests/test_ssh_commands.py -q`：13 项通过。
- `python -m pytest backend/tests/test_inspection_tasks.py -q`：108 项通过。该文件单独运行约 127 秒，组合检查曾触及 120 秒上限，分开运行已完成。
- `npm --prefix frontend run build`：类型检查与生产构建通过；`git diff --check` 无格式错误。
- 既有 `test_analysis_diagnostics.py::test_section_validation_has_context_without_model_output` 四组参数均失败：纯巡检 finding 已直接组装报告，测试仍期待模型回复校验异常。相关生产代码与旧测试未在本次修改；全量后端测试未通过，不能视为全绿。
- 新增 `backend/tests/test_operations.py` 按现有仓库规则保留为本地忽略测试，未修改忽略规则、暂存或提交。
- README 按中文字符和英文词统计 605，允许模块及顺序核对通过。
- 未进行真实主机写操作或浏览器交互验收；未新增依赖，未提交、推送或修改开发规范。
