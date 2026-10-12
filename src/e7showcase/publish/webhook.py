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


def _call(client: httpx.Client, method: str, url: str, **kw: object) -> httpx.Response:
    """Requête vers Discord ; une limite de débit (429) est respectée une fois."""
    r = client.request(method, url, **kw)  # type: ignore[arg-type]
    if r.status_code == 429:
        try:
            wait = float(r.json().get("retry_after", 1))
        except ValueError:
            wait = 1.0
        time.sleep(min(max(wait, 0.0), MAX_RETRY_WAIT))
        r = client.request(method, url, **kw)  # type: ignore[arg-type]
    return r


def _payload(text: str, username: str) -> dict[str, object]:
    return {"username": username, "content": text[:2000], "allowed_mentions": {"parse": []}}


def post_messages(
    webhook_url: str,
    messages: list[str],
    *,
    username: str = "E7 Showcase",
    timeout: float = 30,
    transport: httpx.BaseTransport | None = None,
) -> list[str]:
    """Publie des messages texte (≤ 2 000 caractères chacun), dans l'ordre ; renvoie leurs id.

    Aucune mention n'est déclenchée (@everyone, rôles, membres).
    """
    if not valid_webhook(webhook_url):
        raise ValueError("adresse de webhook Discord invalide")
    url = webhook_url.strip()
    ids: list[str] = []
    with httpx.Client(timeout=timeout, transport=transport) as client:
        for text in messages:
            r = _call(client, "POST", url, params={"wait": "true"}, json=_payload(text, username))
            r.raise_for_status()
            ids.append(_message_id(r))
    return ids


def sync_messages(
    webhook_url: str,
    messages: list[str],
    previous: list[str],
    *,
    username: str = "E7 Showcase",
    timeout: float = 30,
    transport: httpx.BaseTransport | None = None,
) -> list[str]:
    """Met à jour les messages déjà publiés par ce webhook au lieu d'en poster de nouveaux.

    Un message existant est modifié ; s'il a été supprimé dans Discord (404), il est republié ;
    les messages en trop sont supprimés. Renvoie les id des messages à jour.
    """
    if not valid_webhook(webhook_url):
        raise ValueError("adresse de webhook Discord invalide")
    url = webhook_url.strip()
    ids: list[str] = []
    with httpx.Client(timeout=timeout, transport=transport) as client:
        for i, text in enumerate(messages):
            body = _payload(text, username)
            old = (
                previous[i]
                if i < len(previous) and re.fullmatch(r"\d{5,30}", previous[i])
                else None
            )
            if old:
                edit = {k: body[k] for k in ("content", "allowed_mentions")}
                r = _call(client, "PATCH", f"{url}/messages/{old}", json=edit)
                if r.status_code != 404:
                    r.raise_for_status()
                    ids.append(old)
                    continue
            r = _call(client, "POST", url, params={"wait": "true"}, json=body)
            r.raise_for_status()
            ids.append(_message_id(r))
        for old in previous[len(messages) :]:
            if re.fullmatch(r"\d{5,30}", old):
                r = _call(client, "DELETE", f"{url}/messages/{old}")
                if r.status_code not in (204, 404):
                    r.raise_for_status()
    return ids


def _message_id(response: httpx.Response) -> str:
    try:
        value = str(response.json().get("id", ""))
    except ValueError:
        return ""
    return value if re.fullmatch(r"\d{5,30}", value) else ""
