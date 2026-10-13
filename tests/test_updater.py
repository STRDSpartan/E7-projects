"""Mise à jour via les releases GitHub : version, installateur, téléchargement vérifié."""

from __future__ import annotations

import hashlib
import time
from typing import Any

import httpx

from e7showcase.app import updater
from e7showcase.app.updater import Updater, check, newer, parse_version

BLOB = b"MZ" + b"\0" * 5000


def release(tag: str, digest: str | None = None) -> dict[str, Any]:
    exe = f"Zealot-Setup-{tag.lstrip('v')}.exe"
    return {
        "tag_name": tag,
        "body": "notes",
        "assets": [
            {
                "name": "Zealot-portable.zip",
                "size": 1,
                "browser_download_url": "https://github.com/x/y/releases/download/z/portable.zip",
            },
            {
                "name": exe,
                "size": len(BLOB),
                "digest": digest,
                "browser_download_url": f"https://github.com/x/y/releases/download/z/{exe}",
            },
        ],
    }


def client(rel: dict[str, Any]) -> httpx.Client:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.host == "api.github.com":
            return httpx.Response(200, json=rel)
        return httpx.Response(200, content=BLOB)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_versions() -> None:
    assert parse_version("v0.61.0") == (0, 61, 0)
    assert newer("0.62.0", "0.61.9") and not newer("0.61.0", "0.61.0")
    assert not newer("v0.9.0", "0.10.0")


def test_check_reports_newer_release() -> None:
    info = check(client(release("v999.0.0")))
    assert info["available"] and info["latest"] == "999.0.0"
    assert info["asset"]["name"] == "Zealot-Setup-999.0.0.exe"
    assert not check(client(release("0.0.1")))["available"]


def _wait(up: Updater) -> dict[str, Any]:
    for _ in range(200):
        if up.status["state"] not in ("checking", "downloading"):
            break
        time.sleep(0.02)
    return up.status


def test_install_downloads_verifies_and_launches(monkeypatch: Any, tmp_path: Any) -> None:
    launched: list[str] = []
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(Updater, "_launch", lambda self, path: launched.append(path.name))
    good = "sha256:" + hashlib.sha256(BLOB).hexdigest()
    up = Updater()
    up.install(lambda: client(release("v999.0.0", good)))
    st = _wait(up)
    assert st["state"] == "installing" and launched == ["Zealot-Setup-999.0.0.exe"]


def test_install_rejects_corrupted_installer(monkeypatch: Any, tmp_path: Any) -> None:
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(Updater, "_launch", lambda self, path: None)
    up = Updater()
    up.install(lambda: client(release("v999.0.0", "sha256:" + "0" * 64)))
    st = _wait(up)
    assert st["state"] == "error" and "SHA-256" in st["error"]
    assert not list(tmp_path.glob("*.exe"))
