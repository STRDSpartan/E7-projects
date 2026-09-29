from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("E7S_DATABASE_URL", "sqlite://")  # avant l'import de app.main

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

PASSWORD = "motdepasse42"


@pytest.fixture
def api(tmp_path: Path) -> FastAPI:
    settings = Settings(database_url="sqlite://", media_dir=tmp_path / "media")
    return create_app(settings, create_tables=True)


@pytest.fixture
def make_user(api: FastAPI) -> Iterator[Callable[[str], TestClient]]:
    """Fabrique un client HTTP connecté (un cookie de session par utilisateur)."""
    clients: list[TestClient] = []

    def make(username: str) -> TestClient:
        client = TestClient(api)
        clients.append(client)
        r = client.post(
            "/api/auth/register",
            json={"username": username, "email": f"{username}@example.com", "password": PASSWORD},
        )
        assert r.status_code == 201, r.text
        return client

    yield make
    for c in clients:
        c.close()
