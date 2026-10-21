---
name: autops-frontend
description: autops 项目前端开发流程。修改或设计 Vue、TypeScript、Vite、Element Plus 页面、组件、样式、路由、请求和前端状态时使用；跨端功能与后端技能共同使用。
---

# autops 前端实施

本文路径均相对于仓库根目录。从 `AGENTS.md` 和 `FILE_INDEX.md` 定位项目，先完整阅读三份开发规范，再读取相关源码。本技能组织实施步骤，不代替规范正文。

每项任务只加载本技能一次；与后端技能交叉引用时补齐尚未读取的内容即可。只做设计或独立审核时，仅采用相关分析与检查步骤，不执行代码实施和末尾审核流程。

## 读取与设计

1. 加载 `vue` 技能，按任务读取其 `references/` 中相关文件；直接读文件时从 `.agents/skills/vue/SKILL.md` 开始。先阅读 `docs/AI-编程接入指南.md` 的已知差异，按项目依赖版本核对 API。
2. 阅读 `frontend/package.json`、目标页面、相邻实现和实际调用链。接口经过 `frontend/src/api/` 与 `frontend/src/api/http.ts`，类型位于 `frontend/src/types/`；不要在页面照搬外部示例中的直接请求。
3. 检索可复用组件、组合式函数与样式；涉及反馈、测试状态、分页、展开详情或布局时，优先检查 `feedback.ts`、`TestStatus.vue`、`ListPagination.vue`、`DisclosurePanel.vue`、`ConsoleLayout.vue` 及其调用方。
4. 说明目标、涉及文件、数据与状态归属、复用点、用户可见变化和风险；有跨端字段或状态变化时，同时加载 `autops-backend`，检查 Schema、实际响应、前端 API 与类型及全部已知消费者。

## 实施边界

- 以项目规范和现有 Vue 3 + TypeScript + Vite + Element Plus 实现为准。上游的 `any`、直接 `fetch`、额外组件库、动画库和移动端示例不采纳；不据此引入 Pinia、Axios、Nuxt、SSR 或更换包管理器。
- 按数据变化深度选择响应式 API。不能只因上游偏好 `shallowRef` 就改坏深层更新；不为满足风格偏好重写既有组件。
- 沿用请求错误与取消的明确类型、当前有效请求判断和共用反馈入口；分别维护列表与保存状态，失败不进入成功流程。具体文案、位置与时长读取前端规范和实现，不在此复制常量。
- 按用户任务选择可见内容，保留必要状态和业务证据；复用现有主题变量与桌面布局，不照搬外部示例的调试输出、品牌和断点。

## 验证与交付

1. 从 `frontend/` 执行 `npm run typecheck`、`npm run build`；先核对脚本，构建当前包含类型检查时可执行构建一次并记录其包含的检查。未安装依赖或检查失败时如实报告。
2. 实施代码修改后，加载尚未读取的 `autops-review` 并执行一次审核；独立审核中不再回调。交付说明行为变化、组件输入输出及复用范围、验证结果和未执行项；仅在职责或结构变化时更新索引。
