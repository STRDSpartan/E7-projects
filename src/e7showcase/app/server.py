"""Serveur local de l'application (127.0.0.1 uniquement, bibliothèque standard).

L'interface (HTML/JS) dialogue avec ce serveur ; chaque appel /api exige le jeton de session
tiré au lancement (en-tête X-E7-Token) et l'en-tête Host est vérifié : un site web ouvert
dans le navigateur ne peut ni lire ni modifier les profils.
"""

from __future__ import annotations

import base64
import binascii
import contextlib
import io
import json
import logging
import re
import secrets
import threading
import time
from dataclasses import asdict, dataclass
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from PIL import Image

from e7showcase import __version__
from e7showcase.app.armory import armory
from e7showcase.app.battle_report import read_capture, read_report
from e7showcase.app.discord_settings import DiscordSettings, Publisher
from e7showcase.app.guild import GuildStore, guild_csv, members_csv
from e7showcase.app.guild_import import GuildImportError, import_guild_csv
from e7showcase.app.gvg import (
    GvgError,
    GvgStore,
    counters_csv,
    counters_report,
    defense_plan,
    defenses_csv,
    war_report,
    wars_csv,
)
from e7showcase.app.importer import ScreenshotImporter
from e7showcase.app.portraits import Portraits
from e7showcase.app.profile_csv import profile_csv
from e7showcase.app.profiles import ProfileStore
from e7showcase.app.viewer import profile_page
from e7showcase.app.vitrine_file import (
    VitrineFileError,
    export_profile,
    import_vitrine,
    suggested_filename,
)
from e7showcase.assets import AssetStore
from e7showcase.parsers.war_map import parse_fortress, parse_war_map
from e7showcase.vision.hero_faces import FaceMatcher

FACES_MIN = 50  # en dessous, la reconnaissance des portraits n'a pas de quoi comparer

log = logging.getLogger(__name__)
UI = Path(__file__).resolve().parent / "ui.html"
MAX_BODY = 400 * 1024 * 1024
MAX_UPLOAD = 40 * 1024 * 1024  # une capture
UPLOAD_TTL = 600.0
UNLOCKED = (
    "/api/sim/",
    "/api/portraits",
    "/api/gvg/report",
    "/api/gvg/faces",
)  # calculs sans écriture, parfois longs


ANIM_PAGE = Path(__file__).with_name("anim.html")
# Interface et vitrine : tout est local et intégré (aucun script, style ou image externe) ;
# la page ne peut être affichée dans un cadre que par l'application elle-même
APP_CSP = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "img-src 'self' data: blob:; connect-src 'self'; frame-src 'self'; "
    "frame-ancestors 'self'; base-uri 'none'; form-action 'none'"
)
APP_HEADERS = {"Content-Security-Policy": APP_CSP, "Referrer-Policy": "no-referrer"}
MAP_HELP = "capture non reconnue : utilisez l'écran principal de la guerre (guildes et forteresses)"
FORTRESS_HELP = "aucun joueur reconnu : utilisez la vue d'une forteresse (pseudos des défenseurs)"
WARMAP_RE = re.compile(r"/gvgmap/([0-9a-f]{16}\.webp|background\.webp)")
MEDIA_RE = re.compile(r"/media/([a-z0-9-]{1,60})/([a-z0-9-]{1,80}(?:\.[a-z]{1,10})?\.webp)")
ANIM_RE = re.compile(r"/anim/(c\d{4}(?:_[a-z0-9]{1,8}){0,2})")
# Page du modèle animé : seuls le lecteur et les fichiers publics d'E7 Codex sont autorisés
ANIM_CSP = (
    "default-src 'none'; script-src 'unsafe-inline' https://e7codex.com; "
    "connect-src https://e7codex.com; img-src https://e7codex.com data: blob:; "
    "style-src 'unsafe-inline'"
)


