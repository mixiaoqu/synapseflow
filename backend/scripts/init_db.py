"""初始化数据库：执行 init.sql 创建表结构"""
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# 从 DATABASE_URL 解析连接参数
url = os.getenv("DATABASE_URL", "")
# postgresql+asyncpg://postgres:123456@localhost:5433/synapseflow
if "+asyncpg" in url:
    url = url.replace("postgresql+asyncpg://", "")
parts = url.split("@")
if len(parts) != 2:
    print("无法解析 DATABASE_URL")
    exit(1)
user_pass, host_db = parts
user, password = user_pass.split(":", 1)
host_port, dbname = host_db.split("/")
if ":" in host_port:
    host, port = host_port.split(":")
else:
    host, port = host_port, "5432"

init_sql = Path(__file__).resolve().parent.parent.parent / "docker" / "postgres" / "init.sql"
if not init_sql.exists():
    print(f"init.sql 不存在: {init_sql}")
    exit(1)

async def main():
    import asyncpg
    conn = await asyncpg.connect(
        host=host,
        port=int(port),
        user=user,
        password=password,
        database=dbname,
    )
    try:
        sql = init_sql.read_text(encoding="utf-8")
        await conn.execute(sql)
        print("数据库初始化成功")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
