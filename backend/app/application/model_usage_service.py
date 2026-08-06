"""Application service for the AI cost center summary."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.model_usage_repository import ModelUsageRepository
from app.utils.time import utc_now


def _as_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (TypeError, ValueError):
        return Decimal("0")


def _usage_models(payload: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        return {}
    models = payload.get("models")
    return dict(models) if isinstance(models, dict) else {}


def _add_model_usage(target: dict[str, dict[str, Any]], payload: Any) -> None:
    for model_key, raw in _usage_models(payload).items():
        if not isinstance(raw, dict):
            continue
        item = target.setdefault(
            str(model_key),
            {
                "name": str(raw.get("model_key") or model_key),
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "estimated_cost": Decimal("0"),
            },
        )
        item["input_tokens"] += int(raw.get("input_tokens") or 0)
        item["output_tokens"] += int(raw.get("output_tokens") or 0)
        item["total_tokens"] += int(raw.get("total_tokens") or 0)
        item["estimated_cost"] += _as_decimal(raw.get("estimated_cost"))


def _serialize_models(models: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(models.values(), key=lambda item: item["total_tokens"], reverse=True)
    total_tokens = sum(int(item["total_tokens"]) for item in ordered)
    tones = ("blue", "green", "purple", "slate")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(ordered):
        share = round((item["total_tokens"] / total_tokens) * 100) if total_tokens else 0
        result.append(
            {
                "name": item["name"],
                "share": share,
                "tone": tones[index % len(tones)],
                "input_tokens": item["input_tokens"],
                "output_tokens": item["output_tokens"],
                "total_tokens": item["total_tokens"],
                "estimated_cost": str(item["estimated_cost"]),
            }
        )
    return result


def _date_bounds(start_date: date | None, end_date: date | None) -> tuple[datetime, datetime]:
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=6))
    return datetime.combine(start, time.min), datetime.combine(end, time.max)


def _bucket(value: datetime, granularity: str) -> tuple[str, str]:
    current = value.date()
    if granularity == "month":
        key = current.strftime("%Y-%m")
        return key, current.strftime("%Y-%m")
    if granularity == "week":
        monday = current - timedelta(days=current.weekday())
        key = monday.isoformat()
        return key, f"{monday.month:02d}-{monday.day:02d}"
    key = current.isoformat()
    return key, current.strftime("%m-%d")


class ModelUsageService:
    """Aggregate persisted chat/evaluation summaries for the cost center."""

    async def summary(
        self,
        db: AsyncSession,
        *,
        team_ids: list[int] | None,
        start_date: date | None,
        end_date: date | None,
        granularity: str,
    ) -> dict[str, Any]:
        start_at, end_at = _date_bounds(start_date, end_date)
        normalized_granularity = granularity if granularity in {"day", "week", "month"} else "day"

        if team_ids == []:
            return self._empty_response(start_at, end_at, normalized_granularity)
        repository = ModelUsageRepository(db)
        chat_rows = await repository.list_chat_usage(
            team_ids=team_ids,
            start_at=start_at,
            end_at=end_at,
        )
        eval_rows = await repository.list_evaluation_usage(
            team_ids=team_ids,
            start_at=start_at,
            end_at=end_at,
        )
        groups: dict[str, dict[str, Any]] = {}
        trend: dict[str, dict[str, Any]] = {}

        def add_record(
            *,
            scene: str,
            created_at: datetime,
            team_id: int | None,
            team_name: str | None,
            application: str,
            product_id: int | None,
            product_name: str | None,
            project_id: int | None,
            project_name: str | None,
            project_app_id: int | None,
            project_app_name: str | None,
            input_tokens: int | None,
            output_tokens: int | None,
            total_tokens: int | None,
            estimated_cost: Any,
            token_usage: Any,
            group_id: str,
        ) -> None:
            if total_tokens is None:
                return
            cost = _as_decimal(estimated_cost)
            group = groups.setdefault(
                group_id,
                {
                    "id": group_id,
                    "team_id": team_id,
                    "team": team_name or "未命名团队",
                    "application": application,
                    "product_id": product_id,
                    "product_name": product_name,
                    "project_id": project_id,
                    "project_name": project_name,
                    "project_app_id": project_app_id,
                    "project_app_name": project_app_name,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "chat_tokens": 0,
                    "evaluation_tokens": 0,
                    "estimated_cost": Decimal("0"),
                    "models": {},
                    "has_usage": False,
                },
            )
            group["input_tokens"] += int(input_tokens or 0)
            group["output_tokens"] += int(output_tokens or 0)
            group["total_tokens"] += int(total_tokens or 0)
            group[f"{scene}_tokens"] += int(total_tokens or 0)
            group["estimated_cost"] += cost
            group["has_usage"] = group["has_usage"] or bool(token_usage)
            _add_model_usage(group["models"], token_usage)

            bucket_key, label = _bucket(created_at, normalized_granularity)
            point = trend.setdefault(
                bucket_key,
                {
                    "label": label,
                    "date": bucket_key,
                    "total_tokens": 0,
                    "estimated_cost": Decimal("0"),
                    "chat_tokens": 0,
                    "evaluation_tokens": 0,
                },
            )
            point["total_tokens"] += int(total_tokens or 0)
            point[f"{scene}_tokens"] += int(total_tokens or 0)
            point["estimated_cost"] += cost

        for row in chat_rows:
            application = (
                row.project_app_name
                or row.project_name
                or row.product_name
                or "未绑定应用"
            )
            group_id = f"chat:{row.project_app_id or row.project_id or row.product_id or 'unbound'}:{row.team_id or 0}"
            add_record(
                scene="chat",
                created_at=row.created_at,
                team_id=row.team_id,
                team_name=row.team_name,
                application=application,
                product_id=row.product_id,
                product_name=row.product_name,
                project_id=row.project_id,
                project_name=row.project_name,
                project_app_id=row.project_app_id,
                project_app_name=row.project_app_name,
                input_tokens=row.input_tokens,
                output_tokens=row.output_tokens,
                total_tokens=row.total_tokens,
                estimated_cost=row.estimated_cost,
                token_usage=row.token_usage,
                group_id=group_id,
            )

        for row in eval_rows:
            application = f"评测集：{row.dataset_name}"
            group_id = f"evaluation:{row.dataset_id}"
            add_record(
                scene="evaluation",
                created_at=row.created_at,
                team_id=row.team_id,
                team_name=row.team_name,
                application=application,
                product_id=None,
                product_name=None,
                project_id=None,
                project_name=None,
                project_app_id=None,
                project_app_name=None,
                input_tokens=row.input_tokens,
                output_tokens=row.output_tokens,
                total_tokens=row.total_tokens,
                estimated_cost=row.estimated_cost,
                token_usage=row.token_usage,
                group_id=group_id,
            )

        row_items = []
        for item in groups.values():
            coverage = 100 if item["has_usage"] else 0
            row_items.append(
                {
                    **{key: value for key, value in item.items() if key not in {"models", "estimated_cost", "has_usage"}},
                    "estimated_cost": float(item["estimated_cost"]),
                    "models": _serialize_models(item["models"]),
                    "coverage": coverage,
                    "coverage_status": "complete" if coverage == 100 else "partial",
                }
            )
        row_items.sort(key=lambda item: (-(item["total_tokens"] or 0), item["application"]))

        summary = {
            "input_tokens": sum(item["input_tokens"] for item in groups.values()),
            "output_tokens": sum(item["output_tokens"] for item in groups.values()),
            "total_tokens": sum(item["total_tokens"] for item in groups.values()),
            "estimated_cost": float(sum((item["estimated_cost"] for item in groups.values()), Decimal("0"))),
            "chat_tokens": sum(item["chat_tokens"] for item in groups.values()),
            "evaluation_tokens": sum(item["evaluation_tokens"] for item in groups.values()),
        }
        trend_items = []
        for item in sorted(trend.values(), key=lambda value: value["date"]):
            trend_items.append(
                {
                    **item,
                    "estimated_cost": float(item["estimated_cost"]),
                }
            )
        return {
            "summary": summary,
            "rows": row_items,
            "trend": trend_items,
            "start_date": start_at.date().isoformat(),
            "end_date": end_at.date().isoformat(),
            "granularity": normalized_granularity,
            "updated_at": utc_now().isoformat(),
        }

    @staticmethod
    def _empty_response(start_at: datetime, end_at: datetime, granularity: str) -> dict[str, Any]:
        return {
            "summary": {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "estimated_cost": 0,
                "chat_tokens": 0,
                "evaluation_tokens": 0,
            },
            "rows": [],
            "trend": [],
            "start_date": start_at.date().isoformat(),
            "end_date": end_at.date().isoformat(),
            "granularity": granularity,
            "updated_at": utc_now().isoformat(),
        }


model_usage_service = ModelUsageService()
