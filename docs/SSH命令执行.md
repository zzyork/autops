# SSH 命令执行工具库

SSH 远程执行由后端 Python 工具提供。单命令入口为 `backend/app/core/ssh_commands.py` 的 `run_command`，多步骤入口为 `backend/app/core/ssh_workflows.py` 的 `run_workflow`。现有巡检继续使用单命令入口。

## 调用方式与连接所有权

```python
from collections.abc import Callable

import paramiko

from backend.app.core.ssh_workflows import (
    CommandStep, WorkflowEvent, WorkflowResult, run_workflow,
)


def check_verified_host(
    client: paramiko.SSHClient,
    on_event: Callable[[WorkflowEvent], None],
) -> WorkflowResult:
    return run_workflow(
        client,
        [
            CommandStep(name="读取主机名", command="hostname"),
            CommandStep(name="检查服务", command="systemctl is-active nginx"),
        ],
        timeout_seconds=120,
        on_event=on_event,
    )
```

`client` 必须是调用方已完成目标身份校验的有效连接；业务沿用 `core/ssh.py` 的 `open_ssh_connection` 上下文及既有 SSH 资产、信任解析。工具不自行连接或关闭正常完成后的整个 SSHClient，每条命令的 Channel 由 `run_command` 释放。取消等待打开 Channel 的操作时，底层可能关闭该客户端以释放阻塞，因此同一连接不得与其他业务并发共用。

每步使用独立 Channel 和 Shell，同一流程复用传入连接。上一条命令的 `cd`、Shell 变量不会自动传入下一步。完整命令不按换行或分号拆分；复合命令及管道须自行传播正确退出状态。底层使用 `LC_ALL=C LANG=C bash -c`，不申请 PTY、提权或接受交互输入。

调用方负责业务授权、资产与服务器信任复核、连接生命周期、并发上限、排队、同主机互斥和结果保存/传输。工具为同步阻塞调用，异步业务接入使用项目已有的有界执行方式。调用一次执行一次，不提供跨调用去重或重启恢复；业务确认前不得因断连自动重调。

## 输入与返回值

`run_workflow(client, steps, timeout_seconds=900, *, on_event=None, cancel=None, secrets=())` 返回 `WorkflowResult`。全部输入在发出命令前校验，步骤及允许退出码、秘密值复制为快照，回调修改原列表不影响后续执行。参数不合法抛出 `ValueError`。

| 输入 | 契约 |
| --- | --- |
| `steps` | 1–20 个 `CommandStep`，按给定顺序执行 |
| `CommandStep.name` | 去除首尾空白后 1–100 字符 |
| `CommandStep.command` | 非空、不含 NUL，最多 8192 字符；保留原始脚本文本 |
| `CommandStep.success_exit_codes` | 1–16 个不重复的 0–255 严格整数，默认 `(0,)`，不接受布尔值 |
| `CommandStep.timeout_seconds` | 有限正数，最多 600 秒，默认 30 秒，可用小数 |
| 流程 `timeout_seconds` | 有限正数，最多 1800 秒，默认 900 秒；从输入校验完成后开始计时 |
| `on_event` | 可选同步回调，接收 `WorkflowEvent` |
| `cancel` | 可选 `threading.Event`，触发后停止本地采集和后续执行 |
| `secrets` | 可选已知秘密字符串序列，由调用方显式提供；多行值同时过滤完整值和长度大于 3 的各行 |

`WorkflowResult` 包含 `status`、有序 `steps: tuple[StepResult, ...]` 和可空 `error_code`。每个 `StepResult` 包含名称、状态、可空退出码与错误码、过滤后的 stdout/stderr；不复制命令、资产或连接配置。命令输入、结果输出与输出事件文本不进入这些数据类的 `repr`。

## 成功、失败与未知结果

stderr 有内容不等于失败。只有取得有效退出码、满足该步允许集合且事件回调成功返回后，才开始下一步；业务验收可以作为后续检查步骤。

| 状态 | 含义 |
| --- | --- |
| `succeeded` | 步骤退出码满足约定，或所有步骤成功 |
| `failed` | 退出码不符、派发前失败，或已知退出码但超时/超限/中断等要求未满足 |
| `unknown` | 命令可能已执行，但未取得可信退出结果 |
| `skipped` | 仅步骤使用；前序失败或结果未知后，后续步骤未执行 |

有效退出码原值保留；`-1` 或缺失退出码不能成功。命令尝试派发之后发生超时、断连、超限或中断且没有有效退出码时，该步为 `unknown`；确认未派发则为 `failed`。已确认允许退出码后连接断开，该步保留成功；还有后续步骤时整体为 `failed/connection`，后续跳过，最后一步已确认成功则流程可以成功。超时、输出超限、中断及内部采集错误即使携带有效退出码，也停止流程。

稳定错误码包括 `exit_status`、`timeout`、`connection`、`output_limit`、`internal`、`unknown`、`interrupted`。回调异常直接向调用方传播，停止后续步骤，不再次调用已失败的回调，也不伪造完整结果或完成事件。调用方可用已接受的事件确认处理进度；事件传输失败不证明远端命令未发生。

