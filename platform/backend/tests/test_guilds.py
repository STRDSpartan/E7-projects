from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

MakeUser = Callable[[str], TestClient]


def _guild(leader: TestClient, is_open: bool = False) -> None:
    r = leader.post("/api/guilds", json={"name": "Les Veilleurs", "tag": "vlr", "is_open": is_open})
    assert r.status_code == 201, r.text
    assert r.json()["tag"] == "VLR"


def test_join_request_roles_and_leave(make_user: MakeUser) -> None:
    alice, bob, carol = make_user("alice"), make_user("bob"), make_user("carol")
    _guild(alice)
    assert (
        bob.post("/api/guilds/VLR/join", json={"message": "salut"}).json()["status"] == "requested"
    )
    reqs = alice.get("/api/guilds/VLR/requests").json()
    assert bob.get("/api/guilds/VLR/requests").status_code == 403
    alice.post(f"/api/guilds/VLR/requests/{reqs[0]['id']}/accept")
    members = {m["user"]["username"]: m["role"] for m in bob.get("/api/guilds/VLR/members").json()}
    assert members == {"alice": "leader", "bob": "member"}
    assert bob.patch("/api/guilds/VLR/members/alice", json={"role": "member"}).status_code == 403
    assert alice.patch("/api/guilds/VLR/members/bob", json={"role": "officer"}).status_code == 200
    # un officier ne peut pas expulser le chef
    assert bob.delete("/api/guilds/VLR/members/alice").status_code == 403
    assert alice.post("/api/guilds/VLR/leave").status_code in (400, 409)  # chef : passer la main
    alice.patch("/api/guilds/VLR/members/bob", json={"role": "leader"})
    assert alice.post("/api/guilds/VLR/leave").status_code == 204
    assert carol.get("/api/guilds/VLR").json()["members_count"] == 1


def test_chat_http_and_websocket(make_user: MakeUser) -> None:
    alice, bob, outsider = make_user("alice"), make_user("bob"), make_user("eve")
    _guild(alice, is_open=True)
    assert bob.post("/api/guilds/VLR/join", json={}).json()["status"] == "member"
    channels = bob.get("/api/guilds/VLR/channels").json()
    general = next(c for c in channels if c["name"] == "général")
    assert outsider.get(f"/api/channels/{general['id']}/messages").status_code == 403
    with bob.websocket_connect(f"/api/ws/channels/{general['id']}") as ws:
        r = alice.post(f"/api/channels/{general['id']}/messages", json={"body": "GvG ce soir"})
        assert r.status_code == 201, r.text
        event = ws.receive_json()
        assert "GvG ce soir" in str(event)
    history = bob.get(f"/api/channels/{general['id']}/messages").json()
    assert history[-1]["body"] == "GvG ce soir"


def test_officer_channel_hidden_from_members(make_user: MakeUser) -> None:
    alice, bob = make_user("alice"), make_user("bob")
    _guild(alice, is_open=True)
    bob.post("/api/guilds/VLR/join", json={})
    r = alice.post("/api/guilds/VLR/channels", json={"name": "officiers", "officers_only": True})
    assert r.status_code == 201, r.text
    assert "officiers" not in [c["name"] for c in bob.get("/api/guilds/VLR/channels").json()]
    assert bob.post("/api/guilds/VLR/channels", json={"name": "x"}).status_code == 403


def test_forum(make_user: MakeUser) -> None:
    alice, bob = make_user("alice"), make_user("bob")
    _guild(alice, is_open=True)
    bob.post("/api/guilds/VLR/join", json={})
    threads = bob.get("/api/guilds/VLR/threads").json()
    assert threads and threads[0]["pinned"]  # fil d'accueil épinglé
    announce = {"title": "Règles", "category": "annonces", "body": "..."}
    assert bob.post("/api/guilds/VLR/threads", json=announce).status_code == 403
    r = bob.post(
        "/api/guilds/VLR/threads",
        json={"title": "Build Arby", "category": "builds", "body": "Vos avis ?"},
    )
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    assert (
        alice.post(f"/api/threads/{tid}/posts", json={"body": "Vitesse d'abord"}).status_code == 201
    )
    assert alice.patch(f"/api/threads/{tid}", json={"locked": True}).status_code == 200
    assert bob.post(f"/api/threads/{tid}/posts", json={"body": "ok"}).status_code == 403
    detail = bob.get(f"/api/threads/{tid}").json()
    assert len(detail["posts"]) == 2
