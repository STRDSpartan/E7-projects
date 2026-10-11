"""Point d'entrée de l'application : `e7showcase-app [vitrine.e7v]`.

Lance le serveur local puis ouvre l'interface dans la fenêtre native de l'application
(pywebview + WebView2) ; il n'y a pas de version navigateur. Un fichier .e7v passé en
argument (double-clic sur le fichier) est ajouté aux vitrines reçues et affiché
directement.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from e7showcase.app.server import AppState, start_server
from e7showcase.app.vitrine_file import (
    SUFFIX,
    VitrineFileError,
    export_profile,
    import_vitrine_file,
    suggested_filename,
)
from e7showcase.config import data_dir

log = logging.getLogger(__name__)


class WindowApi:
    """Fonctions natives appelées depuis l'interface (fenêtre pywebview uniquement).

    pywebview expose à JavaScript tout attribut PUBLIC de cet objet en le parcourant
    récursivement : l'état et la fenêtre doivent rester privés (préfixe « _ »), sinon il
    explore la fenêtre native elle-même et l'application se fige au chargement.
    """

    def __init__(self, state: AppState):
        self._state = state
        self._window: Any = None

    def save_vitrine(self, profile_id: str) -> str | None:
        import webview

        player = self._state.store.load(profile_id).player
        chosen = self._window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=suggested_filename(player),
            file_types=(f"Vitrine E7 Showcase (*{SUFFIX})",),
        )
        if not chosen:
            return None
        target = Path(chosen if isinstance(chosen, str) else chosen[0])
        if target.suffix.lower() != SUFFIX:
            target = target.with_suffix(SUFFIX)
        target.write_bytes(export_profile(self._state.store, profile_id))
        return str(target)


def main(argv: list[str] | None = None) -> int:
    log_kwargs: dict[str, Any] = {
        "level": logging.INFO,
        "format": "%(asctime)s %(levelname)s %(message)s",
    }
    if sys.stderr is None:  # exécutable fenêtré (Windows) : pas de console → journal fichier
        log_kwargs["filename"] = str(data_dir() / "e7showcase.log")
        log_kwargs["encoding"] = "utf-8"
    logging.basicConfig(**log_kwargs)
    args = sys.argv[1:] if argv is None else argv
    files = [Path(a) for a in args if not a.startswith("--")]

    state = AppState(data_dir())
    start_id = ""
    for path in files:
        try:
            start_id = import_vitrine_file(state.store, path)
            log.info("Vitrine ouverte : %s", path.name)
        except (OSError, VitrineFileError) as exc:
            log.error("Impossible d'ouvrir %s : %s", path, exc)

    server = start_server(state)
    url = f"http://127.0.0.1:{server.server_address[1]}/" + (f"#p={start_id}" if start_id else "")
    try:
        import webview
    except ImportError:
        server.shutdown()
        _fatal("Composant d'affichage manquant (pywebview). Réinstallez E7 Showcase.")
        return 1

    api = WindowApi(state)
    webview.settings["ALLOW_DOWNLOADS"] = True
    window = webview.create_window("E7 Showcase", url, js_api=api, width=1360, height=860)
    api._window = window  # noqa: SLF001 - jamais exposé à JavaScript
    window.events.loaded += lambda: log.info("Fenêtre chargée [window-loaded]")
    try:
        webview.start()
    except Exception:  # noqa: BLE001 - composant d'affichage absent (WebView2)
        log.exception("Fenêtre native indisponible")
        server.shutdown()
        _fatal(
            "Impossible d'ouvrir la fenêtre d'E7 Showcase : le composant Microsoft Edge WebView2 "
            "est absent ou endommagé. Installez-le depuis "
            "https://go.microsoft.com/fwlink/p/?LinkId=2124703 puis relancez l'application."
        )
        return 1
    server.shutdown()
    return 0


def _fatal(message: str) -> None:
    """Prévenir l'utilisateur d'une erreur bloquante (boîte de dialogue sous Windows)."""
    log.error(message)
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, "E7 Showcase", 0x10)
    else:
        print(message, file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