取消、超时或关闭通道不证明远端进程已经退出，也不证明此前变更已撤销。业务负责验收、备份与恢复设计；工具不自动重试、恢复执行、重新连接或补偿。

## 实时事件

`WorkflowEvent` 在执行调用线程按顺序同步交付。stdout 与 stderr 各自保持字节接收顺序，不承诺两者原始写入时序；UTF-8 使用增量解码，跨块字符完整解码，非法字节替换为替代字符。

| `kind` | 有效字段与含义 |
| --- | --- |
| `step_start` | `step_index`，从 0 开始，表示开始处理该步；不证明已派发 |
| `output` | `step_index`、`stream`（`stdout` 或 `stderr`）、过滤后的增量 `text` |
| `step_end` | `step_index`、`status`、可空 `exit_status`、可空 `error_code` |
| `workflow_end` | 整体 `status` 和可空 `error_code`，`step_index` 为 `None` |

其余未适用字段为空或默认空文本。跳过的步骤不产生开始/结束事件，其结果从返回值读取。每步输出事件按流拼接后与返回的 stdout/stderr 一致；失败时保留已采集的部分输出。步骤结束不代表整个流程成功，以流程结果判断。回调应及时返回；同步回调的阻塞与其外部资源由调用方控制。

## 输出、安全与兼容边界

单步原始 stdout/stderr 合计最多 256 KiB，过滤后的 UTF-8 文本也受相同上限约束，最多 20 步。超限保留限额内部分输出并以 `output_limit` 停止，不会截断后继续执行。已知秘密跨分块匹配后替换为 `[REDACTED]`，非打印控制字符转为替代字符；命令包含这些已知秘密时，在执行任何步骤前拒绝。该过滤只覆盖调用方提供的值，业务仍须控制凭据来源和对外字段。

工具不自动读取凭据、不记录命令或输出日志、不写数据库。调用方不得将秘密写入命令或日志；向其他调用端传输时继续按项目权限及纯文本/JSON 编码边界处理结果，不将输出当作 HTML 执行。

2026-10-20 按“工具库”目标撤下误加的独立“SSH 执行”页面、`/api/v1/ssh/executions` 管理 API/SSE、后台任务管理器及专属模型/迁移。实时能力通过 Python 回调交付，业务所需的传输方式由业务调用方接入。既有 SSH 连接测试、公钥确认和巡检入口保留。

应用不再创建、查询或更新旧 `ssh_executions`、`ssh_execution_steps`、`ssh_execution_events`、`ssh_execution_requests` 表。本次不删除这些表及其中数据，不提供清理迁移；既有源码可从 Git 历史恢复。历史管理平台测试保留为本地历史用例，引用已撤下模块的用例不再适用于当前工具库，不能把未运行的历史验证算作本次通过。

## 验证边界

本地验证使用虚构数据、模拟 SSH Channel/连接及隔离 SQLite，覆盖顺序、允许退出码、失败/未知停止、超时/取消、部分输出、回调失败、参数快照、秘密跨块过滤和输出超限，并回归既有单命令、连接及巡检调用。测试与验证脚本按项目政策仅本地保存，不随 Git 交付，干净克隆不保证具备这些用例。

2026-10-20 实际本地检查共 123 项通过、1 项跳过：

| 检查范围 | 实际结果 |
| --- | --- |
| `test_ssh_workflow_library.py` | 48 项通过，包含审核后补齐的回调/取消信号参数校验 |
| `test_ssh_commands.py` | 21 项通过 |
| `test_ssh_transport.py` | 23 项通过，1 项因 Ed25519 无传统 PEM 表示而跳过 |
| `test_ssh_library_integration.py`、`test_ssh_connection_status.py` | 22 项通过；验证旧入口撤下、现有入口可用、新库不建旧表及重复初始化保留虚构历史数据 |
| `test_inspection_tasks.py` 的本次影响范围 | 9 项通过、100 项未选择，覆盖正常采集、日志结果、连接/检查失败、重启中断与关闭 |
| 前端 `npm run build` | 通过，包含 `vue-tsc --noEmit` 和 Vite 构建 |

pytest 使用项目 `.venv` 的 Python，在根目录对上述文件分组运行；涉及应用装配的进程先将 `Settings.model_config['env_file']` 设为 `None`，避免读取真实 `.env`。巡检使用 `-k 'catalog_completed_critical_and_report_api or log_result_is_in_task_and_report or multi_host_partial_and_connection_failure or independent_check_failure_and_disconnect or restart_interrupts_only_unfinished_checks or shutdown_rejects_new_work_and_releases_workers'` 选择范围。本地测试均受 Git 忽略，不暂存或提交；未运行全仓历史管理测试。

独立只读审核提出的输入契约缺口已修复并复核。前次管理页面及 SSE 的模拟验证不作为当前工具库证据。本次未做浏览器交互验收、未连接真实 SSH 主机；真实传输及远端进程行为仍须在获准环境验收，AI 审核不能替代人工审核。
