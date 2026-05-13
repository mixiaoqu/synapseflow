# SynapseFlow Frontend

当前前端收口为两个正式产品入口：

- `/ask`：用户问答界面
- `/admin`：后台管理界面

## 开发

```bash
pnpm install
pnpm dev
```

默认访问地址：`http://localhost:3000`

## 当前目录结构

```text
frontend/
├── app/
│   ├── (auth)/login/
│   ├── (user)/ask/
│   └── (admin)/admin/
├── components/
├── features/
│   └── documents/
├── hooks/
└── lib/api/
```

## 主要页面

### 用户侧

- `app/(user)/ask/page.tsx`

### 后台侧

- `app/(admin)/admin/page.tsx`
- `app/(admin)/admin/documents/page.tsx`
- `app/(admin)/admin/assistants/page.tsx`
- `app/(admin)/admin/review/page.tsx`
- `app/(admin)/admin/sensitive-words/page.tsx`
- `app/(admin)/admin/teams/page.tsx`
- `app/(admin)/admin/users/page.tsx`

## 环境变量

在 `frontend/.env.local` 中至少配置：

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```
