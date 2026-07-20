# SynapseFlow Agent 业务系统接入指南

本文面向需要把 SynapseFlow Agent 接入现有 Web 业务系统的研发团队。接入后：

- 业务前端通过 CDN Loader 打开 Web Component Widget；
- 业务后端继续负责用户身份、登录状态和最终业务权限；
- SynapseFlow 负责短期凭证、Agent 会话、模型、知识库和工具编排；
- 业务系统可按需通过 MCP 向 Agent 开放受控业务能力。

第一版不需要安装 npm SDK，不需要新增业务用户体系，也不能把 Client Secret 暴露给浏览器。

## 1. 接入步骤总览

### 基础聊天：必须实现

1. SynapseFlow 管理员创建并启用 ProjectApp。
2. 管理员为 ProjectApp 开通业务接入凭证并配置允许的 Origin。
3. 业务后端实现一个同源 Bootstrap 接口。
4. 业务前端加载 CDN Loader，并提供自己的入口按钮。
5. 路由变化、退出登录和切换身份时正确管理 Widget 生命周期。
6. 配置 CORS、HTTPS、反向代理并完成验收。

完成以上步骤后，业务系统即可使用 Agent 聊天和知识库能力。

### 业务工具：按需实现

只有 Agent 需要查询或操作业务数据时，才需要：

1. 业务方提供 MCP Server。
2. MCP Server 暴露白名单业务工具。
3. 业务系统在每次调用时重新执行最终业务授权。
4. SynapseFlow 管理员同步、启用并向 ProjectApp 授权工具集。

## 2. 架构与责任边界

```text
业务页面
  -> CDN Loader / Web Component
  -> 业务后端 Bootstrap
  -> SynapseFlow /integration/bootstrap
  -> 短期 Widget Token
  -> SynapseFlow Agent
  -> （按需）业务 MCP Server
  -> 业务授权与业务用例
```

| 参与方 | 负责内容 | 不负责内容 |
| --- | --- | --- |
| 业务前端 | 入口展示、页面提示上下文、Widget 生命周期 | 用户鉴权、权限判断、Client Secret、模型调用 |
| 业务后端 | 登录态、可信身份和业务范围、Bootstrap、最终业务授权 | Agent 会话、Widget 版本加载、模型编排 |
| SynapseFlow | 短期 Token、Widget、Agent、知识库、工具发现、编排和调用审计 | 替代业务系统判断最终数据权限 |
| 业务 MCP Server | MCP 协议、参数边界、业务授权入口、调用业务用例 | 信任浏览器或模型提供的身份和业务范围 |

必须遵守：

- Client Secret 只能保存在业务后端。
- 浏览器只调用业务系统自己的同源 Bootstrap。
- 用户、租户、组织、门店等可信范围只能由业务后端生成。
- 页面 Context 只是提示信息，不能作为权限依据。
- MCP 工具参数中的用户或业务范围不可信，不能覆盖可信上下文。

## 3. SynapseFlow 管理员准备

在 SynapseFlow 管理端：

1. 创建或选择产品和项目。
2. 创建 ProjectApp，绑定知识库和默认助手。
3. 启用 ProjectApp，配置精确 Widget 版本，例如 `1.0.0`。
4. 在“业务接入”中填写业务页面允许的 Origin。
5. 生成 Client ID 和 Client Secret。

Client Secret 只在签发或重置时显示一次，应立即保存到业务后端密钥配置。

Origin 必须包含协议、域名和端口，例如：

```text
https://admin.example.com
http://localhost:8080
```

不要填写路径，不要使用 `*`。

业务方基础配置示例：

```text
AGENT_API_BASE_URL=https://agent.example.com/api/v1
AGENT_LOADER_URL=https://agent.example.com/agent-static/loader/v1/loader.js
AGENT_CLIENT_ID=<Client ID>
AGENT_CLIENT_SECRET=<Client Secret>
```

不同环境必须使用不同凭证。Secret 不得进入前端环境变量、构建产物或日志。

## 4. 业务后端 Bootstrap

### 4.1 提供同源接口

业务后端提供一个 POST 接口，例如：

```text
POST /api/agent/bootstrap
```

该接口必须：

1. 使用业务系统现有登录态鉴权。
2. 执行必要的 CSRF、Origin、限流和账号状态检查。
3. 从服务端会话或鉴权结果取得可信用户和业务范围。
4. 使用服务端 Client ID/Secret 调用 SynapseFlow。
5. 校验上游响应并返回标准 Bootstrap 结构。

Loader 发出的请求为：

```http
POST /api/agent/bootstrap
Content-Type: application/json
X-Requested-With: EnterpriseAgentLoader

{}
```

