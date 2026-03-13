# SynapseFlow Frontend

基于Next.js 15和shadcn/ui的前端应用

## 开发指南

### 安装依赖

```bash
pnpm install
```

### 启动开发服务器

```bash
pnpm dev
```

访问 http://localhost:3000

### 构建生产版本

```bash
npm run build
npm start
```

### 添加shadcn/ui组件

```bash
npx shadcn@latest add button
npx shadcn@latest add card
npx shadcn@latest add dialog
```

## 项目结构

```
app/
├── (auth)/          # 认证路由组
│   └── login/
├── (dashboard)/     # 主应用路由组
│   ├── qa/         # 迭代问答
│   ├── revision/   # 递归修订
│   └── prototype/  # 文档转原型
├── layout.tsx      # 根布局
└── page.tsx        # 首页

components/
├── ui/             # shadcn/ui组件
├── agents/         # 智能体相关组件
├── documents/      # 文档组件
└── layout/         # 布局组件

lib/
├── api/            # API客户端
├── utils.ts        # 工具函数
└── constants.ts    # 常量定义
```

## 三个场景页面

1. **问答页面**：`app/(dashboard)/qa/page.tsx`
2. **修订页面**：`app/(dashboard)/revision/page.tsx`
3. **原型页面**：`app/(dashboard)/prototype/page.tsx`

## 环境变量

创建 `.env.local` 文件：

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 样式定制

全局样式在 `app/globals.css` 中定义，使用CSS变量支持主题切换。
