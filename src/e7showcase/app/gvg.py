"""Guerre de guilde (GvG) : défenses des membres, suivi des guerres et contres connus.

    <dossier de données>/gvg.json

- défense d'un membre de la guilde : deux équipes de 3 héros de son roster (un héros ne peut
  être que dans une équipe) et la tour défendue ;
- guerre : adversaire, date, attaques (attaquant, équipe utilisée, défense ennemie, résultat) ;
- contres : pour chaque défense ennemie (3 héros), les équipes qui l'ont battue ou non, cumulées
  sur toutes les guerres.

Tout reste sur l'ordinateur du joueur ; les entrées sont validées (noms de héros du roster pour
les équipes de la guilde, textes courts pour l'adversaire).
"""

from __future__ import annotations

import json
import secrets
from datetime import date
from pathlib import Path
from typing import Any

from e7showcase.app.guild import GuildStore
from e7showcase.app.jsonfile import write_json
from e7showcase.app.profiles import ProfileStore
from e7showcase.parsers.war_map import FORT_SLOTS
from e7showcase.reference import load

TEAM_SIZE = 3
TEAMS = 2
MAX_TEXT = 40
RESULTS = ("win", "loss")
MAX_SCOUTED = 200
MAX_ARCHIVES = 200
MAX_FORTRESSES = 6
MAX_PLAYERS = 40
SCOUT_STATS = (
    "atk", "def", "hp", "spd", "crit_chance", "crit_dmg", "effectiveness", "effect_res",
    "dual_attack",
)  # fmt: skip
DEFAULT_TOWERS = [
    "Bastion nord",
    "Bastion sud",
    "Fort est",
    "Fort ouest",
    "Château",
]


class GvgError(ValueError):
    pass


def _text(value: Any, limit: int = MAX_TEXT) -> str:
    return str(value or "").strip()[:limit]


