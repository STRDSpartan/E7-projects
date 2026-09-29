from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.conftest import PASSWORD

MakeUser = Callable[[str], TestClient]


def test_register_login_logout(api: FastAPI, make_user: MakeUser) -> None:
    alice = make_user("alice")
    assert alice.get("/api/auth/me").json()["username"] == "alice"
    assert alice.post("/api/auth/logout").status_code == 204
    assert alice.get("/api/auth/me").status_code == 401

    anon = TestClient(api)
    assert (
        anon.post("/api/auth/login", json={"login": "alice", "password": "faux"}).status_code == 401
    )
    r = anon.post("/api/auth/login", json={"login": "alice@example.com", "password": PASSWORD})
    assert r.status_code == 200
    assert anon.get("/api/auth/me").status_code == 200


def test_register_rejects_weak_password_and_duplicates(api: FastAPI, make_user: MakeUser) -> None:
    make_user("alice")
    anon = TestClient(api)
    weak = {"username": "bob", "email": "bob@example.com", "password": "court"}
    assert anon.post("/api/auth/register", json=weak).status_code in (400, 422)
    dup = {"username": "Alice", "email": "x@example.com", "password": PASSWORD}
    assert anon.post("/api/auth/register", json=dup).status_code in (400, 409)


def test_search_and_profile(make_user: MakeUser) -> None:
    alice = make_user("alice")
    make_user("alicia")
    alice.patch("/api/users/me", json={"display_name": "Alice", "bio": "Main Ray"})
    names = [u["username"] for u in alice.get("/api/users/search", params={"q": "ali"}).json()]
    assert set(names) == {"alice", "alicia"}
    profile = alice.get("/api/users/alice").json()
    assert profile["relationship"] == "self"
    assert profile["user"]["bio"] == "Main Ray"


def test_export_and_delete_account(api: FastAPI, make_user: MakeUser) -> None:
    alice = make_user("alice")
    alice.post("/api/posts", json={"kind": "text", "body": "Bonjour"})
    export = alice.get("/api/users/me/export")
    assert export.status_code == 200
    assert "Bonjour" in export.text
    assert alice.request("DELETE", "/api/users/me", json={"password": "faux"}).status_code == 403
    assert alice.request("DELETE", "/api/users/me", json={"password": PASSWORD}).status_code == 204
    anon = TestClient(api)
    assert anon.get("/api/users/alice").status_code == 404
