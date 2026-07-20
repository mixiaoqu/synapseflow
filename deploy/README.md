# LangChain RAG 知识库生产部署说明

这份文档是当前仓库的推荐生产部署入口，目标是让国内服务器部署尽量稳定、简单、可维护。
当前仓库遵循“示例环境变量显式保留连接、寻址、初始化和常用运维项，纯内部固定值尽量留在 `docker-compose.prod.yml`”的原则。

## 部署文件说明

- `docker-compose.prod.yml`
  生产编排入口，包含 `nginx`、`frontend`、`backend`、`backend-worker`、`postgres`、`redis`
- `.env.prod.example`
  生产环境变量模板，按实际运行链路整理，并统一使用中文注释
- `deploy/nginx/default.conf.template`
  Docker 环境内的反向代理配置，负责前端入口、`/api`、`/agent-static` 和流式接口透传
- `deploy/nginx/synapseflow.host.conf.example`
  宿主机统一 Nginx 模板，按 `zsk.szsayu.com` 与 `zsk-test.szsayu.com` 分流生产和测试环境
- `docker/backend/Dockerfile`
  后端镜像构建
- `docker/frontend/Dockerfile.prod`
  前端生产镜像构建
- `frontend/src/agent-loader/`、`frontend/src/widget/`
  构建固定 CDN Loader 和精确版本的 Web Component Widget，产物统一位于 `/agent-static/`
- `deploy/AGENT_WIDGET.md`
  面向业务研发团队的通用 Agent 接入指南，包含 Bootstrap、Loader、MCP、最终业务权限、发布和验收流程

## 当前推荐拓扑

- 对外只开放宿主机 Nginx 的 `80/443`
- 宿主机 Nginx 作为唯一公网入口，按域名隔离生产和测试环境
- 生产 Docker Nginx 仅监听 `127.0.0.1:18081`
- 测试 Docker Nginx 仅监听 `127.0.0.1:18080`
- `frontend` 和 `backend` 仅绑定到 `127.0.0.1`
- `postgres`、`redis` 只在 Docker 内网使用
- 前端默认走同域名 `/api` 反代，不直接写死后端公网地址
- 宿主机 Nginx 负责 TLS 和域名分流，再转发到对应 Compose 栈的 Docker Nginx
- Docker Nginx 继续负责 `/`、`/api`、`/preview`、`/agent-static` 和流式接口的内部路由，不直接绕过它

这套方式最适合国内云服务器，优点是：

- 防火墙规则简单
- 不需要把后端端口暴露到公网
- 前端换域名时通常不需要重建镜像
- CORS 配置更容易收敛

## 国内服务器建议

- Docker 仓库拉取慢时，优先给 Docker daemon 配置镜像加速，而不是把公网端口长期暴露出来
- Python 依赖建议使用 `SF_UV_INDEX_URL`
- Node 依赖建议使用 `SF_NPM_REGISTRY`
- 域名已备案时，建议让 `443` 由宿主机 Nginx、云负载均衡或 CDN 终结，再转发到当前 Compose 栈

## 首次部署

1. 准备代码

```bash
git clone <your-repo> /opt/synapseflow
cd /opt/synapseflow
```

2. 准备环境变量

```bash
cp .env.prod.example .env.prod
```

3. 按 `.env.prod.example` 逐项填写 `.env.prod`

- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `NEO4J_PASSWORD`
- `GRAPH_ENABLED`
- `GRAPH_INDEXING_ENABLED`
- `GRAPH_URI`
- `GRAPH_USERNAME`
- `GRAPH_PASSWORD`
- `GRAPH_DATABASE`
- `SF_SECRET_KEY`
- `SILICONFLOW_API_KEY`
- `MOYU_API_KEY`
- `DEEPSEEK_API_KEY`
- `SF_CORS_ORIGINS`
- `SF_ENTERPRISE_SERVICE_TOKEN`
- `SF_INTEGRATION_CREDENTIAL_PEPPER`
- `SF_AGENT_PUBLIC_API_BASE_URL`
- `SF_EMBED_FRONTEND_BASE_URL`
- `SF_NGINX_SERVER_NAME`

如果你准备在首次启动时自动创建管理员，再额外填写：