不要从浏览器请求体读取用户 ID、租户、门店或权限列表。

### 4.2 调用 SynapseFlow

```http
POST {AGENT_API_BASE_URL}/integration/bootstrap
Authorization: Basic base64(AGENT_CLIENT_ID:AGENT_CLIENT_SECRET)
Content-Type: application/json
```

请求体：

```json
{
  "principal": {
    "external_user_id": "user_001",
    "display_name": "张三"
  },
  "scope": {
    "tenant_id": "tenant_001",
    "store_id": "store_001"
  },
  "initial_page_type": "dashboard"
}
```

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `principal.external_user_id` | 是 | 业务系统内稳定且不可复用的用户标识 |
| `principal.display_name` | 否 | 仅用于展示，不参与鉴权 |
| `scope` | 否 | 业务后端确认的租户、组织、门店等可信范围 |
| `initial_page_type` | 否 | 初次打开时的页面类型提示 |

`scope` 最多 4096 字节、嵌套不超过 3 层。只传工具真正需要的最小范围，不传完整用户对象、角色详情或敏感资料。

### 4.3 返回浏览器

业务 Bootstrap 返回以下顶层结构：

```json
{
  "access_token": "short-lived-widget-token",
  "token_type": "Bearer",
  "expires_in": 900,
  "api_base_url": "https://agent.example.com/api/v1",
  "widget": {
    "version": "1.0.0",
    "protocol_version": "1"
  }
}
```

不要增加额外的 `data` 包装层。标准 Loader 直接读取这些顶层字段。

推荐错误语义：

| 状态码 | 场景 |
| --- | --- |
| `401` | 用户未登录或会话失效 |
| `403` | 用户被禁用或无权使用 Agent |
| `429` | 调用过于频繁 |
| `502` | SynapseFlow 返回异常响应 |
| `504` | 调用 SynapseFlow 超时 |

不要向浏览器返回 Secret、上游响应原文或内部堆栈。

框架无关伪代码：

```text
POST /api/agent/bootstrap:
  session = authenticate_existing_business_session(request)
  assert session.user_is_active
  assert session.can_use_agent

  principal = build_principal_from_session(session)
  scope = resolve_trusted_business_scope(session)

  result = POST AGENT_API_BASE_URL + "/integration/bootstrap"
    BasicAuth(AGENT_CLIENT_ID, AGENT_CLIENT_SECRET)
    JSON({ principal, scope, initial_page_type })
    timeout(5-10 seconds)

  validate result
  return result
```

## 5. 业务前端接入

### 5.1 加载 Loader

```html
<script
  src="https://agent.example.com/agent-static/loader/v1/loader.js"
  data-bootstrap-endpoint="/api/agent/bootstrap"
  defer
></script>
```

- `data-bootstrap-endpoint` 必须与业务页面同源。
- 同一页面只能初始化一次 Loader。
- 可以动态插入脚本，但应统一封装在一个业务 Loader 适配模块中。

### 5.2 打开 Agent

```js
await window.EnterpriseAgent.open({
  context: {
    schema_version: 1,
    page_type: "order_detail",
    route_name: "OrderDetail",
    route_path: "/orders/10001",
    entity_type: "order",
    entity_id: "10001",
    entity_name: "订单 10001",
    attributes: {
      page_title: "订单详情"
    }
  }
})
```

Context 支持 `page_type`、路由信息、当前实体和非敏感属性。它不能包含登录 Token、Cookie、密钥、权限结论、完整用户对象或敏感业务数据。

### 5.3 生命周期

```js
EnterpriseAgent.open({ context })
EnterpriseAgent.close()
EnterpriseAgent.setContext(context)
EnterpriseAgent.destroy()
EnterpriseAgent.on(event, listener)
```

事件包括 `ready`、`open`、`close`、`error`、`destroy`。

业务前端必须：

- 路由变化时调用 `setContext()`；
- 退出登录时调用 `destroy()`；
- 切换账号、租户、组织或门店时先销毁，再由新会话重新打开；
- 不自行保存 Widget Access Token；
- 让 Widget 通过业务 Bootstrap 自动刷新短期 Token。

## 6. 按需接入业务 MCP 工具

只使用聊天和知识库时，可以跳过本节。

### 6.1 MCP Server 最小协议

业务方提供一个 SynapseFlow 后端可访问的 HTTP 地址，例如：

```text
POST https://business-internal.example.com/mcp
```

当前接入使用 JSON-RPC 2.0，并至少支持：

```text
initialize
notifications/initialized
tools/list
tools/call
```

