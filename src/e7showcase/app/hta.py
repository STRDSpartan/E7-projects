"""Héritage des temps anciens (HTA) : préparation de la saison d'exploration de guilde.

    <dossier de données>/hta.json

- saison : numéro, étage atteint, boss vaincus, rations du jour, retraits autorisés, date de
  fermeture du bureau de change. Tout est saisi par les joueurs, rien n'est lu dans le jeu ;
- répartition : pour chaque membre de la guilde, son élément principal (feu, glace ou terre),
  sa spécialité lumière/ténèbres, ses retraits utilisés et ses héros enrôlés ;
- rôles : rôle HTA d'un héros (double attaque, DPS, support, soin) et colonne « solo ». Le rôle
  est déduit des compétences (`skills.json`), et la guilde peut le corriger ; ces corrections
  s'exportent et s'importent pour être partagées ;
- boss : fiche par boss d'étage (mécaniques notées, équipe d'un membre) et estimation des
  dégâts de l'équipe avec le calculateur de dégâts ;
- reliques : liste et priorité notées par le joueur.

Les héros enrôlés et les équipes sont validés contre le roster du membre.
"""

from __future__ import annotations

import json
import secrets
from datetime import date
from pathlib import Path
from typing import Any

from e7showcase.app.guild import GuildStore
from e7showcase.app.gvg import _chunks
from e7showcase.app.jsonfile import write_json
from e7showcase.app.profiles import ProfileStore
from e7showcase.models.hero import Hero
from e7showcase.reference import hero_info

ELEMENTS = ("fire", "ice", "earth", "light", "dark")  # ordre du jeu
PRIMARY = ("fire", "ice", "earth")  # élément principal conseillé, monté au niveau 10
SPECIALTIES = ("light", "dark")  # spécialistes des boss de fin d'étage
ELEMENT_FR = {
    "fire": "Feu",
    "ice": "Glace",
    "earth": "Terre",
    "light": "Lumière",
    "dark": "Ténèbres",
}
ROLES = ("dual", "dps", "support", "healer")  # ordre de priorité des guides communautaires
ROLE_FR = {"dual": "Double attaque", "dps": "DPS", "support": "Support", "healer": "Soin"}
TEAM_SIZE = 4
MAX_ENLISTED = 40
MAX_FLOOR = 10
MAX_TEXT = 40
MAX_NOTE = 200
MAX_BOSSES = 30
MAX_RELICS = 60
MAX_TIERS = 500
SUGGESTIONS = 12
_ALLIES = {"allies", "ally"}


class HtaError(ValueError):
    pass


def _text(value: Any, limit: int = MAX_TEXT) -> str:
    return str(value or "").strip()[:limit]


def _int(value: Any, low: int, high: int, default: int | None) -> int | None:
    if value in (None, ""):
        return default
    try:
        return min(max(int(value), low), high)
    except (TypeError, ValueError) as exc:
        raise HtaError("nombre attendu") from exc


def _date(value: Any) -> str:
    text = _text(value, 10)
    if not text:
        return ""
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise HtaError("date attendue au format AAAA-MM-JJ") from exc


def _key(name: str) -> str:
    return name.strip().casefold()


# --- rôles HTA déduits des compétences
def hero_element(hero: Hero) -> str | None:
    element = hero.element or (hero_info(hero.name) or {}).get("element")
    return element if element in ELEMENTS else None


def guess_role(name: str) -> str:
    """Rôle HTA d'un héros d'après ses compétences : double attaque, soin, support ou DPS."""
    from e7showcase.calc.damage import hero_skills

    data = hero_skills(name) or {}
    cls = data.get("class") or (hero_info(name) or {}).get("role")
    effects = [e for s in data.get("skills", {}).values() for e in s.get("effects", [])]
    types = {e.get("type") for e in effects}
    if "dual" in types:
        return "dual"
    ally = {e.get("type") for e in effects if e.get("target") in _ALLIES}
    if cls == "soul-weaver" or "revive_ally" in types or "heal" in ally:
        return "healer"
    if cls == "knight" or len(ally & {"buff", "barrier", "cleanse"}) >= 2:
        return "support"
    return "dps"


