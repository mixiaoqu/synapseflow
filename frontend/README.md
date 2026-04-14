# SynapseFlow Frontend

基于 Next.js 15 和 shadcn/ui 的前端应用。

## 开发

```bash
pnpm install
pnpm dev
```

访问 `http://localhost:3000`

## 页面结构

```text
app/
  (dashboard)/
    kb-chat/        # 普通用户知识库问答
    kb-curation/    # 管理员知识库治理
    revision/       # 文档修订
    prototype/      # 文档转原型
    documents/      # 文档管理
```

## 主要页面

1. `app/(dashboard)/kb-chat/page.tsx`
2. `app/(dashboard)/kb-curation/page.tsx`
3. `app/(dashboard)/revision/page.tsx`
4. `app/(dashboard)/prototype/page.tsx`

## 环境变量

创建 `.env.local`：

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```
