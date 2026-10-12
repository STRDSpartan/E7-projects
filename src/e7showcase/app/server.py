"""Serveur local de l'application (127.0.0.1 uniquement, bibliothèque standard).

L'interface (HTML/JS) dialogue avec ce serveur ; chaque appel /api exige le jeton de session
tiré au lancement (en-tête X-E7-Token) et l'en-tête Host est vérifié : un site web ouvert
dans le navigateur ne peut ni lire ni modifier les profils.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import re
import secrets
import threading
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from e7showcase import __version__
from e7showcase.app.armory import armory
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

log = logging.getLogger(__name__)
UI = Path(__file__).resolve().parent / "ui.html"
MAX_BODY = 400 * 1024 * 1024


ANIM_PAGE = Path(__file__).with_name("anim.html")
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
        self.discord = DiscordSettings(data_root / "discord.json")
        self.webhook_transport: Any = None  # tests : transport httpx simulé
        self.publisher = Publisher(self.discord, self.publication, lambda: self.webhook_transport)
        self.importer = importer or ScreenshotImporter(data_root / "templates" / "sets")
        self.token = secrets.token_urlsafe(24)
        self.lock = threading.Lock()  # un import OCR à la fois
        self.jobs: dict[str, ImportJob] = {}

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
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for k, v in (extra or {}).items():
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

        def _dispatch(self, method: str) -> None:
            if not self._host_ok():
                self._send(403, b"forbidden", "text/plain")
                return
            path = urlparse(self.path).path
            try:
                if method == "GET" and path == "/":
                    html = UI.read_text(encoding="utf-8").replace("__TOKEN__", state.token)
                    self._send(200, html.encode(), "text/html; charset=utf-8")
                elif method == "GET" and (m := re.fullmatch(r"/profile/([a-z0-9-]+)", path)):
                    if not state.store.exists(m[1]):
                        raise ApiError(404, "profil introuvable")
                    page = profile_page(state.store, m[1], state.assets)
                    self._send(200, page.encode(), "text/html; charset=utf-8")
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
                roster = store.load(pid)
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
                return self._json({"csv": profile_csv(store.load(pid))})
            if rest == "/armory" and method == "GET":
                return self._json(armory(store, pid, state.importer.set_library))
            if rest == "/export" and method == "GET":
                data = export_profile(store, pid)
                name = suggested_filename(store.load(pid).player)
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
            if rest == "/screenshots" and method == "POST":
                files = self._body().get("files")
                if not isinstance(files, list) or not files:
                    raise ApiError(400, "aucune capture reçue")
                decoded = [(str(f.get("name", "capture")), _b64(f.get("data"))) for f in files]
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
