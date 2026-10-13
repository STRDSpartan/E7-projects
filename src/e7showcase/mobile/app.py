"""Application mobile Zealot (Toga) : serveur local + WebView plein écran sur `ui.html`."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def start_backend(data: Path) -> tuple[Any, str]:
    """Démarre l'état de l'app et le serveur local ; renvoie (serveur, adresse de l'interface)."""
    data.mkdir(parents=True, exist_ok=True)
    from e7showcase.app.server import AppState, start_server

    state = AppState(data)
    server = start_server(state)
    url = f"http://127.0.0.1:{server.server_address[1]}/#mobile"
    return server, url


def main() -> Any:
    import toga

    class Zealot(toga.App):  # type: ignore[misc]
        def startup(self) -> None:
            data = Path(self.paths.data)
            os.environ.setdefault("E7_DATA_DIR", str(data))
            os.environ.setdefault("E7_NO_PROCESSES", "1")  # pas de sous-processus sur mobile
            logging.basicConfig(level=logging.INFO)
            self.server, url = start_backend(data)
            log.info("Interface mobile : %s", url)
            self.main_window = toga.MainWindow(title=self.formal_name)
            self.main_window.content = toga.WebView(url=url, style=toga.style.Pack(flex=1))
            self.main_window.show()

        def on_exit(self) -> bool:
            server = getattr(self, "server", None)
            if server is not None:
                server.shutdown()
            return True

    return Zealot("Zealot", "com.shatteredspartan.zealot")