`tools/list` 返回工具名称、描述和 JSON Schema：

```json
{
  "jsonrpc": "2.0",
  "id": "request-id",
  "result": {
    "tools": [
      {
        "name": "query_orders",
        "description": "查询当前用户业务范围内的订单摘要。只读工具。",
        "inputSchema": {
          "type": "object",
          "properties": {
            "keyword": { "type": "string" },
            "page": { "type": "integer", "minimum": 1 },
            "limit": { "type": "integer", "minimum": 1, "maximum": 100 }
          },
          "additionalProperties": false
        }
      }
    ]
  }
}
```

工具成功结果建议使用 `structuredContent`，并提供简短文本：

```json
{
  "jsonrpc": "2.0",
  "id": "request-id",
  "result": {
    "structuredContent": {
      "items": [],
      "page": 1,
      "limit": 20,
      "total": 0
    },
    "content": [
      { "type": "text", "text": "未查询到符合条件的订单。" }
    ],
    "isError": false
  }
}
```

### 6.2 服务鉴权和可信上下文

推荐为 MCP Server 配置独立 Bearer Token：

```http
Authorization: Bearer <MCP_SERVICE_TOKEN>
```

SynapseFlow 在实际工具调用时附带：

| 请求头 | 说明 |
| --- | --- |
| `X-Agent-User-Id` | Bootstrap 提供的外部用户 ID |
| `X-Agent-Store-Id` | `scope.store_id` |
| `X-Agent-Product-Id` | SynapseFlow 产品 ID |
| `X-Agent-Project-Id` | SynapseFlow 项目 ID |
| `X-Agent-Project-App-Id` | ProjectApp ID |
| `X-Agent-Session-Id` | Agent 会话 ID |
| `X-Request-Id` | 调用追踪 ID |
| `X-Agent-Scope` | Base64URL 编码的完整可信 Scope JSON |

只有服务凭证验证成功后才能信任这些请求头。外部调用者不得绕过服务鉴权直接伪造它们。

### 6.3 最终业务权限

每次 `tools/call` 都必须：

```text
1. 验证 MCP Service Token
2. 读取可信 external_user_id 和业务范围
3. 验证用户仍然有效
4. 验证用户仍属于当前租户 / 组织 / 门店
5. 验证用户拥有当前工具对应的业务能力
6. 强制把可信范围注入查询或写操作
7. 执行业务应用服务
8. 裁剪和脱敏返回字段
9. 记录 request_id、用户、范围、工具和结果状态
```

建议在业务应用层集中提供：

```text
authorizeAgentCapability({
  external_user_id,
  trusted_scope,
  capability
})
```

能力编码示例：

```text
orders.read
inventory.read
sales.read
refund.approve
```

不要让每个工具各写一套权限判断，也不要只依赖 SynapseFlow 的工具绑定替代业务权限。

### 6.4 工具设计要求

- 第一版优先只开放只读工具。
- 工具名使用稳定的英文 `snake_case`。
- 描述明确业务范围、返回内容和是否只读。
- 参数设置枚举、分页、时间范围和长度上限。
- 工具参数不接受可信用户、租户、组织或门店范围。
- 只返回 Agent 真正需要的字段。
- 敏感数据必须脱敏或不返回。
- 未找到数据返回正常空结果，不伪造数据。
- 未知异常不得暴露数据库、内部地址或堆栈。

写操作还必须具备用户确认、幂等键、状态校验、细粒度权限、本地审计和补偿机制。

### 6.5 在 SynapseFlow 中启用工具

MCP Server 上线后，由 SynapseFlow 管理员：

1. 创建 MCP 服务并填写 Endpoint 和鉴权方式。
2. 测试连接并同步工具。
3. 检查工具名称、描述和 Schema。
4. 启用或发布允许 Agent 使用的工具。
5. 将 MCP 工具集绑定到对应 ProjectApp。
6. 使用测试账号验证成功、拒绝和越权场景。

MCP Server 中存在一个工具，不代表所有 ProjectApp 或业务用户都自动获得权限。

## 7. 本地开发

SynapseFlow 前端执行 `pnpm dev` 时会先生成 Agent 静态资源。本地常见地址：

```text
SynapseFlow API:    http://127.0.0.1:8000/api/v1
SynapseFlow Loader: http://localhost:5173/agent-static/loader/v1/loader.js
业务 Bootstrap:    http://localhost:<业务端口>/api/agent/bootstrap
业务 MCP:          http://127.0.0.1:<MCP端口>/mcp
```

如果 SynapseFlow 后端运行在 Docker，而 MCP Server 运行在宿主机：