class AppState:
    def __init__(self, data_root: Path, importer: ScreenshotImporter | None = None):
        self.store = ProfileStore(data_root / "profiles")
        self.assets = AssetStore(data_root / "assets")
        self.guild = GuildStore(data_root / "guild.json", self.store)
        self.gvg = GvgStore(data_root / "gvg.json", self.store, self.guild)
        self.portraits = Portraits(self.assets, self.store)
        self.discord = DiscordSettings(data_root / "discord.json")
        self.webhook_transport: Any = None  # tests : transport httpx simulé
        self.publisher = Publisher(self.discord, self.publication, lambda: self.webhook_transport)
        self.importer = importer or ScreenshotImporter(data_root / "templates" / "sets")
        self.token = secrets.token_urlsafe(24)
        self.lock = threading.Lock()  # un import OCR à la fois
        self.jobs: dict[str, ImportJob] = {}
        self._ui: bytes | None = None
        self._ocr: Any = None
        self.lock_ocr = threading.Lock()
        self.faces = FaceMatcher(data_root / "assets" / "faces")
        self.war_images = data_root / "gvg_map"
        self.face_sync: dict[str, Any] = {"running": False, "done": 0, "total": 0, "error": None}
        self._pages: dict[str, tuple[tuple[int, int, int], bytes]] = {}
        self.uploads: dict[str, tuple[float, str, bytes]] = {}
        self.lock_uploads = threading.Lock()
        self.write_lock = threading.RLock()

    def add_upload(self, name: str, data: bytes) -> str:
        """Capture reçue en attente d'analyse ; les envois oubliés (> 10 min) sont purgés."""
        now = time.monotonic()
        with self.lock_uploads:
            self.uploads = {k: v for k, v in self.uploads.items() if now - v[0] < UPLOAD_TTL}
            if sum(len(v[2]) for v in self.uploads.values()) + len(data) > MAX_BODY:
                raise ApiError(413, "trop de captures en attente : relancez l'import")
            upload_id = secrets.token_hex(8)
            self.uploads[upload_id] = (now, name, data)
        return upload_id

    def take_uploads(self, ids: list[str]) -> list[tuple[str, bytes]]:
        with self.lock_uploads:
            if any(i not in self.uploads for i in ids):
                raise ApiError(400, "capture introuvable : relancez l'import")
            return [self.uploads.pop(i)[1:] for i in ids]

    def vitrine(self, profile_id: str) -> bytes:
        """Page vitrine, gardée en mémoire tant que rien ne change (profils, images, assets)."""
        assets = 0
        for kind in ("heroes", "faces", "artifacts", "anims"):  # images téléchargées
            with contextlib.suppress(OSError):
                assets = max(assets, (self.assets.root / kind).stat().st_mtime_ns)
        key = (self.store.generation, self.store.path(profile_id).joinpath("profile.json")
               .stat().st_mtime_ns, assets)  # fmt: skip
        cached = self._pages.get(profile_id)
        if cached is not None and cached[0] == key:
            return cached[1]
        page = profile_page(self.store, profile_id, self.assets).encode()
        self._pages = {k: v for k, v in list(self._pages.items())[-7:]}  # 8 pages au plus
        self._pages[profile_id] = (key, page)
        return page

    def ui_page(self) -> bytes:
        """Interface (lue une fois puis gardée en mémoire, jeton de session inséré)."""
        if self._ui is None:
            self._ui = UI.read_text(encoding="utf-8").replace("__TOKEN__", self.token).encode()
        return self._ui

    def ocr(self) -> Any:
        """Moteur OCR partagé (chargé au premier besoin : plusieurs secondes)."""
        with self.lock_ocr:
            if self._ocr is None:
                from e7showcase.vision.ocr import get_engine

                self._ocr = get_engine()
            return self._ocr

    def face_sync_status(self) -> dict[str, Any]:
        from e7showcase.sources.e7codex import face_jobs

        return {
            **self.face_sync,
            "count": self.faces.count(),
            "total": self.face_sync.get("total") or len(face_jobs()),
        }

    def start_face_sync(self) -> None:
        """Télécharge en tâche de fond les icônes de visage (reconnaissance des portraits)."""
        if self.face_sync.get("running"):
            return
        self.face_sync = {"running": True, "done": 0, "total": 0, "error": None}

        def work() -> None:
            import httpx

            from e7showcase.sources.e7codex import sync_faces

            def progress(done: int, total: int) -> None:
                self.face_sync.update(done=done, total=total)

            try:
                with httpx.Client(follow_redirects=True) as client:
                    report = sync_faces(self.assets, client, on_progress=progress)
                if report.missing and not report.downloaded and not report.skipped:
                    self.face_sync["error"] = "téléchargement impossible : vérifiez la connexion"
            except Exception:  # noqa: BLE001 - affiché dans l'interface
                log.exception("Téléchargement des visages impossible")
                self.face_sync["error"] = "téléchargement impossible : vérifiez la connexion"
            finally:
                self.face_sync["running"] = False

        threading.Thread(target=work, daemon=True).start()

    def background(self) -> dict[str, Any]:
        """Image de fond de la GvG choisie par le joueur (gardée sur son ordinateur)."""
        target = self.war_images / "background.webp"
        try:
            return {"background": f"/gvgmap/background.webp?v={target.stat().st_mtime_ns}"}
        except OSError:
            return {"background": None}

    def save_war_image(self, image: Any) -> str:
        """Capture de guerre gardée localement (réencodée, 2 000 px au plus) pour la carte."""
        self.war_images.mkdir(parents=True, exist_ok=True)
        name = secrets.token_hex(8) + ".webp"
        img = image.copy()
        img.thumbnail((2000, 2000))
        img.save(self.war_images / name, "WEBP", quality=80)
        return name

    def drop_war_images(self, names: list[str]) -> None:
        for name in names:
            if WARMAP_RE.fullmatch("/gvgmap/" + name):
                (self.war_images / name).unlink(missing_ok=True)

    def guild_ids(self) -> list[str]:
        """Profils où chercher un portrait découpé : membres de la guilde, puis les autres."""
        members = [m["id"] for m in self.guild.summary()["members"]]
        return members + [p.id for p in self.store.list() if p.id not in members]

    def publication(self, key: str) -> list[str] | None:
        """Messages Discord d'une publication : plan de défense ou suivi d'une guerre."""
        if key == "plan":
            return list(defense_plan(self.gvg.summary())["messages"])
        if key == "counters":
            return counters_report(self.gvg.summary())
        return war_report(self.gvg.summary(), key.removeprefix("war:"))

    def start_import(self, profile_id: str, files: list[tuple[str, bytes]]) -> ImportJob:
        job = ImportJob(id=secrets.token_hex(6), total=max(1, len(files) * 2))
        self.jobs = {k: j for k, j in self.jobs.items() if not j.finished}  # purge
        self.jobs[job.id] = job

        def work() -> None:
            try:
                with self.lock:
                    report = self.importer.run(self.store, profile_id, files, job.update)
                job.report = report.as_dict()
            except Exception:  # noqa: BLE001 - l'interface affiche l'erreur
                log.exception("Échec de l'import")
                job.error = "l'analyse des captures a échoué (voir le journal)"
            finally:
                job.finished = True

        threading.Thread(target=work, daemon=True).start()
        return job


