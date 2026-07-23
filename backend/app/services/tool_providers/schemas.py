"""Protocol-neutral schemas for external tool providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ToolProviderConfig:
    code: str
    base_url: str
    transport_type: str
    auth_type: str
    auth_header_name: str | None = None
    auth_token: str | None = None


@dataclass(frozen=True, slots=True)
class DiscoveredTool:
    external_name: str
    external_display_name: str
    description: str | None
    domain: str
    action: str
    read_only: bool
    required_permissions: list[str]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    required_context: list[str]
    raw_manifest: dict[str, Any]
    schema_hash: str


@dataclass(frozen=True, slots=True)
class ToolCallResult:
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    message: str = ""
    retryable: bool = False
    http_status: int | None = None
    duration_ms: int | None = None


class ToolProviderError(ValueError):
    """A provider configuration, transport or contract error."""
