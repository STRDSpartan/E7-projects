"""Publication des vitrines dans un salon Discord via webhook (aucun bot requis)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

MAX_FILES_PER_MESSAGE = 10


def post_images(
    webhook_url: str,
    images: list[Path],
    *,
    content: str = "",
    username: str = "E7 Showcase",
    timeout: float = 30,
) -> None:
    if not webhook_url:
        raise ValueError("E7_DISCORD_WEBHOOK_URL n'est pas défini.")
    for start in range(0, len(images), MAX_FILES_PER_MESSAGE):
        batch = images[start : start + MAX_FILES_PER_MESSAGE]
        payload = {"username": username, "content": content if start == 0 else ""}
        handles = [p.open("rb") for p in batch]
        try:
            files = {
                f"files[{i}]": (p.name, h, "image/png")
                for i, (p, h) in enumerate(zip(batch, handles, strict=True))
            }
            r = httpx.post(
                webhook_url,
                data={"payload_json": json.dumps(payload)},
                files=files,
                timeout=timeout,
            )
            r.raise_for_status()
        finally:
            for h in handles:
                h.close()
