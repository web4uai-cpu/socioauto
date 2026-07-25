"""Local-disk media storage for user-uploaded audio/video/image files.

Implements the ``MediaStorage`` protocol so a real object store (S3/R2) can be swapped in later
without touching callers — mirrors the ``PlatformClient`` protocol pattern in `src/platforms/`.
"""

from __future__ import annotations

import mimetypes
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

ALLOWED_KIND_PREFIXES = ("image/", "audio/", "video/")


class MediaValidationError(ValueError):
    """Raised when an upload fails content-type or size validation."""


@dataclass
class MediaRecord:
    id: str
    url: str
    content_type: str
    kind: str


class MediaStorage(Protocol):
    def save(self, *, filename: str, content_type: str, data: bytes) -> MediaRecord: ...


def _kind_for(content_type: str) -> str:
    for prefix in ALLOWED_KIND_PREFIXES:
        if content_type.startswith(prefix):
            return prefix.rstrip("/")
    raise MediaValidationError(
        f"Unsupported content type '{content_type}'; only image/audio/video are allowed"
    )


class LocalMediaStorage:
    """Stores uploads on local disk under ``MEDIA_ROOT``, served back at ``/media/<id><ext>``."""

    def __init__(self, root: str | None = None, max_upload_mb: int | None = None) -> None:
        self.root = Path(root or os.environ.get("MEDIA_ROOT", "./data/media"))
        self.max_upload_bytes = (
            (max_upload_mb or int(os.environ.get("MAX_UPLOAD_MB", "50"))) * 1024 * 1024
        )
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, *, filename: str, content_type: str, data: bytes) -> MediaRecord:
        kind = _kind_for(content_type)
        if len(data) > self.max_upload_bytes:
            raise MediaValidationError(
                f"File exceeds the {self.max_upload_bytes // (1024 * 1024)}MB upload limit"
            )
        ext = Path(filename).suffix or mimetypes.guess_extension(content_type) or ""
        media_id = uuid.uuid4().hex
        target = self.root / f"{media_id}{ext}"
        target.write_bytes(data)
        return MediaRecord(
            id=media_id, url=f"/media/{media_id}{ext}", content_type=content_type, kind=kind
        )


media_storage = LocalMediaStorage()
