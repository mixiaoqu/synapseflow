# syntax=docker/dockerfile:1
FROM node:20-alpine

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@latest --activate

COPY package.json pnpm-lock.yaml ./
ENV NODE_OPTIONS="--max-old-space-size=1024"
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile --network-concurrency 1 --child-concurrency 1

COPY . .

EXPOSE 3000

CMD ["pnpm", "run", "dev"]
