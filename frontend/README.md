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
