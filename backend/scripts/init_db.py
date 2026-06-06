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

from app.core.authz import SYSTEM_ROLE_ADMIN
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
DEFAULT_TEAM_CODE = "default"
DEFAULT_TEAM_NAME = "默认团队"


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


async def _ensure_default_team(session) -> Team:
    team_name = os.getenv("BOOTSTRAP_DEFAULT_TEAM_NAME", DEFAULT_TEAM_NAME).strip() or DEFAULT_TEAM_NAME
    team_code = os.getenv("BOOTSTRAP_DEFAULT_TEAM_CODE", DEFAULT_TEAM_CODE).strip() or DEFAULT_TEAM_CODE
    team = (
        await session.execute(
            select(Team).where(
                or_(
                    Team.code == team_code,
                    Team.name == team_name,
                )
            )
        )
    ).scalar_one_or_none()
    if team is not None:
        return team

    team = Team(name=team_name, code=team_code, description="系统初始化默认团队")
    session.add(team)
    await session.commit()
    await session.refresh(team)
    print(f"Bootstrap default team created: name={team.name} code={team.code}")
    return team


async def _ensure_team_owner(session, *, team_id: int, user_id: int) -> None:
    member = (
        await session.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if member is None:
        session.add(TeamMember(team_id=team_id, user_id=user_id, role="owner"))
        await session.commit()
        return
    if member.role != "owner":
        member.role = "owner"
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
                role=SYSTEM_ROLE_ADMIN,
                is_active=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            print(f"Bootstrap admin created: username={user.username} email={user.email}")
        else:
            changed = False
            if user.role != SYSTEM_ROLE_ADMIN:
                user.role = SYSTEM_ROLE_ADMIN
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

        team = await _ensure_default_team(session)
        await _ensure_team_owner(session, team_id=team.id, user_id=user.id)


def main() -> None:
    code = _run_migrations()
    if code != 0:
        raise SystemExit(code)

    asyncio.run(_ensure_admin_user())


if __name__ == "__main__":
    main()
