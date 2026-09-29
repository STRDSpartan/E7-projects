from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

MakeUser = Callable[[str], TestClient]

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def test_friend_flow(make_user: MakeUser) -> None:
    alice, bob = make_user("alice"), make_user("bob")
    assert alice.post("/api/friends/requests", json={"username": "bob"}).status_code == 201
    assert bob.get("/api/users/alice").json()["relationship"] == "request_received"
    incoming = bob.get("/api/friends/requests").json()
    assert incoming[0]["direction"] == "incoming"
    assert bob.post(f"/api/friends/requests/{incoming[0]['id']}/accept").status_code == 200
    assert [u["username"] for u in alice.get("/api/friends").json()] == ["bob"]
    assert bob.get("/api/notifications").json()  # demande reçue notifiée
    assert alice.delete("/api/friends/bob").status_code == 204
    assert alice.get("/api/friends").json() == []


def test_reciprocal_request_auto_accepts(make_user: MakeUser) -> None:
    alice, bob = make_user("alice"), make_user("bob")
    alice.post("/api/friends/requests", json={"username": "bob"})
    bob.post("/api/friends/requests", json={"username": "alice"})
    assert alice.get("/api/users/bob").json()["relationship"] == "friends"


def test_post_visibility_likes_comments(make_user: MakeUser) -> None:
    alice, bob, carol = make_user("alice"), make_user("bob"), make_user("carol")
    alice.post("/api/friends/requests", json={"username": "bob"})
    bob.post("/api/friends/requests", json={"username": "alice"})
    r = alice.post("/api/posts", json={"kind": "text", "body": "amis", "visibility": "friends"})
    assert r.status_code == 201
    pid = r.json()["id"]
    assert bob.get(f"/api/posts/{pid}").status_code == 200
    assert carol.get(f"/api/posts/{pid}").status_code == 404
    assert [p["id"] for p in bob.get("/api/feed").json()] == [pid]
    assert carol.get("/api/explore").json() == []
    assert bob.post(f"/api/posts/{pid}/like").json()["likes"] == 1
    assert bob.post(f"/api/posts/{pid}/comments", json={"body": "GG"}).status_code == 201
    assert alice.get(f"/api/posts/{pid}").json()["comments"] == 1
    assert bob.delete(f"/api/posts/{pid}").status_code in (403, 404)
    assert alice.delete(f"/api/posts/{pid}").status_code == 204


def test_post_kind_validation(make_user: MakeUser) -> None:
    alice = make_user("alice")
    bad_clip = {"kind": "clip", "media_url": "https://evil.example/x.mp4"}
    assert alice.post("/api/posts", json=bad_clip).status_code in (400, 422)
    assert alice.post("/api/posts", json={"kind": "vitrine"}).status_code in (400, 422)


def test_media_upload_checks_signature(make_user: MakeUser) -> None:
    alice = make_user("alice")
    ok = alice.post("/api/media", files={"file": ("a.png", PNG, "image/png")})
    assert ok.status_code == 201, ok.text
    url = ok.json()["url"]
    assert alice.get(url).content == PNG
    fake = alice.post("/api/media", files={"file": ("a.png", b"<script>", "image/png")})
    assert fake.status_code == 415
    svg = alice.post("/api/media", files={"file": ("a.svg", b"<svg/>", "image/svg+xml")})
    assert svg.status_code == 415
    post = alice.post(
        "/api/posts", json={"kind": "achievement", "title": "Rang Légende", "media_url": url}
    )
    assert post.status_code == 201, post.text