- MCP Server 应监听容器可访问的地址，例如 `0.0.0.0`；
- SynapseFlow 中不要配置 `127.0.0.1`；
- Docker Desktop 通常可使用 `host.docker.internal`；
- 双方在同一 Docker 网络时，使用服务名和容器内部端口。

## 8. 生产发布要求

- 业务页面、业务 Bootstrap、SynapseFlow API 和静态资源使用 HTTPS。
- 业务 Bootstrap 保持同源，通过业务 Nginx 或 API Gateway 转发。
- 业务页面 Origin 同时加入 ProjectApp `allowed_origins` 和 `SF_CORS_ORIGINS`。
- Loader 固定路径为 `/agent-static/loader/v1/loader.js`。
- Widget 路径为 `/agent-static/widget/<version>/index.js`。
- Widget 使用 `1.2.3` 形式的精确版本。
- 已发布的 Loader 和 Widget 文件不可覆盖。
- 更新 Widget 时发布新版本并更新 ProjectApp 的 `widget_version`。
- MCP Server 由进程管理器或容器编排托管，并提供健康检查。
- MCP Endpoint 优先使用内网地址，不建议直接暴露公网。

## 9. 验收清单

### 基础接入

- [ ] 未登录调用 Bootstrap 返回 `401`。
- [ ] 无 Agent 使用权限的用户返回 `403`。
- [ ] 已登录用户获得标准 Bootstrap 响应。
- [ ] 浏览器和构建产物中不存在 Client Secret。
- [ ] 非允许 Origin 无法使用 Widget Token。
- [ ] Loader 和精确版本 Widget 均返回 `200`。
- [ ] Agent 可以打开、关闭和刷新 Token。
- [ ] 路由变化后 Context 会更新。
- [ ] 退出或切换身份后旧 Widget 被销毁。
- [ ] 不同业务用户无法读取彼此的 Agent 会话。

### MCP 工具

- [ ] 缺少或使用错误 Service Token 时调用被拒绝。
- [ ] 工具参数中的伪造用户或业务范围不会生效。
- [ ] 已停用用户或已移出范围的用户调用被拒绝。
- [ ] 无对应业务权限的用户调用被拒绝。
- [ ] 分页、日期、枚举和长度限制有效。
- [ ] 返回字段经过裁剪和脱敏。
- [ ] 未找到数据返回正常空结果。
- [ ] 系统异常不暴露内部实现信息。
- [ ] 两端可通过 `request_id` 定位同一次调用。

## 10. 常见问题

### Loader 返回 404

确认地址为 `/agent-static/loader/v1/loader.js`。本地开发需先生成 Agent 静态资源，并重新启动 SynapseFlow 前端开发服务器。

### Bootstrap 返回 401

检查浏览器是否携带原业务登录态，以及 Bootstrap 是否复用了正确的业务鉴权中间件。

### Bootstrap 返回 403 或 409

检查 ProjectApp、接入凭证是否启用，是否已绑定知识库和助手，以及用户是否有业务系统定义的 Agent 使用权限。

### Origin 或 CORS 错误

确认业务页面完整 Origin 同时存在于 ProjectApp `allowed_origins` 和 `SF_CORS_ORIGINS`。协议、域名或端口任一不同，都是不同 Origin。

### MCP 提示 `All connection attempts failed`

这表示 SynapseFlow 尚未连接到 MCP HTTP 服务，通常不是工具参数问题。检查 MCP 进程、Endpoint、Docker 地址、防火墙和反向代理。

### MCP 返回 Token 无效

确认 SynapseFlow MCP 配置与业务 MCP Server 使用同一环境、同一 Token，并在修改后重新加载服务。

## 11. 最小交付物

```text
业务前端
  - Agent Loader 适配模块
  - Agent 入口按钮
  - 路由 Context 更新
  - 登出 / 切换身份销毁逻辑

业务后端
  - Agent Bootstrap 配置
  - 同源 Bootstrap 路由
  - SynapseFlow Bootstrap Client
  - 登录态、权限、限流和错误处理测试

部署配置
  - Loader URL
  - Bootstrap 反向代理
  - Origin / CORS
  - 服务端密钥配置
```

接入工具时再增加：

```text
业务 MCP
  - MCP Server
  - Service Token 校验
  - 可信上下文解析
  - 统一业务授权入口
  - 工具定义和参数校验
  - 业务应用服务调用
  - 脱敏、错误和审计测试
```

长期维护时应保持：业务前端只装配，Bootstrap 只做身份交换，MCP 只做协议和用例调用，最终权限集中在业务系统统一授权层。不要在页面、Loader、Prompt 或单个工具中复制业务权限规则。
