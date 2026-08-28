# 业务端 Agent Tools 接入指南

业务系统直接在现有后端中实现 Agent Tools API，由 Nginx 通过 HTTPS 暴露给 SynapseFlow。业务端不新增 MCP 进程、端口、容器或仓库。

```text
Agent -> SynapseFlow ToolProviderGateway -> HTTPS -> 业务端 Nginx
      -> 现有业务后端 Agent Tools API -> Service -> Repository / 数据库
```

第一阶段只接入只读工具。SynapseFlow 负责发现、同步、发布、逐工具授权、调用和审计；业务 Service 负责数据权限、查询规则和脱敏。

## 1. 接入结果

业务端只需要在**现有后端服务**中增加两个 HTTP 接口，不需要启动额外服务：

1. 在 Service 中实现可供 Agent 使用的只读查询能力。
2. 在静态工具注册表中声明工具名称、说明、参数和执行函数。
3. 由 `/manifest` 返回工具清单，由 `/execute` 执行白名单中的工具。
4. 通过现有 Nginx 将这两个接口以 HTTPS 暴露给 SynapseFlow。
5. 管理员在 SynapseFlow 注册 Provider，完成测试、同步、发布和应用授权。

职责边界如下：

| 组件 | 负责 | 不负责 |
| --- | --- | --- |
| Agent Tools 路由 | Token 校验、请求响应转换 | 业务查询、权限规则 |
| 工具注册表 | 工具声明、静态白名单分发、读取可信上下文 | 数据库访问 |
| Business Service | 数据权限、查询规则、结果脱敏 | HTTP 和 Agent 协议 |
| Repository | SQL、MongoDB Pipeline、外部数据访问 | 业务决策 |
| SynapseFlow | 工具发现、参数校验、发布授权、调用审计 | 业务数据权限 |

## 2. 固定接口

```text
GET  /internal/agent-tools/manifest
POST /internal/agent-tools/execute
```

两个接口都必须校验业务项目专用的 Bearer Service Token：

```http
Authorization: Bearer <service-token>
```

生产环境必须使用 HTTPS，并通过防火墙、Nginx allowlist 或云安全组限制来源。Token 不能提交到 Git、输出到日志或返回给客户端。

## 3. Manifest

Manifest 是工具清单。SynapseFlow 用它发现工具、读取参数 Schema 和可信上下文要求，并计算 Schema 哈希；它不执行查询，也不包含业务数据。

```json
{
  "contract_version": "1.0",
  "tools": [{
    "name": "query_products",
    "description": "查询当前门店的商品、价格和库存。只读工具。",
    "input_schema": {
      "type": "object",
      "properties": {
        "keyword": { "type": "string" },
        "page": { "type": "integer", "minimum": 1 }
      },
      "additionalProperties": false
    },
    "output_schema": {},
    "required_context": ["store_id"]
  }]
}
```

约束：

- `contract_version` 当前只能是 `1.0`。
- 工具名使用稳定的英文 `snake_case`，同一 Provider 内唯一。
- `input_schema` 使用 JSON Schema，并应设置 `additionalProperties: false`。
- `description` 要写清用途、数据范围、日期跨度、分页上限等限制，Agent 会依据它选择工具和生成参数。
- `output_schema` 第一版可以使用空对象 `{}`；需要稳定约束输出时再补充。
- `required_context` 只能使用 `external_user_id`、`project_app_id`、`project_id`、`request_id`、`session_id`、`store_id`。
- 身份、权限和范围字段不得出现在 `input_schema.properties`，包括 `store_id`、`user_id`、`external_user_id`、`tenant_id`、`project_id`、`project_app_id`、`role`、`permission`。
- 第一阶段只声明只读工具。

Schema 变化后，SynapseFlow 会将已发布工具标记为待审核。重新测试并发布前，Agent 不能调用该工具。

## 4. Execute

```json
{
  "contract_version": "1.0",
  "name": "query_products",
  "arguments": { "keyword": "感冒药", "page": 1 },
  "context": {
    "subject": { "external_user_id": "user-001" },
    "scope": { "store_id": "store-001" },
    "source": {
      "project_id": 1,
      "project_app_id": 2,
      "session_id": "session-001",
      "request_id": "request-001"
    }
  }
}
```

