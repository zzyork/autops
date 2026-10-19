# AI 编程接入指南

## 结构与职责

本项目采用原生规则入口与 Agent Skills。`AGENTS.md` 强制完整阅读三份核心开发规范，并按任务范围执行工程治理、接口安全和测试交付补充规范；项目适配技能组织开发与审核步骤，外部技能提供技术参考。完整导航见 [工程治理与需求规范](AI-工程治理与需求规范.md)。外部内容不能覆盖用户要求、项目规范、已有接口契约或客户端权限。

| 位置 | 职责 |
| --- | --- |
| `AGENTS.md`、三份核心规范及按范围适用的补充规范 | 项目约束的权威来源 |
| `.agents/skills/autops-frontend/` | 前端源码定位、Vue 知识应用与验证 |
| `.agents/skills/autops-backend/` | 后端源码定位、FastAPI 知识应用与验证 |
| `.agents/skills/autops-review/` | 变更、契约、安全与修复验证审核 |
| `.agents/skills/vue/`、`fastapi/` | 含全部技能目录文件及许可的固定上游快照 |
| `.opencode/commands/` | OpenCode 规划与审核入口 |
| `.opencode/agents/autops-auditor.md` | 禁止编辑、Shell 与任务委派的只读审核 Agent |
| `docs/plans/` | 较大任务执行期间的行为、契约、实施与验收方案；完成后删除对应方案 |

接入的最终结构、来源与取舍统一维护在本指南；执行完成的方案不作为长期文档入口。本项目未因技能接入安装规则分发器、规格 CLI、流程插件、MCP 或额外 Lint 依赖；当前已有原生加载机制与任务文档，后续有实际需要再评估。

## 已采纳来源与审核记录

核对日期：2026-10-15。快照仅用于本项目的知识读取，不执行文中的安装、网络或运维示例。

