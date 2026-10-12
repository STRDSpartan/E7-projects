"""Publication des vitrines dans un salon Discord via webhook (aucun bot requis)."""

from __future__ import annotations

import json
import mimetypes
import re
import time
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
                f"files[{i}]": (
                    p.name,
                    h,
                    mimetypes.guess_type(p.name)[0] or "application/octet-stream",
                )
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


# Adresse d'un webhook Discord : https://discord.com/api/webhooks/<id>/<jeton>
WEBHOOK_RE = re.compile(
    r"^https://(?:(?:ptb|canary)\.)?(?:discord|discordapp)\.com/api(?:/v\d+)?/webhooks/"
    r"(\d{5,30})/([A-Za-z0-9_-]{20,120})$"
)
MAX_RETRY_WAIT = 10.0  # s : attente maximale imposée par Discord (limite de débit, code 429)


def valid_webhook(url: str) -> bool:
    return bool(WEBHOOK_RE.fullmatch(url.strip()))


def mask_webhook(url: str) -> str:
    """Adresse affichable : identifiant du webhook, jeton masqué."""
    m = WEBHOOK_RE.fullmatch(url.strip())
    return f"webhook {m[1][:4]}…{m[1][-4:]} (jeton masqué)" if m else ""


def post_messages(
    webhook_url: str,
    messages: list[str],
    *,
    username: str = "E7 Showcase",
    timeout: float = 30,
    transport: httpx.BaseTransport | None = None,
) -> int:
    """Envoie des messages texte (≤ 2 000 caractères chacun), dans l'ordre ; renvoie leur nombre.

    Aucune mention n'est déclenchée (@everyone, rôles, membres) ; une limite de débit (429)
    est respectée une fois en attendant le délai demandé par Discord.
    """
    if not valid_webhook(webhook_url):
        raise ValueError("adresse de webhook Discord invalide")
    sent = 0
    with httpx.Client(timeout=timeout, transport=transport) as client:
        for text in messages:
            payload = {
                "username": username,
                "content": text[:2000],
                "allowed_mentions": {"parse": []},
            }
            r = client.post(webhook_url.strip(), json=payload)
            if r.status_code == 429:
                try:
                    wait = float(r.json().get("retry_after", 1))
                except ValueError:
                    wait = 1.0
                time.sleep(min(max(wait, 0.0), MAX_RETRY_WAIT))
                r = client.post(webhook_url.strip(), json=payload)
            r.raise_for_status()
            sent += 1
    return sent