`arguments` 由模型生成，始终是不可信输入。`context` 由 SynapseFlow 根据已验证的应用会话构造，只有 Service Token 验证通过后才能作为权限范围使用。业务端必须分别处理二者，禁止让 `arguments` 覆盖 `context`。

成功响应：

```json
{ "success": true, "data": { "items": [], "total": 0 } }
```

失败响应：

```json
{
  "error": {
    "type": "INVALID_PARAMS",
    "reason": "keyword不能为空",
    "message": "keyword不能为空",
    "data": {}
  }
}
```

稳定错误码建议使用 `INVALID_PARAMS`、`CONTEXT_REQUIRED`、`FORBIDDEN`、`TOOL_NOT_FOUND`、`RATE_LIMITED`、`INTERNAL_ERROR`。鉴权失败使用 `UNAUTHORIZED`。对应使用 HTTP 400、401、403、404、429、500。

## 5. 业务端代码示例

在现有后端中维护静态白名单注册表，由同一份注册表生成 manifest 并分发 execute，避免声明和执行映射漂移：

```text
src/
├─ agent-tools/
│  ├─ errors.js
│  ├─ registry.js
│  ├─ handlers.js
│  └─ routes.js
└─ business/
   ├─ errors.js
   ├─ services/
   │  └─ sales-query-service.js
   └─ repositories/
      └─ sales-query-repository.js
```

路由只负责 Token、契约版本、请求格式和响应转换；dispatcher 只允许调用注册表中的函数；业务 Service 负责权限、查询规则和脱敏；Repository 只负责数据访问。禁止根据请求中的模块名或方法名动态加载代码。

以下是 CommonJS 风格的最小示例。它应作为现有 Node.js 后端的一组路由运行，不是新的独立服务。

### 5.1 稳定业务错误

```js
// src/agent-tools/errors.js
class AgentToolError extends Error {
  constructor(type, message) {
    super(message)
    this.name = 'AgentToolError'
    this.type = type
  }
}

module.exports = { AgentToolError }
```

业务层使用自己的错误类型，不依赖 Agent Tools：

```js
// src/business/errors.js
class BusinessQueryError extends Error {
  constructor(code, message) {
    super(message)
    this.name = 'BusinessQueryError'
    this.code = code
  }
}

module.exports = { BusinessQueryError }
```

### 5.2 静态工具注册表

```js
// src/agent-tools/registry.js
const Ajv = require('ajv')
const { AgentToolError } = require('./errors')
const { BusinessQueryError } = require('../business/errors')
const salesService = require('../business/services/sales-query-service')

const CONTRACT_VERSION = '1.0'
const RESERVED_ARGUMENTS = new Set([
  'external_user_id', 'project_app_id', 'project_id', 'request_id',
  'session_id', 'store_id', 'tenant_id', 'user_id', 'role', 'permission',
])
const ajv = new Ajv({ allErrors: true, strict: false })

const tools = {
  query_sales_summary: {
    description: '汇总当前门店指定日期范围的销售和退款数据。日期格式为 YYYY-MM-DD，跨度最多 366 天。只读工具。',
    input_schema: {
      type: 'object',
      properties: {
        start_date: {
          type: 'string',
          description: '查询开始日期，格式为 YYYY-MM-DD，必须与 end_date 同时提供，查询跨度最多 366 天。',
        },
        end_date: {
          type: 'string',
          description: '查询结束日期，格式为 YYYY-MM-DD，必须与 start_date 同时提供，查询跨度最多 366 天。',
        },
      },
      additionalProperties: false,
    },
    output_schema: {},
    required_context: ['store_id'],
    execute: async ({ arguments: args, context }) => {
      const storeId = String(context.scope && context.scope.store_id || '').trim()
      if (!storeId) {
        throw new AgentToolError('CONTEXT_REQUIRED', '缺少可信上下文：store_id')
      }
      return salesService.querySummary({
        storeId,
        startDate: args.start_date,
        endDate: args.end_date,
      })
    },
  },
}

const validators = Object.fromEntries(
  Object.entries(tools).map(([name, tool]) => [name, ajv.compile(tool.input_schema)]),
)

function createManifest() {
  return {
    contract_version: CONTRACT_VERSION,
    tools: Object.entries(tools).map(([name, tool]) => ({
      name,
      description: tool.description,
      input_schema: tool.input_schema,
      output_schema: tool.output_schema,
      required_context: tool.required_context,
    })),
  }
}

async function executeTool(request) {
  const name = String(request.name || '').trim()
  const tool = tools[name]
  if (!tool) {
    throw new AgentToolError('TOOL_NOT_FOUND', `不支持的业务工具：${request.name || ''}`)
  }
  const args = request.arguments
  if (!args || typeof args !== 'object' || Array.isArray(args)) {
    throw new AgentToolError('INVALID_PARAMS', 'arguments必须是对象')
  }
  const reserved = Object.keys(args).find(key => RESERVED_ARGUMENTS.has(key))
  if (reserved) {
    throw new AgentToolError('INVALID_PARAMS', `arguments不能包含可信上下文字段：${reserved}`)
  }
  if (!validators[name](args)) {
    const reason = ajv.errorsText(validators[name].errors, { separator: '；' })
    throw new AgentToolError('INVALID_PARAMS', `工具参数不符合要求：${reason}`)
  }
  try {
    return await tool.execute({ arguments: args, context: request.context || {} })
  } catch (error) {
    if (error instanceof BusinessQueryError) {
      throw new AgentToolError(error.code, error.message)
    }
    throw error
  }
}

module.exports = { createManifest, executeTool }
```

