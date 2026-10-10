"""Point d'entrée de l'application : `e7showcase-app [vitrine.e7v]`.

Lance le serveur local puis ouvre l'interface dans une fenêtre native (pywebview) ou, à
défaut, dans le navigateur. Un fichier .e7v passé en argument (double-clic sur le fichier)
est ajouté aux vitrines reçues et affiché directement.
"""

from __future__ import annotations

import logging
import sys
import threading
import webbrowser
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
    """Fonctions natives appelées depuis l'interface (fenêtre pywebview uniquement)."""

    def __init__(self, state: AppState):
        self.state = state
        self.window: Any = None

    def save_vitrine(self, profile_id: str) -> str | None:
        import webview

        player = self.state.store.load(profile_id).player
        chosen = self.window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=suggested_filename(player),
            file_types=(f"Vitrine E7 Showcase (*{SUFFIX})",),
        )
        if not chosen:
            return None
        target = Path(chosen if isinstance(chosen, str) else chosen[0])
        if target.suffix.lower() != SUFFIX:
            target = target.with_suffix(SUFFIX)
        target.write_bytes(export_profile(self.state.store, profile_id))
        return str(target)


def main(argv: list[str] | None = None) -> int:
    log_kwargs: dict[str, Any] = {
        "level": logging.INFO,
        "format": "%(asctime)s %(levelname)s %(message)s",
    }
    if sys.stderr is None:  # exécutable fenêtré (Windows) : pas de console → journal fichier
        log_kwargs["filename"] = str(data_dir() / "e7showcase.log")
    logging.basicConfig(**log_kwargs)
    args = sys.argv[1:] if argv is None else argv
    browser = "--browser" in args
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
        if browser:
            raise ImportError
        import webview
    except ImportError:
        print(f"E7 Showcase : {url}\n(Ctrl+C pour quitter)", flush=True)
        webbrowser.open(url)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            server.shutdown()
        return 0

    api = WindowApi(state)
    webview.settings["ALLOW_DOWNLOADS"] = True
    api.window = webview.create_window("E7 Showcase", url, js_api=api, width=1360, height=860)
    webview.start()
    server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
