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
from e7showcase.app.profiles import ProfileStore
from e7showcase.reference import load

TEAM_SIZE = 3
TEAMS = 2
MAX_TEXT = 40
RESULTS = ("win", "loss")
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
            },
            "defenses": defenses,
            "wars": wars,
        }

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    # --- validation
    def _roster_names(self, member: str) -> dict[str, str]:
        if not self.profiles.exists(member):
            raise GvgError("membre introuvable")
        return {h.name.casefold(): h.name for h in self.profiles.load(member).heroes}

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

    # --- lecture
    def summary(self) -> dict[str, Any]:
        data = self._read()
        guild = self.guild.summary()
        names = {m["id"]: m["player"] for m in guild["members"]}
        members = []
        for m in guild["members"]:
            roster = self.profiles.load(m["id"])
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
            "hero_names": sorted(
                {h.get("fr") or h["en"] for h in load("heroes")["heroes"] if h.get("stars")}
            ),
        }

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
    messages: list[str] = []
    for line in lines:  # découpe en messages Discord, sans couper une ligne
        if messages and len(messages[-1]) + len(line) + 1 <= DISCORD_LIMIT:
            messages[-1] += "\n" + line
        else:
            messages.append(line[:DISCORD_LIMIT])
    csv = "\n".join(";".join(_csv_cell(c) for c in row) for row in rows)
    return {"text": "\n".join(lines), "messages": messages, "csv": "﻿" + csv + "\n"}


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
    for c in summary["counters"]:
        lines += ["", f"__{' · '.join(c['enemy_team'])}__ ({c['wins']} V / {c['losses']} D)"]
        for t in c["teams"]:
            mark = "✅" if t["wins"] and not t["losses"] else "❌" if not t["wins"] else "⚖️"
            lines.append(f"{mark} {', '.join(t['team'])} — {t['wins']} V / {t['losses']} D")
    return _chunks(lines)
