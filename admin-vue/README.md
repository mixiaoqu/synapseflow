# admin-vue

`admin-vue` 是当前仓库中的 Vue 3 管理后台前端。当前代码已经接入登录、鉴权守卫、后台壳层和 6 个一级模块入口，一级模块页面暂时共用统一骨架页，后续再逐个替换为真实业务页面。

## 技术栈

- Vue 3
- Vue Router 4
- Pinia
- Vue Query
- Element Plus
- Tailwind CSS
- Axios
- Vite

## 本地启动

安装依赖：

```bash
cd admin-vue
pnpm install
```

启动开发环境：

```bash
cd admin-vue
pnpm dev
```

其他常用命令：

```bash
cd admin-vue
pnpm lint
pnpm typecheck
pnpm build
```

说明：

- `pnpm build` 在项目里是有效命令，但只有在明确需要验证生产构建时才建议执行。

## 环境变量

当前代码实际读取的前端环境变量如下：

- `VITE_API_BASE_URL`
  - 后端 API 根地址，默认回退到 `http://localhost:8000/api/v1`
- `VITE_API_TIMEOUT_MS`
  - HTTP 请求超时时间，单位毫秒，默认回退到 `15000`

## 当前页面结构

### 登录页

- 路径：`/login`
- 页面：[`src/modules/auth/pages/LoginPage.vue`](./src/modules/auth/pages/LoginPage.vue)
- 壳层：[`src/app/layouts/AuthLayout.vue`](./src/app/layouts/AuthLayout.vue)

### 后台壳层

- 主布局：[`src/app/layouts/AdminLayout.vue`](./src/app/layouts/AdminLayout.vue)
- 一级导航配置：[`src/app/navigation/admin-nav.ts`](./src/app/navigation/admin-nav.ts)
- 路由定义：[`src/router/index.ts`](./src/router/index.ts)

当前一级导航为：

- 控制台
- 知识库
- 项目
- 助手
- 组织
- 治理

## 当前路由事实

后台根路径 `/` 会重定向到 `/dashboard`。

当前已注册的后台一级路由有：

- `/dashboard`
- `/knowledge-bases`
- `/projects`
- `/assistants`
- `/organizations`
- `/governance`

这些页面当前都复用 [`src/modules/platform/pages/ModulePlaceholderPage.vue`](./src/modules/platform/pages/ModulePlaceholderPage.vue) 作为统一骨架，占位承载各模块后续的真实页面内容。

## 认证与请求流

### 鉴权状态

- Pinia Store：[`src/stores/auth.ts`](./src/stores/auth.ts)
- 路由守卫：[`src/app/guards/auth.ts`](./src/app/guards/auth.ts)
- Session 工具：[`src/shared/auth/session.ts`](./src/shared/auth/session.ts)

当前逻辑：

- 首次访问受保护页面时，路由守卫会先执行 `bootstrap()`
- 如果本地存在 token，前端会调用当前用户接口校验会话
- 未登录用户会被重定向到 `/login`
- 登录后会优先返回用户最初访问的后台地址
- 如果接口返回 `401`，本地会话会被立即清空

### HTTP 请求

- Axios 实例：[`src/shared/api/http.ts`](./src/shared/api/http.ts)
- API 配置：[`src/shared/api/config.ts`](./src/shared/api/config.ts)

当前逻辑：

- 请求发送前自动注入 `Authorization: Bearer <token>`
- 响应错误会先归一化，再返回给调用方处理
- `401` 会自动清空本地登录态

## 共享页面骨架

当前后台页面已经有一套共享骨架组件：

- 列表页骨架：[`src/shared/components/page/ResourceListPage.vue`](./src/shared/components/page/ResourceListPage.vue)
- 详情页骨架：[`src/shared/components/page/ResourceDetailPage.vue`](./src/shared/components/page/ResourceDetailPage.vue)
- 页面操作栏：[`src/shared/components/page/FilterToolbar.vue`](./src/shared/components/page/FilterToolbar.vue)

反馈组件包括：

- [`src/shared/components/feedback/AppLoading.vue`](./src/shared/components/feedback/AppLoading.vue)
- [`src/shared/components/feedback/AppEmpty.vue`](./src/shared/components/feedback/AppEmpty.vue)
- [`src/shared/components/feedback/AppError.vue`](./src/shared/components/feedback/AppError.vue)
- [`src/shared/components/feedback/AppForbidden.vue`](./src/shared/components/feedback/AppForbidden.vue)

## 当前样式约定

当前代码已经收敛为以下方式：

- Element Plus 负责表单、按钮、消息、标签等基础控件
- Tailwind 负责后台布局和页面骨架
- 全局样式入口在 [`src/styles/index.css`](./src/styles/index.css)，只保留基础样式与少量共享 token

如果继续新增后台页面，建议优先沿用这套分工，不再回到大块页面级 `scoped CSS` 的写法。

## 当前已实现与未实现

已由代码验证的事实：

- 登录页可用
- 路由守卫生效
- 后台壳层可用
- 6 个一级模块入口已注册
- 后台统一骨架页已接通

从当前代码可推断的意图：

- 后续会以共享骨架组件为基础逐步补齐各一级模块的真实业务页
- 知识库、项目、助手、组织、治理会沿用统一的后台框架继续扩展

当前未实现：

- 各一级模块的真实业务列表、详情、审核、配置页面
- 更细粒度的模块内二级导航与数据交互流程