示例使用成熟的 JSON Schema 校验器校验类型、必填项、枚举、数值边界和未知字段。若项目尚未安装 Ajv，可执行 `npm install ajv`；已有等价校验器时直接复用，不需要重复引入。

### 5.3 HTTP 处理器

```js
// src/agent-tools/handlers.js
const crypto = require('crypto')
const { createManifest, executeTool } = require('./registry')

function tokenEquals(actual, expected) {
  const left = Buffer.from(String(actual || ''))
  const right = Buffer.from(String(expected || ''))
  return left.length > 0 && left.length === right.length && crypto.timingSafeEqual(left, right)
}

function verifyServiceToken(req, res, next) {
  const authorization = String(req.headers.authorization || '')
  const actual = authorization.startsWith('Bearer ') ? authorization.slice(7).trim() : ''
  const expected = String(process.env.AGENT_TOOLS_SERVICE_TOKEN || '').trim()
  if (!expected) return res.status(500).json({ error: { type: 'INTERNAL_ERROR', message: '服务端未配置 Agent Tools Token' } })
  if (!tokenEquals(actual, expected)) return res.status(401).json({ error: { type: 'UNAUTHORIZED', message: 'Service Token 无效' } })
  return next()
}

function manifestHandler(req, res) {
  return res.json(createManifest())
}

async function executeHandler(req, res) {
  const request = req.body || {}
  if (request.contract_version !== '1.0') {
    return res.status(400).json({ error: { type: 'INVALID_PARAMS', message: '不支持的 Agent Tools 契约版本' } })
  }
  try {
    const data = await executeTool(request)
    return res.json({ success: true, data })
  } catch (error) {
    const statuses = {
      INVALID_PARAMS: 400,
      CONTEXT_REQUIRED: 400,
      FORBIDDEN: 403,
      NOT_FOUND: 404,
      TOOL_NOT_FOUND: 404,
      RATE_LIMITED: 429,
    }
    const type = error.type || 'INTERNAL_ERROR'
    const status = statuses[type] || 500
    const message = status < 500 ? error.message : '工具执行失败'
    if (status === 500) console.error('[agent-tools] execute failed', error)
    return res.status(status).json({ success: false, error: { type, message } })
  }
}

module.exports = { executeHandler, manifestHandler, verifyServiceToken }
```

### 5.4 挂载到现有后端

```js
// src/agent-tools/routes.js
const router = require('express').Router()
const { executeHandler, manifestHandler, verifyServiceToken } = require('./handlers')

router.get('/manifest', verifyServiceToken, manifestHandler)
router.post('/execute', verifyServiceToken, executeHandler)

module.exports = router
```

```js
// 现有后端入口，不要新建 listen 或新端口
const agentToolsRoutes = require('./agent-tools/routes')
app.use('/internal/agent-tools', express.json({ limit: '1mb' }), agentToolsRoutes)
```