| 技能 | 上游与固定提交 | 文件范围与许可 | 审核结果 |
| --- | --- | --- | --- |
| `vue` | [antfu/skills](https://github.com/antfu/skills/tree/feb0f3aba6566426f12230e7fc7a10d97c1293bb/skills/vue)，`feb0f3aba6566426f12230e7fc7a10d97c1293bb` | `SKILL.md`、`GENERATION.md`、3 份参考文件及根目录 `LICENSE.md`，共 6 份，MIT | 已完整阅读并核对上游 Git blob；无脚本、凭据访问或数据外传要求；存在下表所列不采纳示例 |
| `fastapi` | [fastapi/fastapi](https://github.com/fastapi/fastapi/tree/49a09a0d4e876b4e7d6d87fc049710263aaeaa7e/fastapi/.agents/skills/fastapi)，`49a09a0d4e876b4e7d6d87fc049710263aaeaa7e` | `SKILL.md`、6 份参考文件及根目录 `LICENSE`，共 8 份，MIT | 已完整阅读并核对上游 Git blob；无脚本、凭据访问或数据外传要求；工具与新版功能建议须按下表处理 |

Vue 技能为 Anthony Fu 维护的文档生成项目，不是 Vue 官方统一规范；`GENERATION.md` 中的 SHA 指生成所依据的文档，与本表的技能仓库提交不同。FastAPI 技能来自官方仓库，但快照并不保证所有示例适用于本项目固定版本。

三个 `autops-*` 技能由本项目编写，没有复制第三方技能正文。`autops-review` 采纳 [Trail of Bits 变更审核与验证](https://github.com/trailofbits/skills)的先理解上下文、检查差异、验证候选发现及修复回归思路；此次未安装其插件，也未宣称执行了其中的安全扫描。

格式与加载依据：[Agent Skills](https://agentskills.io/specification)、[OpenCode 技能](https://opencode.ai/docs/skills/)、[OpenCode 命令](https://opencode.ai/docs/commands/)、[Codex 技能](https://developers.openai.com/codex/build-skills)。

## 已知差异与不采纳内容

| 外部内容 | 本项目处理 |
| --- | --- |
| Vue 示例中的 `any`、组件直接 `fetch`、调试日志 | 使用明确类型或 `unknown`；通过项目 API 层与请求封装；不复制无必要日志 |
| Vue 示例中的移动端条件、外部动画库、通用视觉偏好 | 继续执行桌面范围、Element Plus、既有主题与组件；不自动增加依赖 |
| Vue 对 `shallowRef`、组件写法的偏好 | 按实际响应性和周边代码判断，不为统一风格重写既有组件 |
| FastAPI 对 SQLModel、Asyncer、uv、ty 及 CLI 的偏好 | 保留 SQLAlchemy、现有执行器、依赖管理及启动入口；不自动迁移 |
| FastAPI 新 SSE、前端托管、遥测等功能建议 | 先核对 `backend/requirements.txt`、已安装 API 和既有调用链；不自动启用、升级或替换现有协议 |
| 外部工具示例中的安装、提交、发布或自动审批步骤 | 不构成执行授权，继续按用户任务与项目工作约定处理 |

已知差异按本节明确选择执行，不逐次重复询问。尚未记录、会改变需求或契约的实质冲突，应按 `AGENTS.md` 说明并澄清后处理受影响部分。上游资料错误时可停止使用相关建议，不能据此悄悄更改项目要求。

## 使用方法

从仓库或其子目录启动支持项目 Agent Skills 的客户端。OpenCode 与 Codex 的文档均支持 `.agents/skills/<名称>/SKILL.md`；因此只保存一份技能，不复制到不同客户端目录，也不需要修改当前 `opencode.json` 的权限设置。

| 任务 | 加载技能 |
| --- | --- |
| 前端设计、实现、修复 | `autops-frontend`、`vue` |
| 后端设计、实现、修复 | `autops-backend`、`fastapi` |
| 跨端功能 | 前后端两组 |
| 完成代码修改或独立审核 | `autops-review`，并按范围读取前后端技能 |

自然语言示例：

```text
使用 autops-frontend 和 vue，按现有规范完善主机列表交互，先阅读现有实现。
使用 autops-backend 和 fastapi，分析并修复指定接口，保持既有响应契约。
使用 autops-review，只审核本次接口与调用方变更，报告证据和验证缺口。
```

OpenCode 可使用 `/autops-plan 需求描述` 与 `/autops-review 文件或功能范围`。规划命令使用内置计划模式；审核命令启动专用 `autops-auditor` 子 Agent，并显式拒绝编辑、Shell 与任务委派。审核入口不能运行 Git 或测试：有传入差异时核对差异，无差异时读取指定源码并说明覆盖限制。需要命令验证或修复时回到正常开发会话按授权执行。Codex 可通过 `$autops-frontend`、`$autops-backend`、`$autops-review` 明确选择技能；此处的 OpenCode Agent 权限不自动适用于 Codex。

每项任务中每个技能只加载一次；相互引用只补齐知识。独立审核不进入开发实施步骤，也不回调另一次审核；已授权实施后的审核仍可在原授权范围修复，专用只读入口除外。

不支持技能工具的客户端，按 `AGENTS.md` 直接读取对应 `SKILL.md`，继续读取任务相关的参考文件；这是人工指定读取方式，不代表客户端原生支持。不同客户端的规则优先级、技能发现和权限以其实际版本为准。

## 规格与验证

较大需求在 `docs/plans/YYYY-MM-DD-主题.md` 集中记录：

1. 目标、非目标、已确认行为与验收场景。
2. 现有实现、复用点、涉及文件与调用方。
3. 请求、响应、SSE 或下载契约，以及成功、失败、取消和未知状态。
4. 最小完整方案、必要复杂度、风险和需确认事项。
5. 实施步骤、验证命令及结果；实施后同步最终行为，未实施内容明确标注。

小改动在任务说明记录即可。规划入口不会自动授权业务实施；用户已要求实施时按范围继续，不重复增加审批。方案执行完成后，将需要长期保留的最终行为、契约或决策归入对应权威文档，删除对应方案；方案文件禁止加入 `FILE_INDEX.md` 等索引。

前端已有 `npm run typecheck` 与 `npm run build`（后者包含类型检查）；后端已有 pytest。各技能要求先核对脚本、依赖和测试，再选择相关检查。本次未增加 ESLint、Ruff、Vitest 或浏览器测试依赖。技能自评、文件结构和构建通过均不替代人工审核。

## 更新与加载验收

维护者升级技能时，应选定完整上游提交，比较技能目录及许可的全部变更，逐份阅读新增和修改文件，检查外传、凭据访问、脚本与依赖建议，核对固定项目版本，再更新快照、本指南和索引。保留上游原文，项目差异集中维护在本指南和 `autops-*` 技能，不自动跟踪 `main` 或 `master`。

修改后检查目录名与 `name` 一致、`description` 完整、名称不冲突、全部本地参考文件存在、许可证保留、原文 Git blob 与上游一致。新依赖及不可逆行为仍按项目约定取得授权。

接入本次新增的命令和技能后，退出并重新启动 OpenCode；Codex 若未发现新技能，也重新启动。随后让客户端列出当前项目的五个技能，并使用“只分析，不改代码”的前端与后端任务检查技能读取记录和规范来源。若列表缺失，检查实际版本、启动目录、全局同名技能及权限，不自动修改用户全局配置。

本次终端未发现 OpenCode 或 Codex 可执行命令，因此只完成文件结构、引用、上游快照和差异验证；客户端实际发现、模型触发和遵守效果仍须在重启后的会话核实。规则文件不能提供技术上的强制执行保证。
