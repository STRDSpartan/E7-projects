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

import json
import logging
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from e7showcase.app.jsonfile import write_json
from e7showcase.publish.webhook import mask_webhook, post_messages, sync_messages, valid_webhook

log = logging.getLogger(__name__)
AUTO_FLAGS = {"plan": "auto", "wars": "auto_wars", "counters": "auto_counters"}
AUTO_DELAY = 20.0  # s : les modifications rapprochées sont regroupées en une publication


class DiscordSettings:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()  # serveur et publications différées écrivent ici

    def _read(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self, data: dict[str, Any]) -> None:
        write_json(self.path, data, private=True)

    def update(self, **changes: Any) -> None:
        with self._lock:
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
        self.update(gvg_webhook=url, message_ids=[], publications={})

    def auto(self, kind: str = "plan") -> bool:
        """Mise à jour automatique activée : `plan`, `wars` (suivi des guerres) ou `counters`."""
        flag = AUTO_FLAGS.get(kind, "auto")
        return bool(self._read().get(flag)) and bool(self.webhook())

    def publications(self) -> dict[str, dict[str, Any]]:
        pubs = self._read().get("publications", {})
        return pubs if isinstance(pubs, dict) else {}

    def message_ids(self, key: str = "plan") -> list[str]:
        """Messages Discord d'une publication (`plan`, `war:<id>`), modifiés aux mises à jour."""
        data = self._read()
        pub = self.publications().get(key, {})
        ids = pub.get("ids") if isinstance(pub, dict) else None
        if ids is None and key == "plan":
            ids = data.get("message_ids", [])  # ancien emplacement (v0.25.0)
        return [str(i) for i in ids if isinstance(i, str | int)] if isinstance(ids, list) else []

    def record(self, key: str, *, ids: list[str] | None = None, error: str | None = None) -> None:
        with self._lock:
            pubs = self.publications()
            pub = dict(pubs.get(key, {}))
            if ids is not None:
                pub.update(ids=ids, last_sent=_now(), last_error=None)
            else:
                pub["last_error"] = error
            pubs[key] = pub
            self.update(publications=pubs)

    def forget(self, key: str) -> None:
        with self._lock:
            pubs = self.publications()
            pubs.pop(key, None)
            self.update(publications=pubs)

    def status(self) -> dict[str, object]:
        data, url = self._read(), self.webhook()
        plan = self.publications().get("plan", {})
        return {
            "configured": bool(url),
            "hint": mask_webhook(url),
            "auto": bool(data.get("auto")),
            "auto_wars": bool(data.get("auto_wars")),
            "auto_counters": bool(data.get("auto_counters")),
            "counters": {
                k: v
                for k, v in self.publications().get("counters", {}).items()
                if k in ("last_sent", "last_error")
            }
            | {"published": bool(self.message_ids("counters"))},
            "published": bool(self.message_ids()),
            "last_sent": plan.get("last_sent") or data.get("last_sent"),
            "last_error": plan.get("last_error"),
            "wars": {
                k.split(":", 1)[1]: {
                    "published": bool(v.get("ids")),
                    "last_sent": v.get("last_sent"),
                    "last_error": v.get("last_error"),
                }
                for k, v in self.publications().items()
                if k.startswith("war:") and isinstance(v, dict)
            },
        }


class Publisher:
    """Publications Discord tenues à jour : plan de défense (`plan`) et guerres (`war:<id>`).

    À la demande, de nouveaux messages sont postés ; ensuite, quand la mise à jour automatique
    est activée, chaque modification relance (après `delay` secondes sans autre modification)
    la mise à jour des messages déjà publiés.
    """

    def __init__(
        self,
        settings: DiscordSettings,
        messages: Callable[[str], list[str] | None],
        transport: Callable[[], Any] = lambda: None,
        delay: float = AUTO_DELAY,
    ):
        self.settings, self.messages, self.transport, self.delay = (
            settings,
            messages,
            transport,
            delay,
        )
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def send_now(self, key: str = "plan") -> int:
        """Nouvelle publication (nouveaux messages), qui devient celle mise à jour ensuite."""
        url = self.settings.webhook()
        if not url:
            raise ValueError("aucun webhook Discord enregistré")
        texts = self.messages(key)
        if texts is None:
            raise ValueError("rien à publier")
        with self._lock:
            ids = post_messages(url, texts, transport=self.transport())
            self.settings.record(key, ids=ids)
        return len(ids)

    def changed(self, key: str = "plan") -> None:
        """Une publication a changé : mise à jour automatique différée (changements regroupés)."""
        kind = _kind(key)
        if not self.settings.auto(kind):
            return
        if kind != "plan" and not self.settings.message_ids(key):
            return  # jamais publié : on attend un premier envoi à la demande
        if old := self._timers.pop(key, None):
            old.cancel()
        timer = threading.Timer(self.delay, self.flush, args=(key,))
        timer.daemon = True
        self._timers[key] = timer
        timer.start()

    def flush(self, key: str = "plan") -> None:
        """Met à jour les messages déjà publiés (ou publie le plan s'il ne l'a jamais été)."""
        self._timers.pop(key, None)
        url = self.settings.webhook()
        if not url:
            return
        with self._lock:
            texts = self.messages(key)
            try:
                ids = sync_messages(
                    url, texts or [], self.settings.message_ids(key), transport=self.transport()
                )
            except Exception as exc:  # noqa: BLE001 - erreur affichée dans l'interface
                log.warning("Publication automatique %s impossible : %s", key, exc)
                self.settings.record(key, error=_describe(exc))
                return
            if texts is None:  # guerre supprimée : ses messages ont été effacés
                self.settings.forget(key)
            else:
                self.settings.record(key, ids=ids)

    def flush_pending(self) -> None:
        """Publie tout de suite les mises à jour encore en attente (fermeture de l'application)."""
        for key, timer in list(self._timers.items()):
            timer.cancel()
            self.flush(key)

    def cancel(self, kind: str | None = None) -> None:
        for key in list(self._timers):
            if kind is None or _kind(key) == kind:
                self._timers.pop(key).cancel()


def _kind(key: str) -> str:
    """Famille d'une publication : `plan`, `counters` ou `wars` (`war:<id>`)."""
    return key if key in ("plan", "counters") else "wars"


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
