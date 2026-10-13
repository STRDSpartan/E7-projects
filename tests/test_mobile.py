"""Portage mobile : le cœur démarre sans sous-processus et sert l'interface."""

from __future__ import annotations

import urllib.request
from pathlib import Path

from e7showcase.mobile.app import start_backend


def test_mobile_backend_serves_ui(tmp_path: Path) -> None:
    server, url = start_backend(tmp_path / "data")
    try:
        assert url.endswith("/#mobile")
        with urllib.request.urlopen(url.split("#")[0]) as res:
            assert b"Zealot" in res.read()
    finally:
        server.shutdown()
