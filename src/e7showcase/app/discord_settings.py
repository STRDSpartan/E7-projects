"""Réglages Discord de l'application et publication du plan de défense GvG.

    <dossier de données>/discord.json
        gvg_webhook   adresse du webhook du salon GvG
        auto          republier le plan à chaque modification
        message_ids   messages Discord du dernier plan publié (mis à jour au lieu d'en poster)
        last_sent, last_error   état de la dernière publication

L'adresse d'un webhook donne le droit d'écrire dans le salon : elle reste sur l'ordinateur
du joueur (jamais dans un fichier .e7v ni renvoyée en clair à l'interface).
"""

from __future__ import annotations

import contextlib
import json
import logging
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from e7showcase.publish.webhook import mask_webhook, post_messages, sync_messages, valid_webhook

log = logging.getLogger(__name__)
AUTO_DELAY = 20.0  # s : les modifications rapprochées sont regroupées en une publication


class DiscordSettings:
    def __init__(self, path: Path):
        self.path = path

    def _read(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data), encoding="utf-8")
        with contextlib.suppress(OSError):  # lisible par le seul utilisateur (hors Windows)
            self.path.chmod(0o600)

    def update(self, **changes: Any) -> None:
        data = self._read()
        data.update(changes)
        self._write(data)

    def webhook(self) -> str:
        url = self._read().get("gvg_webhook", "")
        return url if isinstance(url, str) and valid_webhook(url) else ""

    def set_webhook(self, url: str) -> None:
        url = url.strip()
        if url and not valid_webhook(url):
            raise ValueError(
                "adresse invalide : copiez l'URL du webhook depuis Discord "
                "(Paramètres du salon → Intégrations → Webhooks)"
            )
        # nouveau salon : les messages publiés par l'ancien webhook ne sont plus modifiables
        self.update(gvg_webhook=url, message_ids=[], last_error=None)

    def auto(self) -> bool:
        return bool(self._read().get("auto")) and bool(self.webhook())

    def message_ids(self) -> list[str]:
        ids = self._read().get("message_ids", [])
        return [str(i) for i in ids if isinstance(i, str | int)] if isinstance(ids, list) else []

    def status(self) -> dict[str, object]:
        data, url = self._read(), self.webhook()
        return {
            "configured": bool(url),
            "hint": mask_webhook(url),
            "auto": bool(data.get("auto")),
            "published": bool(self.message_ids()),
            "last_sent": data.get("last_sent"),
            "last_error": data.get("last_error"),
        }


class PlanPublisher:
    """Publie le plan de défense : à la demande, ou automatiquement après les modifications."""

    def __init__(
        self,
        settings: DiscordSettings,
        messages: Callable[[], list[str]],
        transport: Callable[[], Any] = lambda: None,
        delay: float = AUTO_DELAY,
    ):
        self.settings, self.messages, self.transport, self.delay = (
            settings,
            messages,
            transport,
            delay,
        )
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def send_now(self) -> int:
        """Nouvelle publication (nouveaux messages), qui devient celle mise à jour ensuite."""
        url = self.settings.webhook()
        if not url:
            raise ValueError("aucun webhook Discord enregistré")
        with self._lock:
            ids = post_messages(url, self.messages(), transport=self.transport())
            self.settings.update(message_ids=ids, last_sent=_now(), last_error=None)
        return len(ids)

    def changed(self) -> None:
        """Le plan a changé : publication automatique différée (modifications regroupées)."""
        if not self.settings.auto():
            return
        if self._timer is not None:
            self._timer.cancel()
        self._timer = threading.Timer(self.delay, self.flush)
        self._timer.daemon = True
        self._timer.start()

    def flush(self) -> None:
        """Met à jour les messages déjà publiés (ou publie le plan s'il ne l'a jamais été)."""
        self._timer = None
        url = self.settings.webhook()
        if not url:
            return
        with self._lock:
            try:
                ids = sync_messages(
                    url, self.messages(), self.settings.message_ids(), transport=self.transport()
                )
            except Exception as exc:  # noqa: BLE001 - erreur affichée dans l'interface
                log.warning("Publication automatique du plan GvG impossible : %s", exc)
                self.settings.update(last_error=_describe(exc))
                return
            self.settings.update(message_ids=ids, last_sent=_now(), last_error=None)

    def flush_pending(self) -> None:
        """Publie tout de suite une mise à jour encore en attente (fermeture de l'application)."""
        if self._timer is not None:
            self._timer.cancel()
            self.flush()

    def cancel(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None


def _now() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def _describe(exc: Exception) -> str:
    import httpx

    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return f"Discord a refusé l'envoi : erreur {code}" + (
            " (webhook supprimé ?)" if code in (401, 404) else ""
        )
    if isinstance(exc, httpx.HTTPError):
        return "Discord injoignable : vérifiez la connexion"
    return "publication impossible (voir le journal)"
