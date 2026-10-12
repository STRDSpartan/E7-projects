"""Écran de fin de combat GvG : lecture des stats (OCR réel, texte seul) et des portraits."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import numpy as np
import pytest
from PIL import Image, ImageDraw

from e7showcase.parsers.battle_report import parse_report
from e7showcase.vision.ocr import OcrLine

FIXTURE = Path(__file__).parent / "fixtures" / "gvg_battle_report_ocr.json"


def lines() -> list[OcrLine]:
    rows = json.loads(FIXTURE.read_text("utf-8"))
    return [OcrLine(t, 1.0, b[1], (b[0], b[1], b[2], b[3])) for t, b in rows]


def test_parse_report_reads_every_visible_stat() -> None:
    report = parse_report(lines())
    assert report is not None and report.teams == [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11]]
    assert len(report.sets) == 2 and report.step == pytest.approx(22.5, abs=1)
    known = [c for c in report.columns if c.known]
    assert [round(c.x) for c in known] == [579, 677, 776, 1616, 1714, 1816]
    assert known[0].values == {
        "atk": 2828, "def": 1444, "hp": 20703, "spd": 221, "crit_chance": 19,
        "crit_dmg": 150, "effectiveness": 5, "effect_res": 66, "dual_attack": 3,
    }  # fmt: skip
    assert known[3].values["crit_dmg"] == 279 and known[5].values["effect_res"] == 0
    hidden = [c for c in report.columns if not c.known]
    assert [c.values["hp"] for c in hidden] == [9706, 18445, 22617, 28387, 18399, 30971]
    assert all(c.values["atk"] is None and c.values["crit_chance"] is None for c in hidden)


def test_parse_report_rejects_other_screens() -> None:
    assert parse_report([OcrLine("Attaque", 1.0, 0, (0, 0, 50, 20))]) is None


def face(seed: int) -> Image.Image:
    rnd = np.random.default_rng(seed)
    img = Image.new("RGBA", (112, 112), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, 111, 111), fill=tuple(int(v) for v in rnd.integers(40, 220, 3)) + (255,))
    for _ in range(14):  # « traits » aléatoires propres à chaque héros
        x, y = (int(v) for v in rnd.integers(10, 90, 2))
        d.ellipse(
            (x, y, x + 22, y + 22), fill=tuple(int(v) for v in rnd.integers(0, 255, 3)) + (255,)
        )
    return img


def test_face_matcher_recognises_framed_darkened_portrait(tmp_path: Path) -> None:
    from e7showcase.vision.hero_faces import Circle, FaceMatcher

    folder = tmp_path / "faces"
    folder.mkdir()
    for i in range(30):
        face(i).save(folder / f"c{1000 + i}.webp")
    screen = Image.new("RGB", (400, 200), (30, 40, 60))
    portrait = face(17).resize((76, 76))
    screen.paste(portrait, (100, 60), portrait)
    d = ImageDraw.Draw(screen)
    d.ellipse((96, 56, 180, 140), outline=(200, 170, 90), width=4)  # cadre doré
    d.rectangle((100, 60, 118, 78), fill=(220, 220, 220))  # icône de classe
    dark = screen.point(lambda v: int(v * 0.55))  # héros vaincu : assombri
    matcher = FaceMatcher(folder)
    for img in (screen, dark):
        best = matcher.match(img, Circle(138, 98, 38))
        assert best[0][0] == "c1017" and best[0][1] > best[1][1] + 0.1
    assert matcher.count() == 30


def test_sync_faces_downloads_missing_icons(tmp_path: Path) -> None:
    import io

    from e7showcase.assets import AssetStore
    from e7showcase.sources.e7codex import face_jobs, sync_faces

    buf = io.BytesIO()
    face(1).save(buf, "PNG")
    seen: list[str] = []

    def server(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["User-Agent"])
        return httpx.Response(200, content=buf.getvalue())

    jobs = face_jobs()
    store = AssetStore(tmp_path)
    (tmp_path / "faces").mkdir()
    Image.new("RGB", (8, 8)).save(tmp_path / "faces" / f"{jobs[0][0]}.webp")  # déjà présent
    progress: list[int] = []
    with httpx.Client(transport=httpx.MockTransport(server)) as client:
        report = sync_faces(store, client, delay=0, on_progress=lambda d, t: progress.append(d))
    assert len(report.downloaded) == len(jobs) - 1 and report.skipped == [jobs[0][0]]
    assert progress[-1] == len(jobs) and all("e7showcase" in ua for ua in seen)
    assert len(list((tmp_path / "faces").glob("*.webp"))) == len(jobs)
