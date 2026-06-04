# syntax=docker/dockerfile:1
ARG NPM_REGISTRY=https://registry.npmmirror.com

FROM node:20-alpine
ARG NPM_REGISTRY
ENV npm_config_registry=${NPM_REGISTRY}

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@latest --activate

COPY package.json pnpm-lock.yaml ./
ENV NODE_OPTIONS="--max-old-space-size=1024"
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile --network-concurrency 1 --child-concurrency 1

COPY . .

EXPOSE 5173

CMD ["pnpm", "exec", "vite", "--host", "0.0.0.0", "--port", "5173"]