- `BOOTSTRAP_ENABLED=true`
- `BOOTSTRAP_ADMIN_USERNAME`
- `BOOTSTRAP_ADMIN_EMAIL`
- `BOOTSTRAP_ADMIN_PASSWORD`
- `BOOTSTRAP_ADMIN_FULL_NAME`

推荐值：

- `SF_NGINX_SERVER_NAME=你的域名`
  如果还需要保留 `http://服务器IP` 直连备用入口，可写成 `你的域名 你的服务器IP`
- `SF_NGINX_BIND_HOST=127.0.0.1`
- `SF_NGINX_PORT=18081`
- `SF_CORS_ORIGINS=https://你的域名`
  如果还需要保留 `http://服务器IP` 直连备用入口，可补充为 `https://你的域名,http://你的服务器IP`
- `SF_EMBED_FRONTEND_BASE_URL=https://你的域名`
- `POSTGRES_USER=synapseflow`
- `POSTGRES_DB=synapseflow`
- `GRAPH_ENABLED=false`
- `GRAPH_INDEXING_ENABLED=false`
- `GRAPH_URI=bolt://neo4j:7687`
- `GRAPH_USERNAME=neo4j`
- `GRAPH_DATABASE=neo4j`
- `SF_ENTERPRISE_SERVICE_TOKEN=` 使用足够长的随机字符串
- `SF_INTEGRATION_CREDENTIAL_PEPPER=` 使用与其他密钥不同的足够长随机字符串
- `SF_AGENT_PUBLIC_API_BASE_URL=https://你的域名/api/v1`

`.env.prod.example` 已经显式保留了当前项目常见的连接、寻址、初始化和运维参数。没有列出的变量，通常说明当前项目已经在 `docker-compose.prod.yml` 中提供了稳定默认值。只有你明确需要调整时，才建议再补充这些变量，例如：

- 前端构建参数：`SF_FRONTEND_API_BASE_URL`、`SF_FRONTEND_API_TIMEOUT_MS`
- 日志与追踪：`SF_LOG_LEVEL`、`SF_LOG_JSON`、`SF_LANGSMITH_*`

这次显式保留 `POSTGRES_USER`、`POSTGRES_DB`、`GRAPH_URI`、`GRAPH_USERNAME`、`GRAPH_DATABASE`、端口绑定和队列参数，是因为它们虽然有默认值，但会直接影响连接串、初始化行为、服务寻址和运行容量，变更时应当一眼可见。

外层仅做 HTTPS 终结时，还应满足：

- 转发目标指向当前 Compose 栈暴露的 `80` 端口
- 保留原始 `Host`
- 透传 `X-Forwarded-For`
- 将 `X-Forwarded-Proto` 设为 `https`

4. 构建并启动

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml build
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
```

5. 检查状态

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f nginx
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f backend
```

## 升级流程

```bash
git pull
docker compose --env-file .env.prod -f docker-compose.prod.yml build
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
```

如果只改了前端或后端，也可以只重建对应服务。

## 关键最佳实践

- 不要开放 `5432`、`6379`、`8000`、`3000` 到公网
- 生产环境不要使用默认引导账号密码
- 让前端走同域名反代，避免把后端地址写死进前端构建产物
- 前端 `VITE_*` 变量属于构建期参数，不要把它们当成运行时热配置来维护
- 流式接口必须关闭 Nginx 缓冲，否则聊天/生成流会卡成整包返回
- `/agent-static/loader/v1/loader.js` 与 `/agent-static/widget/<精确版本>/index.js` 发布后不可覆盖；升级时发布新版本并更新 ProjectApp 的 `widget_version`
- `postgres_data`、`redis_data`、`backend_previews`、`backend_uploads`、`backend_uploaded_documents` 必须持久化
- 生产环境把 `.env.prod` 排除出版本控制

## 常用命令

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f
docker compose --env-file .env.prod -f docker-compose.prod.yml restart backend
docker compose --env-file .env.prod -f docker-compose.prod.yml pull
docker compose --env-file .env.prod -f docker-compose.prod.yml down
```

## 这次梳理后建议你长期遵循的原则

- 文档只认 `deploy/README.md` 和 `docker-compose.prod.yml`
- 示例变量只保留生产必填项和常用可选项
- 一切公网入口统一收口到 `nginx`
- 能用相对路径就不要在前端写死公网 API 域名
