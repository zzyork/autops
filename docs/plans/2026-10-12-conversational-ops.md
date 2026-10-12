# 对话式 AI 运维实施方案

目标：将 autops 首页改为对话入口，用户自由配置模型，通过自然语言查询资产、确认并执行已有巡检，查看实际进度与结果。

架构：沿用 Vue 3、TypeScript、Element Plus、FastAPI、SQLAlchemy、SQLite 和 Fernet；新增模型适配层和 LangGraph 编排层。模型只选择已注册业务工具，执行继续由 InspectionManager 承担。会话、消息、工具计划持久化，模型连接和会话固定关联。

技术与依赖：新增 LangGraph（对话编排）和 HTTPX（有限超时模型 HTTP 请求）；沿用项目固定版本方式。无需独立 Dify/Open WebUI、向量数据库、前端组件库或全局状态库。

## 已确认的范围

- 配置多个模型连接：名称、协议（OpenAI 兼容或 Anthropic）、服务地址、模型 ID、API Key、默认连接。
- API Key 加密存储；响应仅返回 has_api_key，编辑空值保留旧密钥。允许无密钥的本地服务。
- 模型能力分别测试普通对话和真实工具调用；只有测试工具调用成功的连接开放运维工具。配置变更清除能力测试状态。测试失败明确记录，不自动切换模型。
- 新会话选择连接，已有会话固定连接；提供会话列表、历史、删除与流式消息。
- 工具提供资产分组与主机查询、巡检计划创建、关联任务进度和结果查询。查询输出只包含资产标识、名称、地址、分组、版本，不包含凭据。
- 巡检创建先展示真实主机范围与检查项，用户通过独立确认按钮提交。重复确认不得重复创建任务，确认时重新校验资产版本，保留现有 32 台限制。
- 对话中的任务卡片查询现有任务 API，复用巡检详情组件；实际完成状态与健康结论分别展示。
- 首页及模型配置页面复用既有控制台主题和布局。异常通过共用请求与反馈入口处理，加载失败不显示正常空态。

## 数据与接口契约

前缀 `/api/v1/ai`。

- `GET/POST /connections`，`PUT/DELETE /connections/{id}`：模型连接 CRUD。
- 连接输入：`name, protocol, base_url, model, api_key, is_default`；输出：`id, name, protocol, base_url, model, has_api_key, is_default, chat_status, tool_status`。能力状态为 `untested/passed/failed`。
- `POST /connections/{id}/test`：分别测试聊天和工具能力，返回更新后的连接；网络/协议测试不通过记录 failed，不返回厂商敏感原文。
- `GET/POST /sessions`：会话列表、创建（`connection_id`）；概要 `id, title, connection_id, created_at, updated_at`。
- `GET/DELETE /sessions/{id}`：详情、删除。详情增加 `messages` 和 `proposals`。
- 消息：`id, role(user/assistant), content, created_at, status(completed/failed/interrupted)`。服务端维护厂商工具消息历史，不接受客户端伪造历史；内部 in_flight 区分真正未完成调用与已失败调用。
- 巡检计划：`id, name, hosts[{id,version,name,address}], checks, status(pending/confirmed/cancelled), task_id`。
- `POST /sessions/{id}/messages`：输入 `{content}`，返回 SSE；事件 `token` 数据 `{text}`，`done` 数据 `{session}`，`error` 数据 `{}`。共享请求封装负责流读取、事件校验及错误转换。确认 plan 不由模型执行。
- `POST /sessions/{id}/proposals/{proposal_id}/decision`：输入 `{approve: boolean}`，返回更新的会话详情；批准复用巡检执行器，拒绝不执行。
- 同一会话禁止并发发送、确认、删除；记录消息调用的失败状态，重启中断不能伪装成功。厂商失败不生成备用答案。

## 文件与实施步骤

