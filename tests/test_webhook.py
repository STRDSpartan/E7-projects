from pathlib import Path

import httpx
import pytest

from e7showcase.publish import webhook


def test_post_images_batches_by_ten(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    images = []
    for i in range(12):
        p = tmp_path / f"img{i}.png"
        p.write_bytes(b"\x89PNG")
        images.append(p)
    calls: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.content)
        return httpx.Response(204)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(webhook.httpx, "post", client.post)
    webhook.post_images("https://discord.test/api/webhooks/x", images, content="Salut")
    assert len(calls) == 2
    assert b"payload_json" in calls[0] and b"Salut" in calls[0]
    assert calls[0].count(b'name="files[') == 10 and calls[1].count(b'name="files[') == 2


def test_missing_webhook_url() -> None:
    with pytest.raises(ValueError):
        webhook.post_images("", [])