### 5.5 Business Service

```js
// src/business/services/sales-query-service.js
const { BusinessQueryError } = require('../errors')
const salesRepository = require('../repositories/sales-query-repository')

const MAX_QUERY_DAYS = 366

function normalizeDate(value, field) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(value || ''))) {
    throw new BusinessQueryError('INVALID_PARAMS', `${field}必须使用 YYYY-MM-DD 格式`)
  }
  const date = new Date(`${value}T00:00:00.000Z`)
  if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== value) {
    throw new BusinessQueryError('INVALID_PARAMS', `${field}不是有效日期`)
  }
  return date
}

async function querySummary({ storeId, startDate, endDate }) {
  if (!startDate || !endDate) {
    throw new BusinessQueryError('INVALID_PARAMS', '开始日期和结束日期必须同时提供')
  }
  const start = normalizeDate(startDate, 'start_date')
  const end = normalizeDate(endDate, 'end_date')
  const days = Math.floor((end - start) / 86400000) + 1
  if (days < 1 || days > MAX_QUERY_DAYS) {
    throw new BusinessQueryError('INVALID_PARAMS', `查询日期跨度必须在 1 至 ${MAX_QUERY_DAYS} 天内`)
  }

  // Service 使用可信 storeId 限定数据范围，并在返回前完成脱敏。
  return salesRepository.aggregateByStore({ storeId, start, end })
}

module.exports = { querySummary }
```

### 5.6 Repository

```js
// src/business/repositories/sales-query-repository.js
const db = require('../../infrastructure/database')

async function aggregateByStore({ storeId, start, end }) {
  return db.orders.aggregateSales({
    storeId,
    paidAt: { $gte: start, $lt: new Date(end.getTime() + 86400000) },
  })
}

module.exports = { aggregateByStore }
```

上面的 `db.orders.aggregateSales` 是数据访问占位示例，应替换为业务项目已有 Repository 或 ORM 查询。关键要求是查询条件始终包含可信 `storeId`，Agent Tools 层不直接拼接 SQL、MongoDB Pipeline 或实现第二份业务规则。

## 6. Nginx

两个接口都需要经过 Nginx 转发，因为 SynapseFlow 与业务端不在同一服务器：

```nginx
location = /internal/agent-tools/manifest {
    proxy_pass http://business_backend/api-backstage/agent_tools/manifest;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

location = /internal/agent-tools/execute {
    proxy_pass http://business_backend/api-backstage/agent_tools/execute;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Nginx 不应移除 `Authorization` 请求头。只暴露这两个精确路径，并配置请求体限制和合理超时，不要公开整个后台管理 API。

## 7. 业务端联调

先直接验证业务端，再到 SynapseFlow 注册 Provider。以下命令在 Linux/macOS 或 Git Bash 中执行：

```bash
export AGENT_TOOLS_URL='https://business.example.com/internal/agent-tools'
export AGENT_TOOLS_TOKEN='<service-token>'

curl --fail-with-body \
  -H "Authorization: Bearer ${AGENT_TOOLS_TOKEN}" \
  -H 'Accept: application/json' \
  "${AGENT_TOOLS_URL}/manifest"
```

```bash
curl --fail-with-body \
  -X POST \
  -H "Authorization: Bearer ${AGENT_TOOLS_TOKEN}" \
  -H 'Content-Type: application/json' \
  "${AGENT_TOOLS_URL}/execute" \
  -d '{
    "contract_version": "1.0",
    "name": "query_sales_summary",
    "arguments": {
      "start_date": "2025-01-01",
      "end_date": "2025-12-31"
    },
    "context": {
      "subject": { "external_user_id": "test-user" },
      "scope": { "store_id": "test-store" },
      "source": {
        "project_id": 1,
        "project_app_id": 1,
        "session_id": "manual-test",
        "request_id": "manual-test-001"
      }
    }
  }'
