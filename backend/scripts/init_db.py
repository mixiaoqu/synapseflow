"""Initialize database schema and ensure the default admin user exists."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

from sqlalchemy import or_, select

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.authz import ROLE_KB_ADMIN
from app.core.security import hash_password
from app.db.models import Team, TeamMember, User
from app.db.session import AsyncSessionLocal

ADMIN_USERNAME = "admin"
ADMIN_EMAIL = "admin@synapseflow.local"
ADMIN_PASSWORD = "admin123456"
ADMIN_FULL_NAME = "System Administrator"


def _run_migrations() -> int:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(ROOT),
    )
    return result.returncode


async def _ensure_team_membership(session, *, user_id: int, role: str) -> None:
    team_ids = list((await session.execute(select(Team.id))).scalars().all())
    if not team_ids:
        return

    existing_memberships = {
        (team_id, member_user_id)
        for team_id, member_user_id in (
            await session.execute(select(TeamMember.team_id, TeamMember.user_id))
        ).all()
    }

    changed = False
    for team_id in team_ids:
        if (team_id, user_id) in existing_memberships:
            continue
        session.add(TeamMember(team_id=team_id, user_id=user_id, role=role))
        changed = True

    if changed:
        await session.commit()


async def _ensure_admin_user() -> None:
    async with AsyncSessionLocal() as session:
        user = (
            await session.execute(
                select(User).where(
                    or_(
                        User.username == ADMIN_USERNAME,
                        User.email == ADMIN_EMAIL,
                    )
                )
            )
        ).scalar_one_or_none()

        if user is None:
            user = User(
                username=ADMIN_USERNAME,
                email=ADMIN_EMAIL,
                full_name=ADMIN_FULL_NAME,
                hashed_password=hash_password(ADMIN_PASSWORD),
                role=ROLE_KB_ADMIN,
                is_active=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        else:
            user.username = ADMIN_USERNAME
            user.email = ADMIN_EMAIL
            user.full_name = ADMIN_FULL_NAME
            user.hashed_password = hash_password(ADMIN_PASSWORD)
            user.role = ROLE_KB_ADMIN
            user.is_active = True
            await session.commit()
            await session.refresh(user)

        await _ensure_team_membership(session, user_id=user.id, role="owner")

        print(f"Default admin ready: username={ADMIN_USERNAME} password={ADMIN_PASSWORD}")


def main() -> None:
    code = _run_migrations()
    if code != 0:
        raise SystemExit(code)

    asyncio.run(_ensure_admin_user())


if __name__ == "__main__":
    main()
