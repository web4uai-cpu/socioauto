"""Media upload endpoint: lets an authenticated user attach their own audio/video/image to a
post. Files are validated (type + size) and stored via the `MediaStorage` abstraction.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from src.api.deps import enforce_rate_limit, get_current_user
from src.db.models import User
from src.storage import MediaValidationError, media_storage

router = APIRouter(
    prefix="/api/v1/media", tags=["media"], dependencies=[Depends(enforce_rate_limit)]
)


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_media(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Accept a multipart file upload and return its storage id/url for use in a post."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    try:
        record = media_storage.save(
            filename=file.filename or "upload",
            content_type=file.content_type or "application/octet-stream",
            data=data,
        )
    except MediaValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {
        "id": record.id,
        "url": record.url,
        "content_type": record.content_type,
        "kind": record.kind,
    }
