"""Mise à jour de Zealot depuis les releases GitHub du projet.

`check()` compare la dernière release publiée à la version installée ; `Updater.install()`
télécharge l'installateur Windows (`Zealot-Setup-<version>.exe`) en tâche de fond, vérifie son
empreinte SHA-256 quand GitHub la fournit, puis le lance en mode silencieux : l'installateur ferme
l'application, la met à jour (profils conservés) et la relance.
"""

from __future__ import annotations

import hashlib
import logging
import re
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from e7showcase import __version__

log = logging.getLogger(__name__)

REPO = "STRDSpartan/E7-projects"
LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET_RE = re.compile(r"^Zealot-Setup-[\d.]+\.exe$")
ALLOWED_HOSTS = (
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
)
MAX_SIZE = 600 * 1024 * 1024


class UpdateError(Exception):
    pass


def parse_version(text: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", text.lstrip("vV"))
    return tuple(int(n) for n in nums[:3]) or (0,)


def newer(remote: str, local: str = __version__) -> bool:
    return parse_version(remote) > parse_version(local)


def pick_asset(release: dict[str, Any]) -> dict[str, Any] | None:
    for asset in release.get("assets") or []:
        if isinstance(asset, dict) and ASSET_RE.match(str(asset.get("name", ""))):
            return asset
    return None


def _allowed(url: str) -> bool:
    m = re.match(r"^https://([^/]+)/", url)
    return bool(m) and m[1] in ALLOWED_HOSTS  # type: ignore[index]


def check(client: Any = None) -> dict[str, Any]:
    """Dernière release : {current, latest, available, notes, url, size}."""
    import httpx

    own = client is None
    http = client or httpx.Client(timeout=15, follow_redirects=True)
    try:
        res = http.get(LATEST, headers={"Accept": "application/vnd.github+json"})
    except httpx.HTTPError as exc:
        raise UpdateError("GitHub injoignable : vérifiez votre connexion Internet") from exc
    finally:
        if own:
            http.close()
    if res.status_code == 404:
        raise UpdateError("aucune version publiée trouvée sur GitHub")
    if res.status_code != 200:
        raise UpdateError(f"GitHub a répondu {res.status_code}")
    release = res.json()
    tag = str(release.get("tag_name") or "")
    asset = pick_asset(release)
    return {
        "current": __version__,
        "latest": tag.lstrip("vV"),
        "available": bool(tag) and newer(tag) and asset is not None,
        "notes": str(release.get("body") or "")[:4000],
        "page": str(release.get("html_url") or ""),
        "asset": asset,
    }


class Updater:
    """Téléchargement et installation en tâche de fond (un seul à la fois)."""

    def __init__(self, on_quit: Callable[[], None] | None = None):
        self.on_quit = on_quit
        self.status: dict[str, Any] = {"state": "idle", "done": 0, "total": 0, "error": None}
        self._lock = threading.Lock()

    def install(self, client_factory: Callable[[], Any] | None = None) -> None:
        with self._lock:
            if self.status["state"] in ("checking", "downloading", "installing"):
                return
            self.status = {"state": "checking", "done": 0, "total": 0, "error": None}
        threading.Thread(target=self._run, args=(client_factory,), daemon=True).start()

    def _run(self, client_factory: Callable[[], Any] | None) -> None:
        import httpx

        try:
            if sys.platform != "win32" and client_factory is None:
                raise UpdateError("mise à jour automatique disponible seulement sous Windows")
            client = (
                client_factory()
                if client_factory
                else httpx.Client(timeout=60, follow_redirects=True)
            )
            with client:
                info = check(client)
                if not info["available"]:
                    self.status = {**self.status, "state": "uptodate"}
                    return
                asset = info["asset"]
                url = str(asset.get("browser_download_url") or "")
                if not _allowed(url):
                    raise UpdateError("adresse de téléchargement inattendue")
                path = self._download(client, url, asset)
            self.status = {**self.status, "state": "installing"}
            self._launch(path)
        except (UpdateError, httpx.HTTPError, OSError) as exc:
            log.warning("Mise à jour impossible : %s", exc)
            message = str(exc) if isinstance(exc, UpdateError) else "téléchargement interrompu"
            self.status = {**self.status, "state": "error", "error": message}

    def _download(self, client: Any, url: str, asset: dict[str, Any]) -> Path:
        size = int(asset.get("size") or 0)
        if size > MAX_SIZE:
            raise UpdateError("installateur anormalement volumineux")
        self.status = {**self.status, "state": "downloading", "total": size}
        target = Path(tempfile.gettempdir()) / str(asset["name"])
        digest = hashlib.sha256()
        with client.stream("GET", url) as res, target.open("wb") as out:
            if res.status_code != 200 or not _allowed(str(res.url)):
                raise UpdateError(f"téléchargement refusé ({res.status_code})")
            done = 0
            for chunk in res.iter_bytes(1 << 16):
                done += len(chunk)
                if done > MAX_SIZE:
                    raise UpdateError("installateur anormalement volumineux")
                digest.update(chunk)
                out.write(chunk)
                self.status = {**self.status, "done": done}
        expected = str(asset.get("digest") or "")
        if expected.startswith("sha256:") and expected[7:].lower() != digest.hexdigest():
            target.unlink(missing_ok=True)
            raise UpdateError("installateur corrompu (empreinte SHA-256 différente)")
        if size and target.stat().st_size != size:
            target.unlink(missing_ok=True)
            raise UpdateError("installateur incomplet")
        return target

    def _launch(self, path: Path) -> None:
        if sys.platform == "win32":  # pragma: no cover - Windows seulement
            flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
                subprocess, "CREATE_NEW_PROCESS_GROUP", 0
            )
            subprocess.Popen(  # noqa: S603 - installateur téléchargé et vérifié ci-dessus
                [str(path), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"],
                creationflags=flags,
                close_fds=True,
            )
        log.info("Installateur lancé : %s", path.name)
        if self.on_quit is not None:
            threading.Timer(1.5, self.on_quit).start()  # l'installateur remplace les fichiers
