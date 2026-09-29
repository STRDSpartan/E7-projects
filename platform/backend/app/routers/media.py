"""Envoi d'images et de vidéos (clips). Stockage local en développement, S3 en production."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.config import Settings
from app.deps import current_user, get_settings_dep
from app.models import User
from app.schemas.social import MediaOut

router = APIRouter(prefix="/api/media", tags=["media"])

# Type déclaré → (extension, catégorie, signatures d'en-tête acceptées)
ALLOWED: dict[str, tuple[str, str, tuple[bytes, ...]]] = {
    "image/png": ("png", "image", (b"\x89PNG",)),
    "image/jpeg": ("jpg", "image", (b"\xff\xd8\xff",)),
    "image/webp": ("webp", "image", (b"RIFF",)),
    "image/gif": ("gif", "image", (b"GIF8",)),
    "video/mp4": ("mp4", "video", (b"ftyp",)),  # signature à l'octet 4
    "video/webm": ("webm", "video", (b"\x1a\x45\xdf\xa3",)),
}


def _signature_ok(head: bytes, signatures: tuple[bytes, ...]) -> bool:
    return any(head.startswith(sig) or head[4:8] == sig for sig in signatures)


@router.post("", response_model=MediaOut, status_code=status.HTTP_201_CREATED)
async def upload(
    file: UploadFile,
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings_dep),
) -> MediaOut:
    spec = ALLOWED.get(file.content_type or "")
    if spec is None:
        raise HTTPException(415, "Format non accepté (PNG, JPEG, WebP, GIF, MP4, WebM).")
    ext, category, signatures = spec
    limit_mb = settings.max_video_mb if category == "video" else settings.max_image_mb
    data = await file.read(limit_mb * 1024 * 1024 + 1)
    if len(data) > limit_mb * 1024 * 1024:
        raise HTTPException(413, f"Fichier trop volumineux (max {limit_mb} Mo).")
    if not _signature_ok(data[:16], signatures):  # le contenu doit correspondre au type annoncé
        raise HTTPException(415, "Le contenu du fichier ne correspond pas à son type.")
    folder = settings.media_dir / str(user.id)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{secrets.token_hex(12)}.{ext}"
    (folder / name).write_bytes(data)
    return MediaOut(url=f"/media/{user.id}/{name}", media_type=category, size=len(data))
