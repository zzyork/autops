# 操作记录系统实施方案

> 执行指引：后续使用 executing-plans 技能按任务执行，以项目两份开发规范为强制依据；提交、推送和合并遵循用户明确授权。

日期：2026-10-14。状态：已同意的设计所对应的实施方案，经现行前后端规范重新优化；尚未实施业务代码或迁移。

**目标：** 记录当前 WebUI 的业务操作、操作者、目标、字段变化和真实结果，提供操作查询，为后续用户系统预留可信身份与授权接口。

**架构：** 在现有 SQLite 中追加业务事件，与数据库业务变更共事务；异步任务持久化事件关联，再恢复发起上下文。对外采用独立摘要/详情模型，前端按业务操作聚合展示，不直接返回或渲染事件实体。

**技术栈：** 复用 FastAPI、Pydantic、SQLAlchemy、SQLite、pytest、Vue 3、TypeScript、Element Plus、Vite；不引入新依赖、全局 Store、消息队列或独立日志平台。

## 1. 依据、范围与影响

强制依据为 [AI 前端开发约束规范](../AI-前端开发约束规范.md)和 [AI 后端开发约束规范](../AI-后端开发约束规范.md)。本轮已完整重读，重点落实前端第 9.1 节、后端第 3.1 节，以及两份规范的分层、类型、安全和验收清单。本文件独立包含执行所需契约，不依赖当前已不存在的上一版设计文档。

已确认的实施基线：数据库变更和成功事件同事务，写入失败使该事务失败；文件配置继续使用现有文件与原子替换，保留无法确认结果的窗口；首期不自动清理记录、不迁移配置到数据库、不建设用户系统。范围包括资产增改删、AI 会话/消息/计划决策、SSH 测试及身份确认、巡检/汇报/下载和模型配置。普通列表读取、轮询、翻页、搜索、切换工作区及 SSE token 不记录。

影响范围是现有业务提交点、后台终态/恢复、新增只读查询及独立页面。不得扩大为权限体系改造、通用异常格式重写、SSH 信任行为改变或远端失败补偿。当前源码变化较多，执行前重新检查实际文件，不覆盖其他未提交修改。

现状和风险：

- 项目尚无 Web 用户认证，SSH 用户名不是 Web 操作者；后台线程独立创建 Session。
- 主机有版本并发控制；成功记录必须覆盖 flush 与 commit 的冲突边界。
- 新建对话按钮只清空页面，首条发送才调用创建会话；创建成功和消息失败是两项不同事实。
- 外部 SSH/模型执行不能和本地数据库原子提交，断流不等于业务失败。
- 巡检规则和功能模型配置是文件；可能已生效却未成功写入审计终态，不得假称已回滚。
- 数据长期增长，首期只做只读容量检查；SQLite 文件管理员仍可修改记录，不能宣称防篡改或不可抵赖。

