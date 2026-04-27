"""Initialize database schema and ensure the default admin user exists."""

from __future__ import annotations

import asyncio
import os
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

PLACEHOLDER_PASSWORDS = {
    "admin",
    "admin123456",
    "password",
    "change-this-admin-password",
    "change-me",
}


def _env_bool(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required when BOOTSTRAP_ENABLED=true")
    return value


def _validate_bootstrap_password(password: str) -> None:
    normalized = password.strip()
    if len(normalized) < 12:
        raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD must be at least 12 characters")
    if normalized.lower() in PLACEHOLDER_PASSWORDS:
        raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD must not use a placeholder password")


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
    if not _env_bool("BOOTSTRAP_ENABLED", default=False):
        print("Bootstrap admin disabled; skipping admin user creation.")
        return

    admin_username = _required_env("BOOTSTRAP_ADMIN_USERNAME").lower()
    admin_email = _required_env("BOOTSTRAP_ADMIN_EMAIL").lower()
    admin_full_name = os.getenv("BOOTSTRAP_ADMIN_FULL_NAME", "System Administrator").strip()

    async with AsyncSessionLocal() as session:
        user = (
            await session.execute(
                select(User).where(
                    or_(
                        User.username == admin_username,
                        User.email == admin_email,
                    )
                )
            )
        ).scalar_one_or_none()

        if user is None:
            admin_password = _required_env("BOOTSTRAP_ADMIN_PASSWORD")
            _validate_bootstrap_password(admin_password)
            user = User(
                username=admin_username,
                email=admin_email,
                full_name=admin_full_name or None,
                hashed_password=hash_password(admin_password),
                role=ROLE_KB_ADMIN,
                is_active=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            print(f"Bootstrap admin created: username={user.username} email={user.email}")
        else:
            changed = False
            if user.role != ROLE_KB_ADMIN:
                user.role = ROLE_KB_ADMIN
                changed = True
            if not user.is_active:
                user.is_active = True
                changed = True
            if admin_full_name and not user.full_name:
                user.full_name = admin_full_name
                changed = True
            if changed:
                await session.commit()
                await session.refresh(user)
            print(
                "Bootstrap admin already exists; password was not changed: "
                f"username={user.username} email={user.email}"
            )

        await _ensure_team_membership(session, user_id=user.id, role="owner")


def main() -> None:
    code = _run_migrations()
    if code != 0:
        raise SystemExit(code)

    asyncio.run(_ensure_admin_user())


if __name__ == "__main__":
    main()
