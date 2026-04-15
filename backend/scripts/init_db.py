"""Initialize database schema and ensure bootstrap users exist."""

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

from app.core.authz import ROLE_END_USER, ROLE_KB_ADMIN
from app.core.security import hash_password, verify_password
from app.db.models import Team, TeamMember, User
from app.db.session import AsyncSessionLocal

LEGACY_ADMIN_PASSWORD = "ChangeMe123!"
DEFAULT_BOOTSTRAP_PASSWORD = "12345678"
INVALID_BOOTSTRAP_PASSWORDS = {
    DEFAULT_BOOTSTRAP_PASSWORD,
    "change-this-admin-password",
    "change-this-user-password",
}


def _env(name: str, default: str) -> str:
    return (os.getenv(name) or default).strip()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _ensure_safe_bootstrap_passwords(*, admin_password: str, user_password: str) -> None:
    env = _env("ENV", "development").lower()
    if env not in {"prod", "production", "release"}:
        return

    weak_names = []
    if admin_password in INVALID_BOOTSTRAP_PASSWORDS:
        weak_names.append("BOOTSTRAP_ADMIN_PASSWORD")
    if user_password in INVALID_BOOTSTRAP_PASSWORDS:
        weak_names.append("BOOTSTRAP_USER_PASSWORD")

    if weak_names:
        raise RuntimeError(
            "Production bootstrap users require strong passwords. "
            f"Please change: {', '.join(weak_names)}"
        )


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


async def _ensure_user(
    session,
    *,
    username: str,
    email: str,
    full_name: str,
    role: str,
    password: str,
    update_legacy_password: bool = False,
) -> User:
    normalized_username = username.strip().lower()
    normalized_email = email.strip().lower()

    user = (
        await session.execute(
            select(User).where(
                or_(
                    User.username == normalized_username,
                    User.email == normalized_email,
                )
            )
        )
    ).scalar_one_or_none()

    if user is None:
        user = User(
            username=normalized_username,
            email=normalized_email,
            full_name=full_name,
            hashed_password=hash_password(password),
            role=role,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    changed = False
    if user.username != normalized_username:
        user.username = normalized_username
        changed = True
    if user.email != normalized_email:
        user.email = normalized_email
        changed = True
    if user.full_name != full_name:
        user.full_name = full_name
        changed = True
    if user.role != role:
        user.role = role
        changed = True
    if not user.is_active:
        user.is_active = True
        changed = True

    if update_legacy_password and verify_password(LEGACY_ADMIN_PASSWORD, user.hashed_password):
        user.hashed_password = hash_password(password)
        changed = True

    if changed:
        await session.commit()
        await session.refresh(user)

    return user


async def _seed_bootstrap_users() -> None:
    admin_username = _env("BOOTSTRAP_ADMIN_USERNAME", "admin")
    admin_email = _env("BOOTSTRAP_ADMIN_EMAIL", "admin@synapseflow.local")
    admin_password = _env("BOOTSTRAP_ADMIN_PASSWORD", DEFAULT_BOOTSTRAP_PASSWORD)

    user_username = _env("BOOTSTRAP_USER_USERNAME", "user")
    user_email = _env("BOOTSTRAP_USER_EMAIL", "user@synapseflow.local")
    user_password = _env("BOOTSTRAP_USER_PASSWORD", DEFAULT_BOOTSTRAP_PASSWORD)
    _ensure_safe_bootstrap_passwords(
        admin_password=admin_password,
        user_password=user_password,
    )

    async with AsyncSessionLocal() as session:
        admin_user = await _ensure_user(
            session,
            username=admin_username,
            email=admin_email,
            full_name="System Administrator",
            role=ROLE_KB_ADMIN,
            password=admin_password,
            update_legacy_password=True,
        )
        normal_user = await _ensure_user(
            session,
            username=user_username,
            email=user_email,
            full_name="Default User",
            role=ROLE_END_USER,
            password=user_password,
        )

        await _ensure_team_membership(session, user_id=admin_user.id, role="owner")
        await _ensure_team_membership(session, user_id=normal_user.id, role="member")

        print(
            f"Bootstrap users ready: admin={admin_user.username}, "
            f"user={normal_user.username}"
        )


def main() -> None:
    code = _run_migrations()
    if code != 0:
        raise SystemExit(code)

    if not _env_bool("BOOTSTRAP_ENABLED", True):
        print("Bootstrap user seeding skipped (BOOTSTRAP_ENABLED=false).")
        return

    asyncio.run(_seed_bootstrap_users())


if __name__ == "__main__":
    main()
