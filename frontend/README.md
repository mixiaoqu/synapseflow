# SynapseFlow Frontend

当前前端已经收口为两个正式产品入口：

- `/ask`：用户问答界面
- `/admin`：后台管理界面

旧的实验性页面和路由已经移除，不再作为当前前端结构的一部分。

## 开发

```bash
pnpm install
pnpm dev
```

默认访问地址：`http://localhost:3000`

## 当前目录结构

```text
frontend/
├─ app/
│  ├─ (auth)/login/                登录页
│  ├─ (user)/ask/                  用户问答页
│  └─ (admin)/admin/               后台管理页及其子页面
├─ components/
│  ├─ ask/                         问答页专属组件
│  ├─ team-scope/                  跨 ask/admin 共用的团队作用域能力
│  └─ teams/                       团队切换等 UI 组件
├─ features/
│  └─ documents/                   文档管理特性页实现
├─ hooks/                          页面与业务 hooks
└─ lib/api/                        前端 API 封装
```

## 主要页面

### 用户侧
- `app/(user)/ask/page.tsx`

### 后台侧
- `app/(admin)/admin/page.tsx`
- `app/(admin)/admin/documents/page.tsx`
- `app/(admin)/admin/knowledge-bases/page.tsx`
- `app/(admin)/admin/assistants/page.tsx`
- `app/(admin)/admin/review/page.tsx`
- `app/(admin)/admin/qa-quality/page.tsx`
- `app/(admin)/admin/sensitive-words/page.tsx`
- `app/(admin)/admin/teams/page.tsx`
- `app/(admin)/admin/users/page.tsx`

## 开发约束

- 新页面默认围绕 `/ask` 或 `/admin` 组织，不再引入实验性平行入口。
- 可复用业务实现优先放在 `features/`、`hooks/`、`lib/` 或共享组件目录下。
- 问答专属组件放在 `components/ask/`，跨页面共享能力放在更中性的目录中。

## 环境变量

在 `frontend/.env.local` 中至少配置：

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```
## 前端实现说明 (嵌入式助理 & 后台项目管理)

本次更新完成了两部分主要的前端开发任务，并使用了 Mock 数据供展示：

1. **统一嵌入式 AI 助手 UI (`/embed/assistant`)**:
   - `features/embed/components/EmbedAssistantChat.tsx`: 高度自适应、采用毛玻璃效果 (Glassmorphism) 与 Framer Motion 动画的纯前端极简聊天 UI。支持窄屏下的侧边抽屉，并且完全去除了后台的冗余导航。
   - `features/embed/hooks/useEmbeddedAssistant.ts`: 对应的纯前端状态机 hook，支持自动回复流式打字动画、回退并自动伸缩输入框。
   - `app/embed/assistant/layout.tsx` & `page.tsx`: 全新的独立路由。

2. **管理后台项目与应用管理 UI (`/admin/projects`)**:
   - `app/(admin)/admin/projects/page.tsx`: 项目列表视图，包含搜索与表格展示，以及启用/停用等模拟操作。
   - `app/(admin)/admin/projects/[id]/page.tsx`: 具体项目下属的应用管理配置页面。包含选择绑定的助手，以及提供了一键复制代码的功能，以便开发者复制 `iframe` 与 `token` 获取的对接说明。

3. **问答质检 (Logs Filter) 更新**:
   - 扩展了 `AskLogListFilters` 接口与 UI 组件（`app/(admin)/admin/qa-quality/page.tsx` 和 `lib/api/endpoints/ask.ts`），增加了对 `project_id`, `project_app_id`, 和 `external_user_id` 的支持，使得管理员能够按照项目维度检索聊天历史日志。

*所有 UI 均通过了类型检查和构建 `pnpm exec next build --no-lint`。*
