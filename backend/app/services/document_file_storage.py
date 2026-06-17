"""Local staging storage for uploaded document files."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from loguru import logger

from app.core.config.settings import settings


@dataclass(frozen=True, slots=True)
class StagedDocumentFile:
    """Metadata for one staged source file."""

    path: str
    filename: str
    size: int
    content_hash: str


class DocumentFileStorage:
    """Persist original uploads until the background parser has consumed them."""

    def _root(self) -> Path:
        return Path(settings.DOCUMENT_STAGING_DIR).expanduser().resolve()

    @staticmethod
    def _safe_filename(filename: str | None) -> str:
        normalized = (filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
        return normalized or "document"

    @staticmethod
    def _extension(filename: str) -> str:
        if "." not in filename:
            return ""
        suffix = "." + filename.rsplit(".", 1)[-1].lower()
        return suffix if suffix.replace(".", "").isalnum() else ""

    def _resolve_staged_path(self, staged_file_path: str) -> Path:
        raw = (staged_file_path or "").strip()
        if not raw:
            raise ValueError("Staged file path is empty")

        root = self._root()
        path = Path(raw)
        resolved = path.expanduser().resolve() if path.is_absolute() else (root / path).resolve()
        if not resolved.is_relative_to(root):
            raise ValueError("Staged file path is outside the configured staging directory")
        return resolved

    def save_uploaded_file(
        self,
        *,
        document_id: int,
        filename: str | None,
        content: bytes,
    ) -> StagedDocumentFile:
        safe_filename = self._safe_filename(filename)
        content_hash = hashlib.sha256(content).hexdigest()
        relative_path = Path(str(int(document_id))) / f"{uuid4().hex}{self._extension(safe_filename)}"
        absolute_path = self._root() / relative_path
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.write_bytes(content)
        return StagedDocumentFile(
            path=relative_path.as_posix(),
            filename=safe_filename,
            size=len(content),
            content_hash=content_hash,
        )

    def open_staged_file(self, staged_file_path: str) -> bytes:
        return self._resolve_staged_path(staged_file_path).read_bytes()

    def delete_staged_file(self, staged_file_path: str | None) -> bool:
        if not staged_file_path:
            return False
        try:
            path = self._resolve_staged_path(staged_file_path)
            if not path.exists():
                return False
            path.unlink()
            self._remove_empty_parent_dirs(path.parent)
            return True
        except Exception as exc:
            logger.warning("Failed to delete staged document file path={}: {}", staged_file_path, exc)
            return False

    def _remove_empty_parent_dirs(self, start: Path) -> None:
        root = self._root()
        current = start.resolve()
        while current != root and current.is_relative_to(root):
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent


document_file_storage = DocumentFileStorage()
