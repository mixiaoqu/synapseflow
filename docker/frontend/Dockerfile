# Frontend Dockerfile
FROM node:20-alpine

WORKDIR /app

# 复制package文件
COPY package*.json ./

# 安装依赖
RUN npm install

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 3000

# 启动命令（由docker-compose覆盖）
CMD ["npm", "run", "dev"]
