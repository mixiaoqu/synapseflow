# LangChain RAG 知识库生产部署说明

这份文档是当前仓库的推荐生产部署入口，目标是让国内服务器部署尽量稳定、简单、可维护。

## 部署文件说明

- `docker-compose.prod.yml`
  生产编排入口，包含 `nginx`、`frontend`、`backend`、`backend-worker`、`postgres`、`redis`
- `.env.prod.example`
  生产环境变量模板
- `deploy/nginx/default.conf.template`
  反向代理配置，负责前端入口、`/api` 转发、流式接口透传
- `docker/backend/Dockerfile`
  后端镜像构建
- `docker/frontend/Dockerfile.prod`
  前端生产镜像构建

## 当前推荐拓扑

- 对外只开放 `80/443`
- `nginx` 作为唯一公网入口
- `frontend` 和 `backend` 仅绑定到 `127.0.0.1`
- `postgres`、`redis` 只在 Docker 内网使用
- 前端默认走同域名 `/api` 反代，不直接写死后端公网地址

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

3. 重点修改 `.env.prod`

- `POSTGRES_PASSWORD`
- `SF_SECRET_KEY`
- `SF_CORS_ORIGINS`
- `SF_ENTERPRISE_SERVICE_TOKEN`
- `SF_EMBED_FRONTEND_BASE_URL`
- `BOOTSTRAP_ADMIN_PASSWORD`
- `BOOTSTRAP_USER_PASSWORD`
- `SF_NGINX_SERVER_NAME`

推荐值：

- `SF_CORS_ORIGINS=https://你的域名`
- `SF_EMBED_FRONTEND_BASE_URL=https://你的域名`
- `SF_NEXT_PUBLIC_API_URL=` 留空
  说明：让前端默认使用当前域名和 `/api` 反向代理
- `SF_ENTERPRISE_SERVICE_TOKEN=` 使用足够长的随机字符串

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
- 流式接口必须关闭 Nginx 缓冲，否则聊天/生成流会卡成整包返回
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