```

联调时至少验证：正确 Token 成功、错误 Token 返回 401、未知工具返回 404、缺少 `store_id` 返回 400，以及越界参数不会触发越权查询。

## 8. 在 SynapseFlow 注册和发布

1. 在业务端实现 Service、静态注册表、manifest 和 execute。
2. 配置独立 Token 和 Nginx HTTPS 转发。
3. 在 SynapseFlow 新增 Provider，并填写下表字段。

| 字段 | 示例 | 说明 |
| --- | --- | --- |
| 团队 | 业务所属团队 | Provider、工具和授权所属范围 |
| Code | `medical-center` | SynapseFlow 内部唯一标识，用于工具 Key 和审计；不需要出现在 manifest 中 |
| 名称 | `医疗中心` | 管理端显示名称 |
| 接入类型 | `business_http` | 使用本文的 Agent Tools HTTP 契约 |
| Base URL | `https://business.example.com/internal/agent-tools` | 不要追加 `/manifest` 或 `/execute` |
| 鉴权方式 | `bearer` | 对应 `Authorization: Bearer ...` |
| Service Token | 与业务端相同 | 每个业务系统使用独立 Token，长度至少 16 个字符 |
| 启用 | 是 | 停用后不再调用该 Provider |

4. 执行“测试连接”，确认 SynapseFlow 能读取 manifest。
5. 执行“同步工具”，将清单同步到 SynapseFlow。
6. 为每个工具填写面向 Agent 的说明、风险等级，并使用管理测试验证真实返回。
7. 发布工具；如果 Schema 后续变化，需要重新测试和发布。
8. 在 Project App 中逐工具授权，并通过真实 Agent 会话验证。

Agent 不扫描业务系统。只有管理员显式注册 Provider 后，SynapseFlow 才会发现工具；Agent 本身不知道业务地址和 Token。

新增工具时只需实现业务 Service，在静态注册表中登记，重新同步、测试、发布和授权。不需要新增服务、进程、端口、Docker 容器、MCP Server 或 NPM 包。

## 9. 安全和运行约束

- 业务 Service 必须使用可信上下文再次校验租户、门店和用户的数据权限，不能只依赖 Agent 提供的查询条件。
- `arguments` 只允许 Schema 声明的字段，必须限制分页大小、日期跨度和最大返回量。
- Token 按业务系统独立配置并支持轮换，不写入 Git、前端代码、响应或日志。
- Nginx 只暴露两个精确路径，启用 HTTPS、来源限制、请求体大小限制和超时。
- 不跟随重定向；Provider 主机应加入 SynapseFlow 的 `TOOL_PROVIDER_ALLOWED_HOSTS` allowlist。
- 未知异常只向调用方返回通用中文错误，详细堆栈仅记录在业务端内部日志。
- 第一版只开放查询类工具。写入、退款、审批等操作需要另行设计确认和幂等机制。

## 10. 常见问题

**业务端需要新建服务吗？**  
不需要。把 Agent Tools 路由挂载到现有业务后端，由现有进程和端口提供服务。

**SynapseFlow 如何发现业务端？**  
不会自动扫描。管理员先注册 Provider，SynapseFlow 再通过 `GET {base_url}/manifest` 获取工具。

**两个接口需要经过 Nginx 吗？**  
当 SynapseFlow 和业务端不在同一内网或同一服务器时需要。Nginx 负责 HTTPS 和精确路径转发，业务后端仍是原来的服务。

**为什么 manifest 不包含 Provider code？**  
Provider code 由 SynapseFlow 管理，用于生成唯一工具 Key 和审计。同一个业务端接口可以在不同环境注册为不同 Provider，不应由业务端重复声明。

**Agent 如何调用工具？**  
Agent 只看到已发布且已授权的工具。SynapseFlow 校验参数并注入可信上下文，然后调用 `POST {base_url}/execute`；Agent 不接触业务地址和 Token。

## 11. 验收清单

- [ ] 错误或缺失 Token 时两个接口都返回 401。
- [ ] 未知工具、错误参数和缺失可信上下文被拒绝。
- [ ] 模型参数不能覆盖门店、用户、租户或项目范围。
- [ ] 业务 Service 再次校验数据权限并脱敏敏感字段。
- [ ] 查询限制分页、时间范围和最大返回量。
- [ ] Nginx 只开放两个工具接口并启用 HTTPS 和来源限制。
- [ ] SynapseFlow 已完成测试、同步、发布和逐工具授权。
- [ ] 日志和审计不包含 Token、完整上下文或完整业务响应。