class GvgStore:
    def __init__(self, path: Path, profiles: ProfileStore, guild: GuildStore):
        self.path, self.profiles, self.guild = path, profiles, guild

    # --- fichier
    def _read(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        raw_settings, raw_defenses = data.get("settings"), data.get("defenses")
        settings: dict[str, Any] = raw_settings if isinstance(raw_settings, dict) else {}
        defenses: dict[str, Any] = raw_defenses if isinstance(raw_defenses, dict) else {}
        wars = [w for w in data.get("wars", []) if isinstance(w, dict) and w.get("id")]
        return {
            "settings": {
                "attacks_per_member": int(settings.get("attacks_per_member", 2) or 2),
                "towers": [_text(t) for t in settings.get("towers", DEFAULT_TOWERS) if _text(t)]
                or list(DEFAULT_TOWERS),
                "plan_counters": bool(settings.get("plan_counters", False)),
            },
            "defenses": defenses,
            "wars": wars,
            "scouted": [s for s in data.get("scouted", []) if isinstance(s, dict) and s.get("id")],
            "map": data["map"] if isinstance(data.get("map"), dict) else None,
            "archives": [
                a for a in data.get("archives", []) if isinstance(a, dict) and a.get("id")
            ],
            "ally_forts": data["ally_forts"] if isinstance(data.get("ally_forts"), dict) else {},
        }

    def _write(self, data: dict[str, Any]) -> None:
        write_json(self.path, data, ensure_ascii=False, indent=1)

    # --- validation
    def _roster_names(self, member: str) -> dict[str, str]:
        if not self.profiles.exists(member):
            raise GvgError("membre introuvable")
        return {h.name.casefold(): h.name for h in self.profiles.peek(member).heroes}

    def _team(self, member: str, team: Any) -> list[str]:
        names = self._roster_names(member)
        if not isinstance(team, list) or len(team) > TEAM_SIZE:
            raise GvgError(f"une équipe compte au plus {TEAM_SIZE} héros")
        out = []
        for raw in team:
            key = _text(raw).casefold()
            if not key:
                continue
            if key not in names:
                raise GvgError(f"{_text(raw)} n'est pas dans le roster du membre")
            if names[key] in out:
                raise GvgError(f"{names[key]} est en double dans l'équipe")
            out.append(names[key])
        return out

    @staticmethod
    def _enemy_team(team: Any) -> list[str]:
        if not isinstance(team, list):
            return []
        return [t for t in (_text(x) for x in team[:TEAM_SIZE]) if t]

    def _war(self, data: dict[str, Any], war_id: str) -> dict[str, Any]:
        wars: list[dict[str, Any]] = data["wars"]
        for war in wars:
            if war["id"] == war_id:
                return war
        raise GvgError("guerre introuvable")

    # --- modifications
    def update_settings(self, body: dict[str, Any]) -> None:
        data = self._read()
        if "attacks_per_member" in body:
            data["settings"]["attacks_per_member"] = min(
                max(int(body["attacks_per_member"]), 1), 10
            )
        if "plan_counters" in body:  # contres connus ajoutés au plan de défense
            data["settings"]["plan_counters"] = bool(body["plan_counters"])
        if isinstance(body.get("towers"), list):
            towers = [_text(t) for t in body["towers"] if _text(t)][:20]
            data["settings"]["towers"] = towers or list(DEFAULT_TOWERS)
        self._write(data)

    def set_defense(self, member: str, body: dict[str, Any]) -> None:
        teams = body.get("teams", [])
        if not isinstance(teams, list) or len(teams) > TEAMS:
            raise GvgError(f"une défense compte au plus {TEAMS} équipes")
        clean = [self._team(member, t) for t in teams]
        seen = [h for t in clean for h in t]
        if len(seen) != len(set(seen)):
            raise GvgError("un héros ne peut défendre que dans une seule équipe")
        data = self._read()
        data["defenses"][member] = {"teams": clean, "tower": _text(body.get("tower"))}
        self._write(data)

    def add_war(self, body: dict[str, Any]) -> str:
        opponent = _text(body.get("opponent"))
        if not opponent:
            raise GvgError("nom de la guilde adverse manquant")
        when = _text(body.get("date"), 10) or date.today().isoformat()
        data = self._read()
        war = {"id": secrets.token_hex(5), "opponent": opponent, "date": when, "attacks": []}
        data["wars"].insert(0, war)
        self._write(data)
        return str(war["id"])

    def delete_war(self, war_id: str) -> None:
        data = self._read()
        self._war(data, war_id)
        data["wars"] = [w for w in data["wars"] if w["id"] != war_id]
        self._write(data)

    def add_attack(self, war_id: str, body: dict[str, Any]) -> str:
        data = self._read()
        war = self._war(data, war_id)
        member = _text(body.get("member"), 60)
        team = self._team(member, body.get("team", []))
        if not team:
            raise GvgError("équipe d'attaque vide")
        result = body.get("result")
        if result not in RESULTS:
            raise GvgError("résultat attendu : victoire ou défaite")
        attack = {
            "id": secrets.token_hex(5),
            "member": member,
            "team": team,
            "enemy_player": _text(body.get("enemy_player")),
            "tower": _text(body.get("tower")),
            "enemy_team": self._enemy_team(body.get("enemy_team")),
            "result": result,
            "note": _text(body.get("note"), 200),
        }
        war["attacks"].append(attack)
        self._write(data)
        return str(attack["id"])

    def delete_attack(self, war_id: str, attack_id: str) -> None:
        data = self._read()
        war = self._war(data, war_id)
        kept = [a for a in war["attacks"] if a.get("id") != attack_id]
        if len(kept) == len(war["attacks"]):
            raise GvgError("attaque introuvable")
        war["attacks"] = kept
        self._write(data)

    def add_scouted(self, body: dict[str, Any]) -> str:
        """Défense adverse relevée sur un écran de résultat (héros et stats), pour la retester."""
        heroes = []
        for h in body.get("heroes", [])[: TEAM_SIZE + 1]:
            if not isinstance(h, dict) or not _text(h.get("name")):
                continue
            raw: dict[str, Any] = h["stats"] if isinstance(h.get("stats"), dict) else {}
            stats = {
                k: float(v)
                for k, v in raw.items()
                if k in SCOUT_STATS and isinstance(v, int | float) and 0 <= v <= 200000
            }
            heroes.append({"name": _text(h.get("name")), "stats": stats})
        if not heroes:
            raise GvgError("aucun héros adverse")
        data = self._read()
        entry = {
            "id": secrets.token_hex(5),
            "player": _text(body.get("player")),
            "note": _text(body.get("note"), 200),
            "date": date.today().isoformat(),
            "heroes": heroes,
        }
        data["scouted"] = [entry, *data["scouted"]][:MAX_SCOUTED]
        self._write(data)
        return str(entry["id"])

    # --- carte de la guerre (captures du jeu : carte, forteresses)
    def set_map(self, war_map: dict[str, Any], image: str | None) -> list[str]:
        """Nouvelle carte de guerre ; renvoie les images remplacées (à supprimer)."""
        data = self._read()
        old = data["map"] or {}
        replaced = [
            i for i in [old.get("image"), *(f.get("image") for f in old.get("fortresses", []))] if i
        ]
        same_war = (old.get("enemy") or {}).get("name") == war_map["enemy"].get("name")
        fortresses = []
        for i, f in enumerate(war_map["fortresses"][:MAX_FORTRESSES]):
            prev: dict[str, Any] = next(
                (p for p in old.get("fortresses", []) if same_war and p.get("name") == f["name"]),
                {},
            )  # même guerre : on garde joueurs et capture de la forteresse
            fortresses.append(
                {**f, "id": f"f{i}", "players": prev.get("players", []), "image": prev.get("image")}
            )
        kept = {f["image"] for f in fortresses if f.get("image")}
        data["map"] = {
            "date": date.today().isoformat(),
            "ours": war_map["ours"],
            "enemy": war_map["enemy"],
            "ends_in": _text(war_map.get("ends_in")),
            "fortresses": fortresses,
            "image": image,
        }
        names = [f["name"] for f in fortresses]
        if names and data["settings"]["towers"] == DEFAULT_TOWERS:
            data["settings"]["towers"] = names  # nos forteresses portent les mêmes noms
        opponent = _text(war_map["enemy"].get("name"))
        if opponent and not any(  # la guerre du jour apparaît aussi dans le suivi
            w["opponent"] == opponent and w["date"] == date.today().isoformat()
            for w in data["wars"]
        ):
            today = date.today().isoformat()
            data["wars"].insert(
                0, {"id": secrets.token_hex(5), "opponent": opponent, "date": today, "attacks": []}
            )
        self._write(data)
        return [i for i in replaced if i not in kept and i != image]

    def set_fortress(
        self, fortress_id: str | None, players: list[dict[str, Any]], image: str | None
    ) -> tuple[str, str | None]:
        """Joueurs d'une forteresse (désignée, sinon celle qui en compte autant) ;
        renvoie son id et l'ancienne capture remplacée."""
        data = self._read()
        if not data["map"]:
            raise GvgError("importez d'abord la capture de la carte de la guerre")
        forts = data["map"]["fortresses"]
        fort = next((f for f in forts if f["id"] == fortress_id), None)
        if fort is None:
            same = [f for f in forts if f.get("total") == len(players)]
            fort = same[0] if len(same) == 1 else None
        if fort is None:
            raise GvgError("choisissez la forteresse de cette capture (nombre de joueurs ambigu)")
        old = fort.get("image")
        fort["players"] = [
            {
                "name": _text(p["name"]),
                "x": float(p["x"]),
                "y": float(p["y"]),
                "slot": p["slot"] if isinstance(p.get("slot"), int) else None,
                "fx": float(p.get("fx", p["x"])),
                "fy": float(p.get("fy", p["y"])),
                "beaten": False,
            }
            for p in players[:MAX_PLAYERS]
        ]
        fort["image"] = image
        self._write(data)
        return str(fort["id"]), old if old != image else None

    def set_ally_fort(self, key: str, players: list[dict[str, Any]]) -> None:
        """Joueurs de notre fort `ally0`..`ally2`, lus sur une capture (positions sur le fort)."""
        if key not in ("ally0", "ally1", "ally2"):
            raise GvgError("fort allié inconnu")
        data = self._read()
        data["ally_forts"][key] = [
            {
                "name": _text(p["name"]),
                "slot": p["slot"] if isinstance(p.get("slot"), int) else None,
                "fx": float(p["fx"]),
                "fy": float(p["fy"]),
            }
            for p in players[:MAX_PLAYERS]
        ]
        self._write(data)

    def clear_ally_fort(self, key: str) -> None:
        data = self._read()
        data["ally_forts"].pop(key, None)
        self._write(data)

    def update_player(self, fortress_id: str, index: int, body: dict[str, Any]) -> None:
        data = self._read()
        fort = next(
            (f for f in (data["map"] or {}).get("fortresses", []) if f["id"] == fortress_id), None
        )
        if fort is None or not 0 <= index < len(fort["players"]):
            raise GvgError("joueur introuvable")
        player = fort["players"][index]
        if "name" in body and _text(body["name"]):
            player["name"] = _text(body["name"])
        if "beaten" in body:
            player["beaten"] = bool(body["beaten"])
        if "present" in body:
            player["present"] = bool(body["present"])
        self._write(data)

    def archive_map(self) -> list[str]:
        """Archive la guerre en cours (carte, forteresses, attaques du jour) puis l'efface :
        ses stats restent consultables et comptent dans l'historique."""
        data = self._read()
        m = data["map"]
        if not m:
            raise GvgError("aucune guerre en cours à archiver")
        opponent = _text((m.get("enemy") or {}).get("name"))
        war = next(
            (w for w in data["wars"] if w["opponent"] == opponent and w["date"] == m.get("date")),
            None,
        )
        attacks = list(war.get("attacks", [])) if war else []
        wins = sum(a.get("result") == "win" for a in attacks)
        data["archives"].insert(
            0,
            {
                "id": secrets.token_hex(5),
                "date": m.get("date") or date.today().isoformat(),
                "war_id": war["id"] if war else None,
                "opponent": opponent,
                "ours": m.get("ours") or {},
                "enemy": m.get("enemy") or {},
                "fortresses": [
                    {
                        "name": f.get("name"),
                        "left": f.get("left"),
                        "total": f.get("total"),
                        "players": len(f.get("players", [])),
                        "beaten": sum(bool(p.get("beaten")) for p in f.get("players", [])),
                    }
                    for f in m.get("fortresses", [])
                ],
                "attacks": attacks,
                "wins": wins,
                "losses": len(attacks) - wins,
            },
        )
        del data["archives"][MAX_ARCHIVES:]
        self._write(data)
        return self.clear_map()

    def delete_archive(self, archive_id: str) -> None:
        data = self._read()
        kept = [a for a in data["archives"] if a.get("id") != archive_id]
        if len(kept) == len(data["archives"]):
            raise GvgError("guerre archivée introuvable")
        data["archives"] = kept
        self._write(data)

    def clear_map(self) -> list[str]:
        data = self._read()
        old = data["map"] or {}
        data["map"] = None
        data["ally_forts"] = {}  # nouvelle guerre : nos forts sont à relire aussi
        self._write(data)
        return [
            i for i in [old.get("image"), *(f.get("image") for f in old.get("fortresses", []))] if i
        ]

    def delete_scouted(self, scout_id: str) -> None:
        data = self._read()
        kept = [s for s in data["scouted"] if s.get("id") != scout_id]
        if len(kept) == len(data["scouted"]):
            raise GvgError("défense relevée introuvable")
        data["scouted"] = kept
        self._write(data)

    # --- lecture
    def summary(self) -> dict[str, Any]:
        data = self._read()
        guild = self.guild.summary()
        names = {m["id"]: m["player"] for m in guild["members"]}
        members = []
        for m in guild["members"]:
            roster = self.profiles.peek(m["id"])
            defense = data["defenses"].get(m["id"], {"teams": [], "tower": ""})
            members.append(
                {
                    "id": m["id"],
                    "player": m["player"],
                    "heroes": sorted(h.name for h in roster.heroes),
                    "defense": defense,
                }
            )
        limit = data["settings"]["attacks_per_member"]
        wars = []
        for war in data["wars"]:
            attacks = [
                {**a, "player": names.get(a.get("member", ""), "Ancien membre")}
                for a in war.get("attacks", [])
            ]
            used = {m["id"]: 0 for m in members}
            for a in attacks:
                used[a["member"]] = used.get(a["member"], 0) + 1
            wins = sum(a["result"] == "win" for a in attacks)
            wars.append(
                {
                    **war,
                    "attacks": attacks,
                    "wins": wins,
                    "losses": len(attacks) - wins,
                    "remaining": {m["id"]: max(limit - used.get(m["id"], 0), 0) for m in members},
                }
            )
        return {
            "settings": data["settings"],
            "guild": guild["name"],
            "members": members,
            "wars": wars,
            "counters": self.counters(data["wars"]),
            "scouted": data["scouted"],
            "map": data["map"],
            "archives": data["archives"],
            "fort_slots": FORT_SLOTS,
            "ally_forts": data["ally_forts"],
            "history": self.history(data),
            "hero_names": sorted(
                {h.get("fr") or h["en"] for h in load("heroes")["heroes"] if h.get("stars")}
            ),
        }

    @staticmethod
    def history(data: dict[str, Any]) -> list[dict[str, Any]]:
        """Taux de victoire de chaque composition d'attaque (héros triés), toutes guerres :
        suivi en cours et guerres archivées dont le suivi a été supprimé."""
        live = {w["id"] for w in data["wars"]}
        attacks = [a for w in data["wars"] for a in w.get("attacks", [])]
        attacks += [
            a
            for ar in data["archives"]
            if ar.get("war_id") not in live
            for a in ar.get("attacks", [])
        ]
        table: dict[tuple[str, ...], dict[str, Any]] = {}
        for a in attacks:
            team = tuple(sorted(a.get("team", [])))
            if not team:
                continue
            row = table.setdefault(team, {"team": list(team), "wins": 0, "losses": 0, "vs": {}})
            won = a.get("result") == "win"
            row["wins" if won else "losses"] += 1
            enemy = " · ".join(sorted(a.get("enemy_team", [])))
            if enemy:
                vs = row["vs"].setdefault(enemy, {"wins": 0, "losses": 0})
                vs["wins" if won else "losses"] += 1
        out = []
        for row in table.values():
            fights = row["wins"] + row["losses"]
            out.append({**row, "fights": fights, "rate": round(100 * row["wins"] / fights)})
        return sorted(out, key=lambda r: (-r["fights"], -r["rate"]))

    @staticmethod
    def counters(wars: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Par défense ennemie (héros triés) : équipes victorieuses et défaites, toutes guerres."""
        table: dict[tuple[str, ...], dict[str, Any]] = {}
        for war in wars:
            for a in war.get("attacks", []):
                enemy = tuple(sorted(a.get("enemy_team", [])))
                if not enemy:
                    continue
                row = table.setdefault(enemy, {"enemy_team": list(enemy), "teams": {}})
                key = " · ".join(a["team"])
                stats = row["teams"].setdefault(key, {"team": a["team"], "wins": 0, "losses": 0})
                stats["wins" if a["result"] == "win" else "losses"] += 1
        out = []
        for row in table.values():
            teams = sorted(row["teams"].values(), key=lambda t: (-t["wins"], t["losses"]))
            out.append(
                {
                    "enemy_team": row["enemy_team"],
                    "teams": teams,
                    "wins": sum(t["wins"] for t in teams),
                    "losses": sum(t["losses"] for t in teams),
                }
            )
        return sorted(out, key=lambda r: -(r["wins"] + r["losses"]))


DISCORD_LIMIT = 1900  # Discord : 2 000 caractères par message (marge pour le découpage)


def defense_plan(summary: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    """Plan de défense de la guilde : texte Discord (messages ≤ 2 000 car.) et tableau CSV."""
    day = (today or date.today()).strftime("%d/%m/%Y")
    towers: list[str] = list(summary["settings"]["towers"])
    groups: dict[str, list[dict[str, Any]]] = {}
    idle = []
    for m in summary["members"]:
        teams = [t for t in m["defense"]["teams"] if t]
        if not teams:
            idle.append(m["player"])
            continue
        tower = m["defense"]["tower"] or "Tour non attribuée"
        groups.setdefault(tower, []).append({"player": m["player"], "teams": m["defense"]["teams"]})
        if tower not in towers:
            towers.append(tower)
    title = f"**Plan de défense GvG{' — ' + summary['guild'] if summary['guild'] else ''}** ({day})"
    lines = [title]
    rows = [["Tour", "Membre", "Équipe", "Héros 1", "Héros 2", "Héros 3"]]
    for tower in towers:
        if tower not in groups:
            continue
        lines += ["", f"__{tower}__"]
        for d in groups[tower]:
            parts = [f"É{i + 1} : {', '.join(t)}" for i, t in enumerate(d["teams"]) if t]
            lines.append(f"• **{d['player']}** — " + " · ".join(parts))
            for i, t in enumerate(d["teams"]):
                if t:
                    rows.append([tower, d["player"], str(i + 1), *(t + ["", "", ""])[:3]])
    if idle:
        lines += ["", "Sans défense : " + ", ".join(idle)]
    if len(lines) == 1:
        lines.append("Aucune défense n'est encore placée.")
    defenses = [list(r) for r in rows]  # tableau des défenses seul (exports tableur)
    if summary["settings"].get("plan_counters") and summary.get("counters"):
        lines += ["", "**Contres connus**", *counter_lines(summary["counters"])]
        rows += [[], *_counter_rows(summary["counters"])]
    rows += _war_rows(summary)
    messages: list[str] = []
    for line in lines:  # découpe en messages Discord, sans couper une ligne
        if messages and len(messages[-1]) + len(line) + 1 <= DISCORD_LIMIT:
            messages[-1] += "\n" + line
        else:
            messages.append(line[:DISCORD_LIMIT])
    csv = "\n".join(";".join(_csv_cell(c) for c in row) for row in rows)
    return {
        "text": "\n".join(lines),
        "messages": messages,
        "csv": "﻿" + csv + "\n",
        "defenses": defenses,
    }


def _counter_rows(counters: list[dict[str, Any]]) -> list[list[str]]:
    """Contres connus pour le CSV : une ligne par équipe testée contre chaque défense."""
    rows = [["Défense ennemie", "Équipe d'attaque", "Victoires", "Défaites", "Bilan"]]
    for c in counters:
        for t in c["teams"]:
            verdict = (
                "gagnée"
                if t["wins"] and not t["losses"]
                else "perdue"
                if not t["wins"]
                else "mitigée"
            )
            enemy, team = " · ".join(c["enemy_team"]), ", ".join(t["team"])
            rows.append([enemy, team, str(t["wins"]), str(t["losses"]), verdict])
    return rows


def defenses_csv(summary: dict[str, Any]) -> str:
    """Défenses seules, en tableur (sans contres ni suivi des guerres)."""
    return _csv(defense_plan(summary)["defenses"])


def counters_csv(summary: dict[str, Any]) -> str:
    """Contres connus seuls, en tableur."""
    rows = _counter_rows(summary["counters"]) if summary["counters"] else []
    return _csv(rows or [["Aucun contre enregistré"]])


def _csv(rows: list[list[str]]) -> str:
    return "\ufeff" + "\n".join(";".join(_csv_cell(c) for c in row) for row in rows) + "\n"


def wars_csv(summary: dict[str, Any]) -> str:
    """Suivi des guerres seul, en tableur (attaques puis attaques restantes)."""
    return _csv(_war_rows(summary)[1:] or [["Aucune guerre enregistrée"]])


def _war_rows(summary: dict[str, Any]) -> list[list[str]]:
    """Suivi des guerres pour le CSV : attaques, puis attaques restantes par membre."""
    if not summary.get("wars"):
        return []
    head = ["Guerre", "Date", "Membre", "Équipe", "Défense ennemie", "Joueur ennemi", "Tour"]
    rows = [[], [*head, "Résultat", "Note"]]
    limit = summary["settings"]["attacks_per_member"]
    left: list[list[str]] = [[], ["Guerre", "Date", "Membre", "Attaques restantes"]]
    for w in summary["wars"]:
        for a in w["attacks"]:
            rows.append(
                [
                    w["opponent"],
                    w["date"],
                    a["player"],
                    ", ".join(a["team"]),
                    ", ".join(a["enemy_team"]),
                    a.get("enemy_player") or "",
                    a.get("tower") or "",
                    "victoire" if a["result"] == "win" else "défaite",
                    a.get("note") or "",
                ]
            )
        for m in summary["members"]:
            remaining = w["remaining"].get(m["id"], limit)
            left.append([w["opponent"], w["date"], m["player"], f"{remaining}/{limit}"])
    return rows + left


def _csv_cell(value: str) -> str:
    """Cellule CSV (séparateur « ; » pour Excel en français) ; formules neutralisées."""
    text = value.replace('"', '""')
    if text[:1] in ("=", "+", "-", "@"):
        text = "'" + text
    return f'"{text}"' if any(c in text for c in ';"\n') or text != value else text


def _chunks(lines: list[str]) -> list[str]:
    """Regroupe des lignes en messages Discord (≤ 2 000 caractères), sans couper une ligne."""
    messages: list[str] = []
    for line in lines:
        if messages and len(messages[-1]) + len(line) + 1 <= DISCORD_LIMIT:
            messages[-1] += "\n" + line
        else:
            messages.append(line[:DISCORD_LIMIT])
    return messages


def war_report(summary: dict[str, Any], war_id: str) -> list[str] | None:
    """Suivi d'une guerre pour Discord : score, attaques, attaques restantes ; None si absente."""
    war = next((w for w in summary["wars"] if w["id"] == war_id), None)
    if war is None:
        return None
    total = war["wins"] + war["losses"]
    rate = f" ({round(100 * war['wins'] / total)} % de victoires)" if total else ""
    guild = summary["guild"] or "Notre guilde"
    lines = [
        f"**Guerre de guilde — {guild} contre {war['opponent']}** ({war['date']})",
        f"Score : **{war['wins']} victoire(s)** · {war['losses']} défaite(s){rate}",
    ]
    if war["attacks"]:
        lines += ["", "__Attaques__"]
        for a in war["attacks"]:
            mark = "✅" if a["result"] == "win" else "❌"
            target = ", ".join(a["enemy_team"]) or "défense non notée"
            where = " · ".join(x for x in (a.get("enemy_player"), a.get("tower")) if x)
            line = f"{mark} **{a['player']}** ({', '.join(a['team'])}) → {target}"
            line += f" [{where}]" if where else ""
            line += f" — {a['note']}" if a.get("note") else ""
            lines.append(line)
    else:
        lines += ["", "Aucune attaque enregistrée pour l'instant."]
    limit = summary["settings"]["attacks_per_member"]
    left = [
        f"{m['player']} ({war['remaining'].get(m['id'], limit)}/{limit})"
        for m in summary["members"]
        if war["remaining"].get(m["id"], limit) > 0
    ]
    lines += ["", "Attaques restantes : " + (", ".join(left) if left else "aucune, bravo !")]
    return _chunks(lines)


def counters_report(summary: dict[str, Any]) -> list[str]:
    """Contres connus pour Discord : par défense ennemie, les équipes testées et leur bilan."""
    guild = summary["guild"]
    lines = [f"**Contres connus en GvG{' — ' + guild if guild else ''}**"]
    if not summary["counters"]:
        lines.append("Aucun contre enregistré pour l'instant.")
    return _chunks(lines + counter_lines(summary["counters"]))


def counter_lines(counters: list[dict[str, Any]]) -> list[str]:
    """Une section par défense ennemie : équipes testées (✅ gagnée, ⚖️ mitigée, ❌ perdue)."""
    lines: list[str] = []
    for c in counters:
        lines += ["", f"__{' · '.join(c['enemy_team'])}__ ({c['wins']} V / {c['losses']} D)"]
        for t in c["teams"]:
            mark = "✅" if t["wins"] and not t["losses"] else "❌" if not t["wins"] else "⚖️"
            lines.append(f"{mark} {', '.join(t['team'])} — {t['wins']} V / {t['losses']} D")
    return lines