1. 后端新增 `ai_models.py`、`schemas/ai.py`、`repositories/ai.py`、`core/migrations/ai.py`，注册迁移并将模型密钥纳入启动解密验证。
2. 新增模型 HTTP 适配与测试服务、LangGraph 对话编排和工具服务，新增 `api/v1/endpoints/ai.py` 并注册路由及生命周期资源。
3. 前端新增 `types/ai.ts`、`api/ai.ts`，扩展统一 HTTP 封装支持 SSE、可配置超时；新增对话、计划/任务卡片、模型表单与配置页面。修改首页路由、侧栏和品牌链接。
4. 编写隔离数据库与模拟模型服务测试，覆盖密钥不回显、能力验证、会话隔离、未确认不执行、重复确认、主机版本变化、非法参数、厂商失败及流中断。
5. 更新使用文档与 FILE_INDEX；README 遵循允许的模块及 1000 字限制。
6. 执行 `.venv/Scripts/python.exe -m pytest`、`npm --prefix frontend run build`，复核两份规范的适用清单。没有真实模型凭据时说明真实模型联调未执行。

## 风险与执行边界

- 模型兼容性以指定端点和模型的能力测试为准，不能保证所有模型均支持工具调用。
- 用户配置的服务可以是内网地址；只接受 HTTP/HTTPS 地址，禁止 URL 内嵌凭据、查询和片段，不跟随重定向。提供者返回错误不向前端回显敏感内容。
- 模型会接收用户对话以及工具返回的资产信息和巡检结果，配置页面和使用文档说明其数据范围。
- 保留项目本地、单实例、单 worker 限制；目前没有多人身份认证和 RBAC，本次不虚构这类保障。
- 项目仅有主机分组，第一版将项目名称作为查找分组的线索，匹配歧义要求用户补充，不建立未经确认的新项目模型。
- 新表通过幂等迁移创建，不改写已有资产及巡检数据；用户已授权本方案范围内的新增存储与架构。
- 旧 nginx 安装模块位于 `E:/Codes/autodeploykit/middleware_ops/nginx_manager.py`，依赖 CLI 提示、RHEL dnf、编译及 sudo、下载失败本地上传等行为。后续单独将其迁移为受控安装任务并明确版本、权限、下载与服务变更策略；第一版不注册安装或任意 Shell 工具。

## 组件职责

- 对话页面：组织会话选择、消息发送与结果展示，状态保存在页面或对应组合函数；依赖 AI API、模型选择和任务组件。
- 计划卡片：输入计划及会话 ID，展示真实执行范围，输出确认/拒绝事件，可在对话历史复用。
- 任务卡片：输入任务 ID，读取并轮询已有巡检任务，展示进度、终态和详情，离开页面清理轮询。
- 模型表单：输入编辑连接，输出保存事件；密钥仅提交到后端，编辑不读取原文，可复用新增和编辑。

## 验收

- 未配置连接时明确引导配置；测试失败与空列表区分。
- 支持指定任意兼容端点和模型 ID，选择连接后完成多轮对话，刷新能恢复历史。
- 模型只通过真实资产查询生成计划，确认前没有 SSH 执行；确认后任务可查看，重复点击不重复执行。
- 模型/网络失败终止调用并恢复发送状态，不显示成功，不自动改用其他连接。
- 检查类型、输入边界、密钥与工具数据范围、并发与资源清理；不执行真实远程安装或巡检作为开发验证。

## 实施验证记录

- 后端固定新增 `httpx==0.28.1`、`langgraph==1.2.14`，已安装至项目虚拟环境。
- 完整 pytest：191 通过、1 跳过；其中 AI 测试 28 通过。跳过项为现有 Ed25519 PEM 表示条件测试。
- 前端生产构建及 TypeScript 检查通过，Git 空白检查通过。
- 额外覆盖两种上游流的终止标识、增量即时转发、断开清理、工具批次重放、默认连接切换、计划幂等、外键事务与后台投递失败。
- 测试文件 `backend/tests/test_ai.py` 按当前忽略约定保留为本地验证文件，未暂存或提交。
- 未配置真实模型端点和凭据，真实模型与真实 SSH 巡检联调未执行；浏览器视觉和交互验收未执行。
