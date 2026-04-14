"""初始化数据库：执行 Alembic 迁移至最新版本（含 pgvector 扩展与表结构）。"""
import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(root),
    )
    raise SystemExit(r.returncode)


if __name__ == "__main__":
    main()