网络依据：参考 [OWASP 日志指南](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)的身份、对象和敏感信息边界，[Kubernetes 审计](https://kubernetes.io/docs/tasks/debug/debug-cluster/audit/)的阶段记录，[GitHub 审计查询](https://docs.github.com/en/organizations/keeping-your-organization-secure/managing-security-settings-for-your-organization/reviewing-the-audit-log-for-your-organization)的动作编码和筛选。此前检索日期为 2026-10-14；这些资料不授权改变项目响应或错误契约。

## 2. 规范落实与优化决定

| 规范要求 | 本方案的落实方式 | 验收证据 |
| --- | --- | --- |
| 前端 1.2、后端一：先理解与复用 | 先核对入口矩阵，读取实际源码与公共组件；新增文件前查找可复用能力 | 实际入口、调用方和提交点记录 |
| 后端二：路由/Schema/Service/Repository 分层 | 路由只收发；事件策略、脱敏和授权在 Service；SQL 在 Repository；模型定义独立 | 无复杂 SQL 或整套业务集中在新接口中 |
| 前端六、七：请求分层与明确类型 | 页面→API→http；响应从 unknown 校验后使用，不使用 any | 类型检查和不合法响应测试 |
| 前端 9.1、后端 3.1：最小必要信息/响应 | 存储、响应和展示分别定义白名单与用途；列表不带详情，不返回原始事件 | 字段消费表、实际 JSON 与页面审核 |
| 前端附录：测试状态统一 | SSH/模型测试历史用 TestStatus 和受控映射；普通操作结果用既有语义标签 | tooltip、键盘聚焦、历史状态验证 |
| 前端四、五：组件契约/局部状态 | 独立页面、筛选/表格/详情按职责拆分；明确用途、输入输出、依赖和复用范围 | 组件说明和状态归属审核 |
| 前端错误反馈、后端五 | 当前请求失败只通过共用反馈显示“系统异常”；历史结果与请求错误分开 | 并发合并、失效请求、失败空态测试 |
| 后端四、六：迁移、校验与秘密保护 | 幂等迁移、参数化查询、字段/载荷限长；成功共事务；凭据和原文禁止入审计 | 旧库演练、故障注入、敏感值检查 |
| 两份规范的修改/验证流程 | 按里程碑小步修改，先针对性验证再集成；人工审核后部署 | 真实运行记录、未执行项明确列出 |

## 3. 内部记录契约

### 3.1 事件与状态

event.id、operation_id 和 request_id 均由服务端生成 UUID；request_id 每 HTTP 请求唯一。短数据库操作只有 finished，异步/外部 I/O 操作 accepted→finished；唯一约束为 (operation_id, phase)，phase 首期仅 accepted/finished。

accepted 的 outcome 为 accepted；finished 为 succeeded/failed/denied/interrupted/unknown/partial/awaiting_confirmation。无 finished 的列表状态为 pending_completion，中文“尚未确认完成”；它只表示还没有终态，不能断言执行器仍活跃。SSH awaiting_trust 是本次测试结束、待信任确认，不能一直显示进行中。后续确认生成新操作，不修改旧测试事实。

保持同一操作的 action、主要对象、发起上下文一致；终态 actor 可为 system/service。事件唯一键不能代替业务幂等或并发状态认领，重复终态必须先检查实际状态转换，不捕获全部冲突后静默忽略。

action 使用稳定的对象.动作编码：host/host_group/jump_host/ssh_key.create/update/delete；ai_session.create/delete、ai_message.send、ai_proposal.confirm/reject；ssh_test.submit、ssh_identity.check、ssh_trust.confirm；inspection.create/delete/export、inspection_report.generate、inspection_rules.update；model_connection.create/update/delete/test、feature_models.update。ssh_trust.auto_accept 仅接入实际存在的自动信任写入，不为审计新增自动信任业务。

### 3.2 事件内部字段

| 字段组 | 记录内容与用途 |
| --- | --- |
| 标识与版本 | id、schema_version、operation_id、request_id、parent_event_id；关联、去重、兼容 |
| 时间与结果 | occurred_at、recorded_at、phase、outcome、duration_ms；真实顺序和耗时 |
| 身份 | actor_type/id/name_snapshot、initiator_type/id/name_snapshot；实际执行者与发起者 |
| 动作和对象 | action、resource_type/id/name_snapshot、版本前后值、受控相关对象；追溯被删除对象 |
| 变化与摘要 | 有类型的 changes、逐动作 metadata 模型、受控 error_code；区别字段变化与失败事实 |

ActorContext 是只读 Schema，actor_type∈user/unauthenticated/system/service。当前明确返回 unauthenticated、id=NULL；不信任 X-User-ID、客户端名称或 Authorization 中未经验证的声明。改名/停用/删除不改写历史快照；旧未认证记录不回填给新管理员。

event Schema 定义枚举组合、UUID、UTC 时间、长度和 UTF-8 载荷上限。上限按已有业务字段和最大目标数校准，超限须在副作用前拒绝，不能静默截掉关键事实。审计不级联引用可删除业务或用户行。

精简决定：首期不存 User-Agent、IP、浏览器来源标签或客户端 interaction_id，没有当前消费用途不修改 http/CORS 增加交互头。request_id 仅用于服务端日志排查；如输出 X-Request-ID，先核对现有 CORS，无前端消费者时不加 expose_headers。后续需要这些信息时单独说明用途和隐私边界。

### 3.3 脱敏和差异

- 按 action 白名单构造，不序列化完整 ORM、请求体、响应体、headers 或异常。
- 主机仅记录名称、地址、端口、远端用户名、分组和资产关联等必要字段；备注仅 changed，凭据仅 credential_changed，不能记录密码、密文、密钥或密码摘要。
- 对话仅 session/message/model ID、字符数和结果；禁止消息正文、AI 回答、工具输入输出、由提示词截取的会话标题。名称使用“AI 对话”加短 ID。
- 模型地址仅“地址已变更”或经允许的协议/主机，不记录用户信息、查询参数和 fragment；主/备用标识切换需记录受影响连接的标识差异。
- SSH 记录指纹变更和授权决策，不记录公私钥原文；巡检记录计数与任务引用，不复制日志或命令输出。
- 同值保存 changes=[]、changed=false。批量目标复用业务任务明细，通过关联 ID 获取，不塞入巨型 JSON。
- 测试动作 metadata 保存该次实际测试的状态快照：SSH 的 queued/running/awaiting_trust/succeeded/failed/interrupted、模型对话和工具能力各自的受控状态。HTTP/业务请求 succeeded 不等于能力 passed，列表不能读取当前模型或最新 SSH 测试来覆盖旧记录；处理中需要的排队/运行状态仅从同 operation 的已关联业务记录投影，不改写 accepted 历史。

## 4. 最小必要查询与页面契约

### 4.1 请求与响应

新增只读接口 GET /api/v1/activities、GET /api/v1/activities/{operation_id}、GET /api/v1/activity-actions。每个接口使用明确 response_model，查询输入用 Schema/依赖校验，SQL 使用参数。不得新增统一响应包装或替换现有错误格式。

列表参数为 page≥1、page_size∈{10,20,50}、带时区 from/to、action、result、resource_type/id。无时间输入时为 [now-7 天,now)，仅 from 时 to=now，仅 to 时 from=to-7 天，两端都给则原样使用；所有路径均校验 from<to，无效区间返回真实校验错误，不悄悄改写显式输入。一次请求只取一个 UTC now。个人授权作用于计数、列表和详情全部查询。actor 筛选契约可预留在服务层，当前无用户系统时不展示无实际选择值的用户筛选。

| 对外模型/字段 | 当前消费用途 | 不返回的内部内容 |
| --- | --- | --- |
| ActivityPage：items、total、page、page_size | 表格与真实服务端分页 | 全表计数细节、数据库信息 |
| ActivitySummary：operation_id、occurred_at、action、resource、actor、result | 唯一行、详情请求、时间/动作/对象/操作者/结果列 | events、changes、metadata、请求 ID、完整上下文 |
| 测试动作专用 test_display：status、description | status 使用现有 TestStatus 类型；description 为共用映射生成的中文 tooltip/可访问名称 | 非测试动作不返回该字段，不暴露原能力协议或错误原文 |
| resource：type、id、name | 识别对象，详情再判断是否可跳转 | 连接凭据、资产完整配置 |
| actor：type、display_name | 显示实际发起者；系统自主操作如实显示系统 | 用户实体、角色列表或认证载荷 |
| ActivityDetail：summary、finished_at、changes、timeline、related_resources | 核对修改前后、完成时间、确认与执行关系、合法业务跳转 | 原始 ActivityEvent、schema_version、recorded_at、内部阶段编码和原始异常 |
| changes：字段标签、类型、前后值或 changed 标记 | 可读差异；缺失/null/已更换各有明确类型 | 自由备注、秘密值 |
| timeline：时间、业务步骤标签、操作者、结果 | 仅异步/跨人决策等有意义的生命周期 | request_id、parent_event_id、调用栈、重复单步骤摘要 |
| related_resources：业务类型、名称、受控引用 | 主对象外的关联任务/消息等定位 | 任意 URL、未授权对象详细信息 |
| ActionDefinition：action、module、label | 筛选与统一动作中文 | 验证策略、内部白名单和未来动作 |

actor 列显示原始发起者，详情有意义时才显示后台执行者/确认者；不同人创建和确认应保留独立记录。状态、关联 ID 和分页即使不直接展示，也仅在明确的程序消费需要时返回。列表/详情字段由 Service 授权过滤和投影后构造，前端隐藏不代替后端过滤。

列表 SQL 选择 accepted 或没有 accepted 的单 finished 为 origin，左连接唯一 finished，按 origin 时间与 operation_id 倒序；筛选终态在聚合投影后执行，total 计操作数而非事件行数。避免 Python 全表聚合和逐行查询关联对象。offset 分页在并发插入时可能移动，不宣称快照分页。

详情不直接打包 events 数组：按业务目录转换可用 timeline，仅返回允许的差异和相关对象。将失败事实表达为历史“失败/拒绝/待确认/未知结果”，不输出原始异常、内部 error_code 或针对当前请求错误的处理建议。关联不可用统一不提供跳转，除非后端有权限且明确确认对象已删除，否则不泄露存在性。

测试动作的摘要/详情使用判别联合模型，只在对应 action 返回 test_display；status 来自该次测试快照的映射，不从通用 result 推断。模型能力需要对话和工具两项都 passed 才返回 passed，进行中优先 pending、失败 failed、待确认/中断 warning，其余按既有状态规则；没有准确状态的历史记录使用 unavailable 并说明“历史测试状态不可用”，不能默认通过。description 文案和映射只维护一处，后端共用目录生成语义、前端消费 type/status/description 并复用适用的展示工具，不分别维护两套相同文案。

实体身份边界：当前 SQLite 整数资产 ID 可能复用。首期整数 ID 资源仅作为历史标识展示/筛选，不按“当前表里有同 ID”直接跳转主机、分组、跳板机或密钥；对象筛选语义明确为“该 ID 的历史记录”，不宣称属于当前资产实例。UUID 业务任务/会话的关联仅在确认标识不复用且授权允许时提供业务跳转。若后续增加整数资产的精确实例跳转，须先制定不可复用实例标识和迁移，不用名称相同推断同一对象，也不能只靠前端隐藏错链。

### 4.2 页面信息和组件契约

新增 /activities 独立页面和导航，复用现有布局/工作区。按“面包屑、紧凑标题、工具栏、表格”组织，无装饰统计或系统说明卡片。时间、动作、对象、操作者、结果保持可见；变化与关联详情按需展示。原始 ID、请求 ID、JSON、协议术语和后台调试过程不在普通界面展示。

| 组件 | 用途、输入与输出 | 依赖与复用 |
| --- | --- | --- |
| ActivitiesView.vue | 组织列表/详情流程；路由与用户筛选输入；独立 loading/loaded、请求序号、页码和选中项 | activities API、既有布局/分页/feedback；专用页面，无全局 Store |
| ActivityFilters.vue | 时间/模块动作/结果筛选；输入目录、条件、可用状态；输出类型化 submit/reset | Element Plus；仅本模块复用，未认证时不虚构用户下拉 |
| ActivityTable.vue | 显示摘要；输入 items、加载可用状态；输出 open-detail(operation_id) | ElTable、activityDisplay、TestStatus；列表展示可复用 |
| ActivityDetail.vue | 展示必要差异及业务时间线；输入已授权详情；输出关闭/合法业务引用选择 | DisclosurePanel、现有语义组件；可在对象历史入口复用，不直接 HTTP |
| activityDisplay.ts | 动作与普通结果文案映射、测试结果到共用状态类型映射 | 复用同类 sshTestDisplay 和 TestStatus 类型，不自建色板或测试图标 |

仅独立管理功能单独路由；首期详情留在当前页面，行内用 DisclosurePanel/既有按钮显示“展开操作详情/收起操作详情”，不新增详情页或改 workspace 核心机制。加载/失败由页面管理，成功详情只传给展示组件，失败时不渲染正常空详情。

SSH 测试和模型能力测试历史结果必须使用 TestStatus.vue、types/testStatus.ts 及适用的已有映射；失败、排队、中断、待确认区别由中文 tooltip/可访问名称说明，不复制错误原文或改为自绘标签。其他操作结果采用既有语义标签；非测试动作不套用测试图标。

请求层将异常转换为既有 HttpError，业务 API 将新增响应视为 unknown 并校验 required 字段/枚举/数组/分页再返回明确类型；不重写通用 request<T> 或引入新错误类。页面 catch(error) 调用 showRequestError(error)，兼容当前 RequestCancelledError，失效请求不弹消息。对当前 http.ts 的 SSH 身份处理保持既有契约，不扩展或移除其流程。

取消边界需要局部修正现有封装：sendRequest 之后 request 的 response.json() 读取/解析异常，若调用方 options.signal 已主动 aborted 则抛已有 RequestCancelledError，否则仍抛 HttpError，超时信号不当作主动取消。新增活动 API 传递调用方 signal；切换筛选/关闭详情/卸载先使请求序号失效再 abort，防止取消晚到更新状态。页面在成功/catch/finally 均检查该请求序号与存活标志；真正网络、读取、JSON 和响应校验失败仍提示系统异常。此次不顺带改写 SSE/blob 请求，既有消费者应回归以保证局部 JSON 封装修正兼容。

列表/目录/详情状态分别管理：目录失败阻止依赖目录的操作，禁止空数组默认值伪造加载成功；列表失败不渲染“暂无数据”，详情失败不标记列表失败。只有当前有效请求更新状态，finally 恢复对应 loading。筛选输入保留，重试成功恢复；失败不继续导航或成功流程，不持久重复展示“系统异常”。

分页使用 ListPagination，数量/筛选变化重置第一页。独立导航、宽表内部滚动、1440px 桌面验收；正文 13px、标题 18px、模块间距 16px、控件间距 8px，颜色与尺寸复用现有变量/样式。折叠必须具备紧邻文字的箭头、按钮语义、Enter/Space、aria-expanded/controls、唯一容器 ID、焦点返回与收起后无隐藏 Tab 项；无必要内容不造展开入口。

## 5. 事务、异步与用户兼容

### 5.1 事务协议

1. 短数据库变更：读安全旧快照→业务变更→flush 获得 ID/版本→追加 finished→同 Session commit。flush 和 commit 的 IntegrityError/StaleDataError 都使用原冲突映射，不能出现成功事件却变更失败。
2. Repository 的审计 append 方法不 commit；由实际业务事务所有者提交。新增脱敏/事件构建在 Service，不向既有路由塞复杂审计逻辑；必要时抽取局部业务 Service，避免无关分层重构。
3. 失败：业务 Session rollback/释放后，再以短独立事务写 finished/failed 或 denied；不能在持有 SQLite 写锁时另开失败写入会话。失败记录再次写入失败明确记安全错误类型和关联 ID，不设备用数据库、不重发业务。
4. 一个请求可包含多个操作，按 operation_id 跟踪，而非一个 request 级布尔值。目录化路由元数据在校验前可识别 action；422 仅记录已校验对象或未知对象，不读 exc.body/input，不按错误文案判断失败类别。
5. 已 accepted 的异步动作由持久业务状态更新终态，通用异常处理不能抢写终态；业务成功提交后响应丢失仍为成功，另记录安全交付故障，不能改写业务结果。
6. 异步认领与 accepted 同事务；终态转换与 finished 同事务，按 generation/版本/状态条件更新命中数认定首次转换；锁/唯一键均不作为远端命令幂等保障。

使用依赖注入统一 ActorContext/OperationContext 和 Session。SQLAlchemy 同步访问留在同步路由/现有线程池，不放到 async 中间件内阻塞事件循环；ASGI 中间件仅产生请求关联，不消费 SSE 或正文。保留原 HTTP 状态码、错误 JSON、SSE 事件及下载内容契约，不将审计内部字段塞入业务响应。

### 5.2 持久关联迁移

| 模型 | 新增可空字段 | 后台用途 |
| --- | --- | --- |
| AIMessage | activity_operation_id | 用户消息接受、完成和恢复 |
| AIProposal | source_activity_operation_id | 实际产生计划的消息来源，确认后仍可追溯 |
| ConnectionTest | activity_operation_id | 测试终态与信任关联 |
| IdentityChallengeRecord | activity_operation_id | 独立身份探测的来源 |
| InspectionTask | activity_operation_id | 巡检汇总、自动汇报发起关系 |
| InspectionAIReport | activity_operation_id | 当前 generation，重新生成使用新操作 |

主体快照在 origin 事件保存，线程读取 origin 构造只读上下文，不把 Request/Session 跨线程传递。不重复给全部 Host/AISession 增加身份字段。旧行 NULL 明确是接入前数据：原恢复流程照常，不补造事件；新行要求关联却找不到 origin 时是完整性故障，不能退回默认用户。

迁移顺序：原业务迁移→migrate_activities 建表/索引及补实际表的可空列→create_all→管理器恢复。沿用 BEGIN IMMEDIATE/inspect/checkfirst，无网络或远端 I/O，空库、旧库、重复启动均验证。

### 5.3 未知结果与恢复

文件配置在原配置协调锁内校验/准备白名单载荷→短事务 accepted→已有原子替换→短事务 finished。SQLite 写事务不跨文件/网络等待。确认替换前失败为 failed，无法确认替换结果或替换后审计提交失败不伪造回滚；启动扫描补 finished/unknown，显示“结果待核对”，不根据当前值相同倒推成功、不自动恢复旧配置。

各管理器先复用已有未完任务恢复，再扫描没有任务行的未完外部动作：身份探测、模型测试中断为 interrupted；文件写入窗口为 unknown。自动 AI 汇报独立于巡检终态，恢复巡检不自动新增汇报行为。

生成中的 AI 汇报可能在终态巡检任务删除时被级联删除。删除事务先读取 generation/operation ID，若未结束则追加 finished/interrupted（内部原因 resource_deleted），再删除业务行并写删除事件，同事务提交后才 cancel 内存任务。worker 条件更新零行不追加迟到终态；若 worker 先完成保留其结果。删除 rollback 不先取消执行。

### 5.4 未来用户系统

当前解析为明确未认证模式；以后替换当前主体依赖，稳定 user ID+名称快照契约不变。认证失败拒绝受保护操作，不降为未认证继续。活动查询预留 read_self/read_all/read_sensitive 策略，在 Service 和 Repository 条件中强制执行，测试可覆盖双用户依赖替换，但不得把它宣称为实际认证已上线。

事件表示执行事实，不能代替会话 owner 或主机权限。用户系统阶段单独增加业务归属、校验对象/字段权限和跳转范围；停用、删除不级联清理历史，旧未认证不归新管理员。组织隔离需另行统一业务 scope 迁移，首期不虚构 tenant 默认值。

## 6. 执行任务与文件

### 任务 0：实际入口和基线

读取 FILE_INDEX、规范、git diff、实际路由及业务代码，登记方法/路径/action/主要对象/事务所有者/恢复点/载荷白名单/调用方/测试。确认未索引的 ssh_identities.py 等现存文件，不重复创建。复核当前自动信任真实路径，有则接入实际 save_trust 事务，无则标记业务未实现而非缺少日志。

检查已有脚本、依赖、pytest 配置及测试文件；新增测试与本地文件重名时先读再复用，不覆盖。不修改规则文件，不提交临时测试或生成产物。完成条件为全部实际业务入口有明确接入或排除理由。

### 任务 1：基础模型、目录和迁移

新增 backend/app/activity_models.py、schemas/activities.py、services/activity_catalog.py、services/activities.py、repositories/activities.py、core/migrations/activities.py。修改 core/storage.py、ai_models.py、connection_models.py、inspection_models.py。

按第 3 节实现类型/唯一键/索引/脱敏，按第 5.2 节幂等补列。services/activities 负责构建和政策，repository 仅数据访问，不独立提交。首期索引覆盖 origin 时间、action、对象、operation/request ID；用户索引结合主体查询契约，不为每个 JSON 建索引。

验证：本地 test_activity_storage.py，空库/旧库升级两次、非法状态、同操作重复终态、秘密哨兵值、业务对象删除后记录留存。迁移失败不接收业务流量。

### 任务 2：请求与失败协调

新增 api/activity_context.py、core/activity_http.py；修改 api/dependencies.py、main.py 及目录化路由接入。ASGI 生成 request ID，依赖提供主体和操作上下文；按第 5.1 节处理校验、业务异常、系统异常、已提交与未提交。

验证：本地 test_activity_requests.py，422/404/409/500、先 rollback 后写失败、伪造身份、并发上下文、一个请求多个操作、SSE 和响应失败不覆盖已提交终态。日志只留受控类型和关联 ID。

### 任务 3：资产短事务

修改 endpoints/hosts.py、host_groups.py、jump_hosts.py、ssh_keys.py，复用 credentials.py；需要复用资产审计策略时放在局部 services/activity_assets.py。保留原密码语义、主机版本、密钥引用/分组删除限制，前后快照和成功事件共事务。

验证：复用 test_assets.py，加本地 test_activity_assets.py；新增、改名/改组/改凭据、同值、旧版本冲突、引用冲突、删除，注入审计写入失败确认变更回滚。不得借接入重写全部资产接口。

### 任务 4：AI 对话与计划

修改 repositories/ai.py、services/ai_chat.py、endpoints/ai.py。create_session/delete 共事务；add_user 保存操作 ID+accepted；complete/finish_failure/interrupt_unfinished 同状态转换写终态。保留会话锁、模型验证、流取消；不追加消息/assistant 正文到审计。

complete 创建 proposal 同事务保存 source_activity_operation_id；decide 关联实际来源消息事件和实际确认者，与创建巡检任务、原 before_commit=link 保持同事务，不覆盖回调。重复相同决策不重造成功；历史来源 NULL 不按最新消息猜用户。

验证：本地 test_activity_ai.py，创建后发送失败、SSE 200 后失败、提交后断流、中断恢复、同会话多条消息分别提出计划、不同人确认、重复确认、会话删除后的来源追溯。模型使用模拟，无需改 ChatView/http 增加交互 ID。

### 任务 5：SSH 测试与信任

修改 services/ssh_connections.py、ssh_identities.py、ssh_trust.py、repositories/ssh_connections.py 和对应 endpoint。start 测试+accepted、_run 终态+finished、interrupt_tests/调度失败闭合。awaiting_trust 终态为待确认；trust_test_key/trust_identity 都记录独立确认并关联 test/challenge。

check_identity 网络前 accepted，挑战/结果同事务 finished；已受信任的 rollback 返回分支也通过短事务闭合。save_trust 不自行 commit；调用方只在一个明确落点写事件。auto_accept 仅在真实存在的信任新增事务接入，保持原策略。

验证：本地 test_activity_ssh.py，身份探测、待确认、两种信任入口、过期/快照变化拒绝、并发确认、恢复及写入失败。实际支持自动信任时才验证新增一次、已信任不重复新增。前端测试历史映射不得新画图标。

### 任务 6：巡检、AI 汇报和下载

修改 services/inspection_tasks.py、inspection_analysis.py、repositories/inspections.py、inspection_analysis.py、endpoints/inspections.py。create_task 与 accepted/关联同事务；summarize_task 按实际状态转换追加唯一终态；未调度/关闭/恢复共用转换规则。

report claim 生成独立 generation 操作，手动取当前主体、自动继承巡检发起者并关联巡检终态；finish 根据 generation/状态命中转换。保留自动回调在巡检 commit 后运行、不在恢复时自动生成汇报。生成中删除按第 5.3 节处理。

Markdown/ZIP 只在内容构建成功后返回前记录 export/succeeded，代表服务端提供内容，不证明浏览器保存文件；不改变原文件/流式契约。业务证据仍通过原报告接口按权限保留，不以审计精简删除诊断必需数据。

验证：复用 test_inspection_tasks.py，加本地 test_activity_inspections.py；并发多主机仅一个终态、部分结果、恢复、手动/自动归因、generation 竞争、生成中删除/完成竞态、删除 rollback、报告导出失败和实际下载内容边界。

### 任务 7：模型与文件配置

修改 repositories/ai.py、endpoints/ai.py、services/ai_feature_models.py、inspection_rules.py、endpoints/inspections.py。连接增改删共事务并记录切换主/备用造成的关联变化；test_connection 外部测试前 accepted，版本复核后结果/finished 共事务，旧配置测试不能证明新配置。

文件配置按第 5.3 节，不改变缺失默认配置的已有明确语义、不新增失败默认值或备用源。复用 feature config_guard，巡检规则按实际并发需要增加仅覆盖该配置流程的锁，禁止跨 I/O 持 SQLite 写锁。

验证：本地 test_activity_config.py，同值/并发、替换前故障、替换后审计失败、重启 unknown、主备用关联、敏感地址和凭据哨兵。真实呈现可能请求失败但配置已生效。

### 任务 8：查询 API 与最小必要投影

新增 api/v1/endpoints/activities.py，修改 api/v1/router.py；完善 activities Schema/Service/Repository。按第 4.1 节显式选择列、聚合分页、详情投影和权限，不返回完整实体。

验证：本地 test_activity_queries.py，阶段聚合计数、单失败、无终态、待确认、同时间排序、仅 from/仅 to/完整时间/非法区间、筛选/越界页、双主体权限替换、敏感字段过滤、整数 ID 删除后复用不产生错链。覆盖 HTTP 测试操作成功但模型能力失败、历史快照不受当前配置影响、queued/running/中断和状态不可用，断言 test_display 的合法状态/中文语义。验证实际 JSON 的允许字段及未知字段不泄露，不只比较内部对象。

### 任务 9：WebUI

新增 frontend/src/types/activities.ts、api/activities.ts、views/ActivitiesView.vue、components/ActivityFilters.vue、ActivityTable.vue、ActivityDetail.vue、activityDisplay.ts、styles/activities.css。修改 router/index.ts 和 AssetsLayout.vue，并对 api/http.ts 的 JSON 读取主动取消分支做上述局部修正；复用 workspace，不新增全局状态或请求封装。

实施顺序为数据流→组件契约→现有样式，按第 4.2 节完成状态、最小信息、分页与折叠。接口 unknown 校验位于业务 API，校验失败抛原 HttpError；同样不可吞错返回空列表。前端不加删除/清空/导出审计按钮，不铺原始事件 JSON。

验证：既有 typecheck/build；有浏览器条件时 1440px 检查加载/失败/空数据/筛选、10/20/50、长名称/差异、键盘和折叠、请求失效/主动取消（包括响应头已到而 JSON 体尚未读完）、超时/真实解析错误仍提示、共用错误合并、测试历史 tooltip/聚焦及工作区切换。不新增移动断点或假定存在 Lint/UI 测试框架。

### 任务 10：集成、部署和文档

新增 docs/activity-records.md，记录实际入口覆盖、使用、容量和未认证边界；更新 FILE_INDEX 和相关已存在文档的必要说明。README 非必要不修改，修改须遵守模块顺序与 1000 字要求，不恢复与任务无关的已删除文档。

按入口矩阵完成相关/完整回归；隔离库约 10 万操作数据，EXPLAIN QUERY PLAN/分页耗时记录实际环境，验证无全表 Python 聚合或资源 N+1，不虚报硬件无关延迟指标。只读检查 COUNT、时间范围、page_count×page_size，首期不新增无用户用途的统计 UI/API、清理任务或 VACUUM。

部署前停止单实例、排空任务，备份整个运行目录含数据库/配置/加密密钥，副本上演练幂等迁移；正式启动迁移完毕再管理器恢复。失败停止流量，保留失败后副本，回退整套一致备份，不单独回退库而保留新配置。完成后人工审核，未经授权不提交/推送/合并。

## 7. 里程碑、检查命令与完成条件

| 里程碑 | 任务 | 完成条件 |
| --- | --- | --- |
| M0 基础设施 | 0–2 | 入口/字段消费表、旧库迁移、脱敏/失败上下文可验证 |
| M1 资产与对话 | 3–4 | 原业务契约不破坏，同事务与计划来源测试通过 |
| M2 后台与配置 | 5–7 | 所有已接入操作有真实终态，未知/删除/恢复边界验证 |
| M3 查询与界面 | 8–9 | 实际响应最小且受控，页面必要信息和规范验收通过 |
| M4 全量交付 | 10 | 全部实际入口覆盖、回归/容量/迁移演练和人工审核 |

按主线顺序执行；契约稳定后查询/UI 可与其他业务接入并行，同文件/迁移/事务入口顺序协调。只完成主机和对话不得称为全系统交付。每个任务记录文件、实际命令/结果、规范条款证据及未完成项，不把计划当测试结论。

后续执行命令如下，本轮未运行；先确认现有 .venv、依赖和测试文件，不擅自安装新工具。新增本地测试按仓库忽略约定不暂存或提交，现有跟踪测试的修改按任务授权处理。

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_activity_storage.py backend/tests/test_activity_requests.py backend/tests/test_activity_assets.py -q
.\.venv\Scripts\python.exe -m pytest backend/tests/test_activity_ai.py backend/tests/test_activity_ssh.py backend/tests/test_activity_inspections.py backend/tests/test_activity_config.py backend/tests/test_activity_queries.py -q
.\.venv\Scripts\python.exe -m pytest
npm --prefix frontend run typecheck
npm --prefix frontend run build
git diff --check
```

build 当前包含 typecheck，完整构建时不需重复独立类型检查；独立 typecheck 供小步开发使用。没有已配置 Lint 脚本不得宣称通过；没有浏览器或真实 SSH/模型条件则明确仅模拟验证。检查正常、异常、权限/边界和实际 JSON/SSE/下载，不编写重复实现的无价值测试。被忽略的本地用例只能作为本次验证证据，不能称为已纳入持续回归；需要长期保留时再按授权明确跟踪方式。

最终审核清单：

- [ ] 原入口/调用方、响应状态和危险确认契约完整；没有无关架构或规范文件修改。
- [ ] route/Schema/Service/Repository 职责清楚，类型明确、字段白名单、SQL 参数化、迁移同步。
- [ ] 内部留存字段有追溯用途，对外字段有当前程序消费者，页面内容有用户用途；无秘密/原始异常/冗余调试信息。
- [ ] 短操作共事务、异步身份持久化、实际状态认领、恢复/删除竞态和配置未知结果边界可验证。
- [ ] 局部状态和统一 API/请求/feedback 复用；失败不伪装空数据，失效/取消请求不错误更新或提示。
- [ ] 所有新列表提供真实 10/20/50 分页，测试历史复用 TestStatus，折叠/焦点/对比度/桌面滚动合规。
- [ ] 已执行相关及集成检查并记录真实结果，未执行项明确；代码经人工审核，部署和 Git 操作在授权范围内。

## 8. 本轮文档修订与未执行项

当前工作区缺少上一轮方案文件，本次在 docs/plans 重新落盘并补充索引。相较此前方案：增加逐条规范映射、最小响应与展示消费表；取消没有现阶段用途的 IP/User-Agent/交互头等字段；明确测试历史复用、组件完整契约、未知响应校验及现有请求取消；保留已同意的事务、异步、未来用户身份和恢复设计。

本轮只优化文档；未实施业务代码、迁移、认证、测试或构建。后续若需偏离上述已确认架构/失败策略、调整规范或增加其他兜底，必须先说明具体影响并按授权确认，不以已有代码代替规范依据。