@dataclass
class ImportJob:
    """Progression d'un import, lue par l'interface toutes les ~300 ms."""

    id: str
    total: int
    done: int = 0
    message: str = "Préparation…"
    finished: bool = False
    report: dict[str, Any] | None = None
    error: str | None = None

    def update(self, done: int, total: int, message: str) -> None:
        self.done, self.total, self.message = done, max(1, total), message


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


@lru_cache(maxsize=256)
def _thumbnail(path: Path, stamp: int, width: int) -> bytes:
    """Vignette WebP d'une image du profil (mémorisée tant que le fichier ne change pas)."""
    from PIL import Image

    with Image.open(path) as src:
        img = src.convert("RGB")
    img.thumbnail((width, width * 2), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=80)
    return buf.getvalue()


def _b64(value: Any) -> bytes:
    if not isinstance(value, str):
        raise ApiError(400, "fichier manquant")
    try:
        return base64.b64decode(value.split(",", 1)[-1], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ApiError(400, "fichier mal encodé") from exc


def make_handler(state: AppState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = f"E7Showcase/{__version__}"

        def log_message(self, fmt: str, *args: Any) -> None:
            log.debug(fmt, *args)

        # --- réponses
        def _send(
            self, status: int, body: bytes, ctype: str, extra: dict[str, str] | None = None
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            extra = extra or {}
            self.send_header("Cache-Control", extra.pop("Cache-Control", "no-store"))
            self.send_header("X-Content-Type-Options", "nosniff")
            for k, v in extra.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, data: Any, status: int = 200) -> None:
            self._send(status, json.dumps(data, ensure_ascii=False).encode(), "application/json")

        def _host_ok(self) -> bool:
            host = (self.headers.get("Host") or "").split(":")[0]
            return host in {"127.0.0.1", "localhost"}

        def _body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                raise ApiError(413, "envoi trop volumineux")
            try:
                data = json.loads(self.rfile.read(length) or b"{}")
            except ValueError as exc:
                raise ApiError(400, "requête invalide") from exc
            if not isinstance(data, dict):
                raise ApiError(400, "requête invalide")
            return data

        def _raw(self, limit: int) -> bytes:
            length = int(self.headers.get("Content-Length") or 0)
            if not 0 < length <= limit:
                raise ApiError(413 if length else 400, "fichier vide ou trop volumineux")
            return self.rfile.read(length)

        def _dispatch(self, method: str) -> None:
            if not self._host_ok():
                self._send(403, b"forbidden", "text/plain")
                return
            path = urlparse(self.path).path
            try:
                if method == "GET" and path == "/":
                    self._send(200, state.ui_page(), "text/html; charset=utf-8", APP_HEADERS)
                elif method == "GET" and (m := re.fullmatch(r"/profile/([a-z0-9-]+)", path)):
                    if not state.store.exists(m[1]):
                        raise ApiError(404, "profil introuvable")
                    self._send(200, state.vitrine(m[1]), "text/html; charset=utf-8", APP_HEADERS)
                elif method == "GET" and (m := WARMAP_RE.fullmatch(path)):
                    target = state.war_images / m[1]  # capture de carte ou de forteresse
                    if not target.is_file():
                        raise ApiError(404, "introuvable")
                    cache = {"Cache-Control": "private, max-age=31536000, immutable"}
                    self._send(200, target.read_bytes(), "image/webp", cache)
                elif method == "GET" and (m := MEDIA_RE.fullmatch(path)):
                    # image d'un profil (adresse versionnée par ?v= : gardée en cache longtemps)
                    if not state.store.exists(m[1]):
                        raise ApiError(404, "introuvable")
                    target = state.store.path(m[1]) / "images" / m[2]
                    if not target.is_file():
                        raise ApiError(404, "introuvable")
                    cache = {"Cache-Control": "private, max-age=31536000, immutable"}
                    width = parse_qs(urlparse(self.path).query).get("w", [""])[0]
                    body = (
                        _thumbnail(target, target.stat().st_mtime_ns, int(width))
                        if width.isdigit() and 16 <= int(width) <= 512
                        else target.read_bytes()
                    )
                    self._send(200, body, "image/webp", cache)
                elif method == "GET" and (m := ANIM_RE.fullmatch(path)):
                    html = ANIM_PAGE.read_text(encoding="utf-8").replace("__CODE__", m[1])
                    self._send(
                        200,
                        html.encode(),
                        "text/html; charset=utf-8",
                        {"Content-Security-Policy": ANIM_CSP},
                    )
                elif path.startswith("/api/"):
                    if not secrets.compare_digest(self.headers.get("X-E7-Token", ""), state.token):
                        raise ApiError(403, "jeton de session invalide")
                    if method == "GET" or path.startswith(UNLOCKED):
                        self._api(method, path[4:])
                    else:  # modifications une par une (fichiers lus, modifiés puis réécrits)
                        with state.write_lock:
                            self._api(method, path[4:])
                else:
                    raise ApiError(404, "introuvable")
            except ApiError as exc:
                self._json({"error": str(exc)}, exc.status)
            except Exception:  # noqa: BLE001 - l'interface doit recevoir une erreur lisible
                log.exception("Erreur interne")
                self._json({"error": "erreur interne (voir le journal)"}, 500)

        def _api(self, method: str, path: str) -> None:
            store = state.store
            if path == "/version":
                return self._json({"version": __version__})
            if path == "/profiles":
                if method == "GET":
                    return self._json([asdict(p) for p in store.list()])
                if method == "POST":
                    pid = store.create(str(self._body().get("player", "")))
                    return self._json({"id": pid}, 201)
            if path.startswith("/sim/"):
                from e7showcase.app import simulator

                try:
                    if path == "/sim/heroes" and method == "GET":
                        return self._json(simulator.catalog(store))
                    if path == "/sim/damage" and method == "POST":
                        return self._json(simulator.damage(store, self._body()))
                    if path == "/sim/battle" and method == "POST":
                        return self._json(simulator.battle(store, self._body()))
                except simulator.SimError as exc:
                    raise ApiError(400, str(exc)) from exc
                raise ApiError(404, "introuvable")
            if path == "/gvg" or path.startswith("/gvg/"):
                return self._gvg(method, path[4:])
            if path == "/portraits" and method == "POST":
                body = self._body()
                names, pids = body.get("names"), body.get("profiles")
                if not isinstance(names, list):
                    raise ApiError(400, "liste de héros attendue")
                pids = [p for p in pids if isinstance(p, str)] if isinstance(pids, list) else []
                return self._json(state.portraits.lookup(names, pids or state.guild_ids()))
            if path == "/guild/import" and method == "POST":
                text = self._body().get("csv")
                if not isinstance(text, str):
                    raise ApiError(400, "fichier CSV manquant")
                try:
                    report = import_guild_csv(text, store, state.guild, state.gvg)
                except GuildImportError as exc:
                    raise ApiError(400, str(exc)) from exc
                state.publisher.changed("plan")  # défenses et contres importés
                state.publisher.changed("counters")
                return self._json(asdict(report))
            if path == "/guild/full.csv" and method == "GET":
                csv = guild_csv(state.guild.summary(), state.store, state.gvg.summary())
                return self._json({"csv": csv})
            if path == "/guild/csv" and method == "GET":
                return self._json({"csv": members_csv(state.guild.summary())})
            if path == "/guild":
                if method == "GET":
                    return self._json(state.guild.summary())
                if method == "PATCH":
                    body = self._body()
                    members = body.get("members")
                    state.guild.update(
                        name=str(body["name"]) if "name" in body else None,
                        members=[str(m) for m in members] if isinstance(members, list) else None,
                    )
                    state.publisher.changed()  # nom ou membres : le plan publié change aussi
                    return self._json(state.guild.summary())
            if (j := re.fullmatch(r"/jobs/([0-9a-f]+)", path)) and method == "GET":
                job = state.jobs.get(j[1])
                if job is None:
                    raise ApiError(404, "import introuvable")
                return self._json(asdict(job))
            if path == "/open" and method == "POST":
                body = self._body()
                try:
                    pid = import_vitrine(store, _b64(body.get("data")))
                except VitrineFileError as exc:
                    raise ApiError(400, str(exc)) from exc
                if body.get("guild"):  # vitrine d'un coéquipier ajoutée depuis la page Guilde
                    state.guild.add(pid)
                return self._json({"id": pid}, 201)
            m = re.fullmatch(r"/profiles/([a-z0-9-]+)(/.*)?", path)
            if not m or not store.exists(m[1]):
                raise ApiError(404, "profil introuvable")
            pid, rest = m[1], m[2] or ""
            if rest == "" and method == "GET":
                roster = store.peek(pid)
                return self._json(
                    {
                        "id": pid,
                        "player": roster.player,
                        "received": store.is_received(pid),
                        "heroes": [h.name for h in roster.heroes],
                    }
                )
            if rest == "" and method == "DELETE":
                store.delete(pid)
                return self._send(204, b"", "text/plain")
            if rest == "/csv" and method == "GET":
                return self._json({"csv": profile_csv(store.peek(pid))})
            if rest == "/armory" and method == "GET":
                return self._json(armory(store, pid, state.importer.set_library))
            if rest == "/export" and method == "GET":
                data = export_profile(store, pid)
                name = suggested_filename(store.peek(pid).player)
                return self._send(
                    200,
                    data,
                    "application/octet-stream",
                    {"Content-Disposition": f'attachment; filename="{name}"'},
                )
            if store.is_received(pid):
                raise ApiError(403, "vitrine reçue : consultation uniquement")
            if rest == "" and method == "PATCH":
                store.rename(pid, str(self._body().get("player", "")))
                return self._json({"id": pid})
            if rest == "/uploads" and method == "POST":  # une capture, en binaire (sans base64)
                name = unquote(self.headers.get("X-File-Name") or "capture")[:120]
                return self._json({"id": state.add_upload(name, self._raw(MAX_UPLOAD))}, 201)
            if rest == "/screenshots" and method == "POST":
                body = self._body()
                files, uploads = body.get("files"), body.get("uploads")
                if isinstance(uploads, list) and uploads:
                    decoded = state.take_uploads([str(u) for u in uploads])
                elif isinstance(files, list) and files:  # ancien envoi en base64
                    decoded = [(str(f.get("name", "capture")), _b64(f.get("data"))) for f in files]
                else:
                    raise ApiError(400, "aucune capture reçue")
                job = state.start_import(pid, decoded)
                return self._json({"job": job.id, "total": job.total}, 202)
            if (i := re.fullmatch(r"/items/([0-9a-f]{1,32})", rest)) and method == "DELETE":
                if not store.remove_item(pid, i[1]):
                    raise ApiError(404, "pièce introuvable")
                return self._send(204, b"", "text/plain")
            if (h := re.fullmatch(r"/heroes/(.+)", rest)) and method == "DELETE":
                store.remove_hero(pid, unquote(h[1]))
                return self._send(204, b"", "text/plain")
            raise ApiError(404, "introuvable")

        def _send_plan(self, key: str = "plan") -> dict[str, Any]:
            """Publie le plan de défense dans le salon Discord du webhook enregistré."""
            import httpx

            from e7showcase.app.discord_settings import _describe

            if not state.discord.webhook():
                raise ApiError(400, "aucun webhook Discord enregistré")
            try:
                return {"sent": state.publisher.send_now(key)}
            except httpx.HTTPError as exc:
                raise ApiError(502, _describe(exc)) from exc

        def _gvg(self, method: str, rest: str) -> None:
            gvg = state.gvg
            try:
                if rest == "" and method == "GET":
                    return self._json(gvg.summary() | state.background())
                if rest == "/report" and method == "POST":  # capture de fin de combat (binaire)
                    try:
                        engine = state.ocr()
                    except ImportError as exc:
                        raise ApiError(503, "moteur de lecture des captures absent") from exc
                    try:
                        found = read_report(self._raw(MAX_UPLOAD), engine, state.faces)
                    except ValueError as exc:
                        raise ApiError(400, str(exc)) from exc
                    if state.faces.count() < FACES_MIN:  # visages absents : téléchargement lancé
                        state.start_face_sync()
                        found["faces_missing"] = True
                    return self._json(found)
                if rest in ("/map", "/map/fortress") and method == "POST":  # captures (binaire)
                    raw = self._raw(MAX_UPLOAD)
                    try:
                        engine = state.ocr()
                    except ImportError as exc:
                        raise ApiError(503, "moteur de lecture des captures absent") from exc
                    try:
                        image, lines = read_capture(raw, engine)
                    except ValueError as exc:
                        raise ApiError(400, str(exc)) from exc
                    if rest == "/map":
                        war_map = parse_war_map(lines, image.size)
                        if war_map is None or not war_map.fortresses:
                            raise ApiError(400, MAP_HELP)
                        state.drop_war_images(gvg.set_map(asdict(war_map), None))
                    else:
                        players = parse_fortress(lines, image.size)
                        if not players:
                            raise ApiError(400, FORTRESS_HELP)
                        fid = parse_qs(urlparse(self.path).query).get("id", [None])[0]
                        _, old = gvg.set_fortress(fid, [asdict(p) for p in players], None)
                        state.drop_war_images([old] if old else [])
                    return self._json(gvg.summary())
                if (
                    pl := re.fullmatch(r"/map/fortress/(f\d)/players/(\d{1,2})", rest)
                ) and method == "PATCH":
                    gvg.update_player(pl[1], int(pl[2]), self._body())
                    return self._json(gvg.summary())
                if rest == "/background" and method == "POST":  # image de fond (binaire)
                    try:
                        with Image.open(io.BytesIO(self._raw(MAX_UPLOAD))) as src:
                            bg = src.convert("RGB")
                    except OSError as exc:
                        raise ApiError(400, "image illisible (PNG, JPG, WebP)") from exc
                    bg.thumbnail((2600, 2600))
                    state.war_images.mkdir(parents=True, exist_ok=True)
                    bg.save(state.war_images / "background.webp", "WEBP", quality=86)
                    return self._json(gvg.summary() | state.background())
                if rest == "/background" and method == "DELETE":
                    (state.war_images / "background.webp").unlink(missing_ok=True)
                    return self._json(gvg.summary() | state.background())
                if rest == "/map/archive" and method == "POST":
                    state.drop_war_images(gvg.archive_map())
                    return self._json(gvg.summary())
                if (ar := re.fullmatch(r"/archives/([0-9a-f]{1,16})", rest)) and method == "DELETE":
                    gvg.delete_archive(ar[1])
                    return self._json(gvg.summary())
                if rest == "/map" and method == "DELETE":
                    state.drop_war_images(gvg.clear_map())
                    return self._json(gvg.summary())
                if rest == "/faces" and method == "GET":
                    return self._json(state.face_sync_status())
                if rest == "/faces/sync" and method == "POST":
                    state.start_face_sync()
                    return self._json(state.face_sync_status(), 202)
                if rest == "/scouted" and method == "POST":
                    gvg.add_scouted(self._body())
                    return self._json(gvg.summary(), 201)
                if (sc := re.fullmatch(r"/scouted/([0-9a-f]{1,16})", rest)) and method == "DELETE":
                    gvg.delete_scouted(sc[1])
                    return self._json(gvg.summary())
                if rest == "/plan" and method == "GET":
                    return self._json(defense_plan(gvg.summary()))
                if rest == "/defense/csv" and method == "GET":
                    return self._json({"csv": defenses_csv(gvg.summary())})
                if rest == "/counters/csv" and method == "GET":
                    return self._json({"csv": counters_csv(gvg.summary())})
                if rest == "/wars/csv" and method == "GET":
                    return self._json({"csv": wars_csv(gvg.summary())})
                if rest == "/webhook" and method == "GET":
                    return self._json(state.discord.status())
                if rest == "/webhook" and method == "PUT":
                    body = self._body()
                    if "url" in body:
                        state.discord.set_webhook(str(body.get("url", ""))[:300])
                    for flag, kind in (
                        ("auto", "plan"),
                        ("auto_wars", "wars"),
                        ("auto_counters", "counters"),
                    ):
                        if flag in body:
                            state.discord.update(**{flag: bool(body[flag])})
                            if not body[flag]:
                                state.publisher.cancel(kind)
                    return self._json(state.discord.status())
                if rest == "/plan/send" and method == "POST":
                    return self._json(self._send_plan())
                if rest == "/settings" and method == "PATCH":
                    gvg.update_settings(self._body())
                    state.publisher.changed()
                elif (d := re.fullmatch(r"/defense/([a-z0-9-]+)", rest)) and method == "PUT":
                    gvg.set_defense(d[1], self._body())
                    state.publisher.changed()  # plan modifié : republication automatique
                elif rest == "/wars" and method == "POST":
                    gvg.add_war(self._body())
                elif (w := re.fullmatch(r"/wars/([0-9a-f]{1,16})", rest)) and method == "DELETE":
                    gvg.delete_war(w[1])
                    state.discord.forget("war:" + w[1])  # les messages déjà publiés restent
                    state.publisher.changed("counters")
                    if gvg.summary()["settings"]["plan_counters"]:
                        state.publisher.changed("plan")  # le plan contient les contres
                elif rest == "/counters/send" and method == "POST":
                    return self._json(self._send_plan("counters"))
                elif (w := re.fullmatch(r"/wars/([0-9a-f]{1,16})/send", rest)) and method == "POST":
                    if w[1] not in {x["id"] for x in gvg.summary()["wars"]}:
                        raise GvgError("guerre introuvable")
                    return self._json(self._send_plan("war:" + w[1]))
                elif (w := re.fullmatch(r"/wars/([0-9a-f]{1,16})/attacks", rest)) and (
                    method == "POST"
                ):
                    gvg.add_attack(w[1], self._body())
                    state.publisher.changed("war:" + w[1])  # suivi publié : mis à jour
                    state.publisher.changed("counters")
                    if gvg.summary()["settings"]["plan_counters"]:
                        state.publisher.changed("plan")  # le plan contient les contres
                elif (
                    a := re.fullmatch(r"/wars/([0-9a-f]{1,16})/attacks/([0-9a-f]{1,16})", rest)
                ) and method == "DELETE":
                    gvg.delete_attack(a[1], a[2])
                    state.publisher.changed("war:" + a[1])
                    state.publisher.changed("counters")
                    if gvg.summary()["settings"]["plan_counters"]:
                        state.publisher.changed("plan")  # le plan contient les contres
                else:
                    raise ApiError(404, "introuvable")
            except (GvgError, ValueError, TypeError) as exc:
                raise ApiError(400, str(exc)) from exc
            return self._json(gvg.summary())

        def do_GET(self) -> None:  # noqa: N802
            self._dispatch("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._dispatch("POST")

        def do_PUT(self) -> None:  # noqa: N802
            self._dispatch("PUT")

        def do_PATCH(self) -> None:  # noqa: N802
            self._dispatch("PATCH")

        def do_DELETE(self) -> None:  # noqa: N802
            self._dispatch("DELETE")

    return Handler


def start_server(state: AppState, port: int = 0) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