class HtaStore:
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

        def section(name: str) -> dict[str, Any]:
            value = data.get(name)
            return value if isinstance(value, dict) else {}

        def rows(name: str) -> list[dict[str, Any]]:
            return [r for r in data.get(name, []) if isinstance(r, dict) and r.get("id")]

        return {
            "season": section("season"),
            "members": section("members"),
            "tiers": section("tiers"),
            "bosses": rows("bosses"),
            "relics": rows("relics"),
        }

    def _write(self, data: dict[str, Any]) -> None:
        write_json(self.path, data, ensure_ascii=False, indent=1)

    # --- validation
    def _roster(self, member: str) -> list[Hero]:
        if not self.profiles.exists(member):
            raise HtaError("membre introuvable")
        return list(self.profiles.peek(member).heroes)

    def _heroes(self, member: str, names: Any, limit: int) -> list[str]:
        roster = {_key(h.name): h.name for h in self._roster(member)}
        if not isinstance(names, list) or len(names) > limit:
            raise HtaError(f"{limit} héros au plus")
        out: list[str] = []
        for raw in names:
            key = _key(_text(raw))
            if not key:
                continue
            if key not in roster:
                raise HtaError(f"{_text(raw)} n'est pas dans le roster du membre")
            if roster[key] not in out:
                out.append(roster[key])
        return out

    @staticmethod
    def _row(rows: list[dict[str, Any]], row_id: str, what: str) -> dict[str, Any]:
        for row in rows:
            if row["id"] == row_id:
                return row
        raise HtaError(f"{what} introuvable")

    # --- saison
    def update_season(self, body: dict[str, Any]) -> None:
        data = self._read()
        season = data["season"]
        for field, low, high in (
            ("number", 1, 999),
            ("floor", 1, MAX_FLOOR),
            ("provisions", 0, 99999),
            ("withdrawals", 0, 99),
        ):
            if field in body:
                season[field] = _int(body[field], low, high, None)
        if "exchange_closes" in body:
            season["exchange_closes"] = _date(body["exchange_closes"])
        if "notice" in body:  # consigne de la guilde (plus longue que le tableau du jeu)
            season["notice"] = _text(body["notice"], 1000)
        if isinstance(body.get("bosses_killed"), list):
            season["bosses_killed"] = [t for t in (_text(b) for b in body["bosses_killed"]) if t][
                :MAX_BOSSES
            ]
        self._write(data)

    def new_season(self, number: Any = None) -> None:
        """Nouvelle saison : enrôlements, retraits et boss vaincus remis à zéro."""
        data = self._read()
        previous = data["season"].get("number")
        default = previous + 1 if isinstance(previous, int) else None
        data["season"] = {
            "number": _int(number, 1, 999, default),
            "withdrawals": data["season"].get("withdrawals"),
        }
        for plan in data["members"].values():
            if isinstance(plan, dict):
                plan.update(enlisted=[], withdrawals_used=0)
        self._write(data)

    # --- répartition des membres
    def set_member(self, member: str, body: dict[str, Any]) -> None:
        self._roster(member)
        data = self._read()
        raw = data["members"].get(member)
        plan: dict[str, Any] = raw if isinstance(raw, dict) else {}
        if "element" in body:
            element = _text(body["element"])
            if element and element not in PRIMARY:
                raise HtaError("élément principal attendu : feu, glace ou terre")
            plan["element"] = element
        if "specialty" in body:
            specialty = _text(body["specialty"])
            if specialty and specialty not in SPECIALTIES:
                raise HtaError("spécialité attendue : lumière ou ténèbres")
            plan["specialty"] = specialty
        if "withdrawals_used" in body:
            plan["withdrawals_used"] = _int(body["withdrawals_used"], 0, 99, 0)
        if "enlisted" in body:
            plan["enlisted"] = self._heroes(member, body["enlisted"], MAX_ENLISTED)
        data["members"][member] = plan
        self._write(data)

    # --- rôles (corrections de la guilde)
    def set_tier(self, body: dict[str, Any]) -> None:
        name = _text(body.get("hero"))
        info = hero_info(name)
        if not name or info is None:
            raise HtaError(f"héros inconnu : {name}")
        role = _text(body.get("role"))
        if role and role not in ROLES:
            raise HtaError("rôle inconnu")
        data = self._read()
        canonical = str(info.get("fr") or info.get("en") or name)
        entry = {"role": role, "solo": bool(body.get("solo")), "note": _text(body.get("note"), 120)}
        if not role and not entry["solo"] and not entry["note"]:
            data["tiers"].pop(canonical, None)  # retour au rôle déduit
        else:
            if canonical not in data["tiers"] and len(data["tiers"]) >= MAX_TIERS:
                raise HtaError(f"{MAX_TIERS} héros au plus")
            data["tiers"][canonical] = entry
        self._write(data)

    def export_tiers(self) -> dict[str, Any]:
        return {"format": "zealot-hta-tiers", "version": 1, "tiers": self._read()["tiers"]}

    def import_tiers(self, payload: Any) -> int:
        """Rôles partagés par un membre de la guilde (fichier exporté) : ajoutés aux siens."""
        if not isinstance(payload, dict) or payload.get("format") != "zealot-hta-tiers":
            raise HtaError("fichier de rôles HTA attendu (exporté depuis Zealot)")
        tiers = payload.get("tiers")
        if not isinstance(tiers, dict):
            raise HtaError("fichier de rôles HTA vide")
        count = 0
        for name, entry in list(tiers.items())[:MAX_TIERS]:
            if isinstance(entry, dict):
                self.set_tier({**entry, "hero": name})
                count += 1
        return count

    def role(self, name: str, tiers: dict[str, Any] | None = None) -> dict[str, Any]:
        info = hero_info(name) or {}
        canonical = str(info.get("fr") or info.get("en") or name)
        entry = (tiers if tiers is not None else self._read()["tiers"]).get(canonical) or {}
        role = entry.get("role") if entry.get("role") in ROLES else None
        return {
            "role": role or guess_role(name),
            "auto": role is None,
            "solo": bool(entry.get("solo")),
            "note": str(entry.get("note") or ""),
        }

    # --- boss
    def add_boss(self, body: dict[str, Any]) -> str:
        data = self._read()
        if len(data["bosses"]) >= MAX_BOSSES:
            raise HtaError(f"{MAX_BOSSES} fiches de boss au plus")
        boss = {"id": secrets.token_hex(5)}
        self._fill_boss(boss, body)
        data["bosses"].append(boss)
        self._write(data)
        return boss["id"]

    def update_boss(self, boss_id: str, body: dict[str, Any]) -> None:
        data = self._read()
        self._fill_boss(self._row(data["bosses"], boss_id, "boss"), body)
        self._write(data)

    def _fill_boss(self, boss: dict[str, Any], body: dict[str, Any]) -> None:
        if "name" in body or "name" not in boss:
            boss["name"] = _text(body.get("name"))
            if not boss["name"]:
                raise HtaError("nom du boss manquant")
        if "floor" in body:
            boss["floor"] = _int(body["floor"], 1, MAX_FLOOR, None)
        if "element" in body:
            element = _text(body["element"])
            if element and element not in ELEMENTS:
                raise HtaError("élément inconnu")
            boss["element"] = element
        for field, high in (("hp", 10**9), ("def", 50000)):
            if field in body:
                boss[field] = _int(body[field], 0, high, None)
        if "mechanics" in body:
            boss["mechanics"] = _text(body["mechanics"], MAX_NOTE)
        if "member" in body or "team" in body:
            member = _text(body.get("member", boss.get("member")), 60)
            team = body.get("team", boss.get("team", []))
            boss["member"] = member
            boss["team"] = self._heroes(member, team, TEAM_SIZE) if member else []

    def delete_boss(self, boss_id: str) -> None:
        data = self._read()
        self._row(data["bosses"], boss_id, "boss")
        data["bosses"] = [b for b in data["bosses"] if b["id"] != boss_id]
        self._write(data)

    def estimate(self, boss_id: str) -> dict[str, Any]:
        """Dégâts attendus de l'équipe contre le boss (meilleure compétence de chaque héros)."""
        from e7showcase.app.simulator import fighter
        from e7showcase.calc.damage import Fighter, damage_table

        boss = self._row(self._read()["bosses"], boss_id, "boss")
        if not boss.get("member") or not boss.get("team"):
            raise HtaError("choisissez d'abord l'équipe de ce boss")
        target = Fighter(
            name=boss["name"],
            atk=0,
            hp=float(boss.get("hp") or 0) or 1,
            defense=float(boss.get("def") or 1000),
            element=boss.get("element") or None,
        )
        heroes = {h.name: h for h in self._roster(boss["member"])}
        rows = []
        for name in boss["team"]:
            hero = heroes.get(name)
            best: dict[str, Any] | None = None
            if hero is not None:
                table = damage_table(fighter(hero), target)
                best = max(table, key=lambda r: r["expected"] or 0, default=None)
            rows.append(
                {
                    "hero": name,
                    "skill": best["skill"] if best else None,
                    "expected": best["expected"] if best else None,
                }
            )
        total = sum(r["expected"] or 0 for r in rows)
        hp = boss.get("hp") or 0
        return {
            "boss": boss["name"],
            "rows": rows,
            "total": total,
            "rounds": -(-hp // total) if hp and total else None,  # tours de l'équipe, arrondi haut
        }

    # --- reliques
    def add_relic(self, body: dict[str, Any]) -> str:
        data = self._read()
        if len(data["relics"]) >= MAX_RELICS:
            raise HtaError(f"{MAX_RELICS} reliques au plus")
        name = _text(body.get("name"))
        if not name:
            raise HtaError("nom de la relique manquant")
        relic = {
            "id": secrets.token_hex(5),
            "name": name,
            "priority": _int(body.get("priority"), 1, 3, 2),
            "note": _text(body.get("note"), 120),
        }
        data["relics"].append(relic)
        self._write(data)
        return str(relic["id"])

    def delete_relic(self, relic_id: str) -> None:
        data = self._read()
        self._row(data["relics"], relic_id, "relique")
        data["relics"] = [r for r in data["relics"] if r["id"] != relic_id]
        self._write(data)

    # --- préparateur d'enrôlement
    def suggestions(self, member: str, element: str | None = None) -> list[dict[str, Any]]:
        """Héros du roster à enrôler : élément choisi, puis rôle, colonne solo et équipement."""
        roster = self._roster(member)
        data = self._read()
        plan = data["members"].get(member) or {}
        wanted = {element} if element else {plan.get("element"), plan.get("specialty")} - {None, ""}
        tiers = data["tiers"]
        out = []
        for hero in roster:
            hero_el = hero_element(hero)
            if wanted and hero_el not in wanted:
                continue
            role = self.role(hero.name, tiers)
            out.append(
                {
                    "name": hero.name,
                    "element": hero_el,
                    **role,
                    "power": hero.power,
                    "gear_score": hero.gear_score_avg,
                    "spd": hero.stats.spd or None,
                    "hp": hero.stats.hp or None,
                }
            )
        out.sort(key=lambda r: (not r["solo"], ROLES.index(r["role"]), -(r["power"] or 0)))
        return out[:SUGGESTIONS] if wanted else out

    # --- vue d'ensemble
    def summary(self) -> dict[str, Any]:
        data = self._read()
        guild = self.guild.summary()
        members = []
        for m in guild["members"]:
            raw = data["members"].get(m["id"])
            plan: dict[str, Any] = raw if isinstance(raw, dict) else {}
            members.append(
                {
                    "id": m["id"],
                    "player": m["player"],
                    "element": plan.get("element") or "",
                    "specialty": plan.get("specialty") or "",
                    "withdrawals_used": plan.get("withdrawals_used") or 0,
                    "enlisted": plan.get("enlisted") or [],
                    "roster": [h.name for h in self._roster(m["id"])],
                }
            )
        counts = {e: 0 for e in ELEMENTS}
        for m in members:
            for e in (m["element"], m["specialty"]):
                if e:
                    counts[e] += 1
        season = data["season"]
        return {
            "guild": guild["name"],
            "season": {
                "number": season.get("number"),
                "floor": season.get("floor"),
                "provisions": season.get("provisions"),
                "withdrawals": season.get("withdrawals"),
                "exchange_closes": season.get("exchange_closes") or "",
                "notice": season.get("notice") or "",
                "bosses_killed": season.get("bosses_killed") or [],
            },
            "members": members,
            "coverage": {
                "counts": counts,
                "missing": [e for e in ELEMENTS if not counts[e]],
                "undecided": [m["player"] for m in members if not m["element"]],
            },
            "bosses": data["bosses"],
            "relics": sorted(data["relics"], key=lambda r: (r.get("priority") or 2, r["name"])),
            "tiers": data["tiers"],
            "elements": {e: ELEMENT_FR[e] for e in ELEMENTS},
            "roles": ROLE_FR,
        }


def hta_report(summary: dict[str, Any], today: date | None = None) -> list[str]:
    """Plan HTA de la guilde pour Discord (messages ≤ 2 000 caractères)."""
    day = (today or date.today()).strftime("%d/%m/%Y")
    s = summary["season"]
    title = f"Saison {s['number']}" if s["number"] else "Saison en cours"
    lines = [f"**Héritage des temps anciens — {summary['guild'] or 'Guilde'}** · {title} · {day}"]
    state = [
        f"Étage {s['floor']}" if s["floor"] else "",
        f"Boss vaincus : {', '.join(s['bosses_killed'])}" if s["bosses_killed"] else "",
        f"Bureau de change jusqu'au {s['exchange_closes']}" if s["exchange_closes"] else "",
    ]
    if any(state):
        lines.append(" · ".join(x for x in state if x))
    if s["notice"]:
        lines += ["", s["notice"]]
    lines += ["", "__Répartition des éléments__"]
    for element in ELEMENTS:
        players = [
            m["player"] for m in summary["members"] if element in (m["element"], m["specialty"])
        ]
        label = ELEMENT_FR[element]
        lines.append(f"{label} : {', '.join(players)}" if players else f"{label} : ⚠️ personne")
    if summary["coverage"]["undecided"]:
        lines.append("Sans élément choisi : " + ", ".join(summary["coverage"]["undecided"]))
    by_id = {m["id"]: m["player"] for m in summary["members"]}
    if summary["bosses"]:
        lines += ["", "__Équipes contre les boss__"]
        for b in summary["bosses"]:
            where = f" (étage {b['floor']})" if b.get("floor") else ""
            team = ", ".join(b.get("team") or []) or "équipe à définir"
            who = by_id.get(b.get("member") or "", "")
            lines.append(f"**{b['name']}**{where} : {team}" + (f" — {who}" if who else ""))
            if b.get("mechanics"):
                lines.append(f"> {b['mechanics']}")
    top = [r["name"] for r in summary["relics"] if r.get("priority") == 1]
    if top:
        lines += ["", "__Reliques prioritaires__", ", ".join(top)]
    return _chunks(lines)
