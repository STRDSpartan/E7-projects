"""Effets des artefacts depuis la base publique E7GW (https://e7gw.xyz/artifacts).

La page liste chaque artefact avec son effet du niveau de compétence 1 au niveau maximum
(« 5% → 10% ») et son texte d'ambiance. Seul ce texte factuel est repris dans
data/reference/artifacts.json (par scripts/update_reference.py) ; aucune image.
Le robots.txt du site autorise /artifacts.
"""

from __future__ import annotations

import html
import re
import unicodedata
from typing import Any

URL = "https://e7gw.xyz/artifacts"

_CARD_RE = re.compile(
    r'<div class="artifact-card[^"]*"\s+id="([^"]+)"\s+data-name="[^"]*"\s+'
    r'data-class="([^"]*)"\s+data-rarity="(\d)">(.*?)</p>\s*</div>',
    re.S,
)
_NAME_RE = re.compile(r'<div class="truncate font-semibold"([^>]*)>([^<]+)</div>')
_EFFECT_SPLIT = '<p class="mt-2 text-xs leading-snug text-mut">'
# Noms différents entre E7GW et e7codex (clé normalisée E7GW → clé e7codex)
ALIASES = {"elegiaccandles": "elegiaccandle", "ascendingaxe": "axeofheavenlymandate"}


def key(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", ascii_name)


def parse_artifacts(page: str) -> list[dict[str, Any]]:
    """Cartes de la page /artifacts : nom, classe, rareté, effet, texte d'ambiance."""
    cards: list[dict[str, Any]] = []
    for _gid, role, rarity, body in _CARD_RE.findall(page):
        name = _NAME_RE.search(body)
        if not name:
            continue
        lore = re.search(r'title="([^"]*)"', name.group(1))
        effect = html.unescape(re.sub(r"<[^>]+>", "", body.split(_EFFECT_SPLIT)[-1])).strip()
        cards.append(
            {
                "name": html.unescape(name.group(2)).strip(),
                "role": role,
                "rarity": int(rarity),
                "effect": None if effect.startswith("No effect") else effect.replace("..", "."),
                "lore": html.unescape(lore.group(1)) if lore else None,
            }
        )
    return cards


def enrich(artifacts: list[dict[str, Any]], cards: list[dict[str, Any]]) -> int:
    """Ajoute `effect_en` / `lore_en` aux artefacts du référentiel ; renvoie le nombre enrichi."""
    by_key = {key(a["en"]): a for a in artifacts if a.get("en")}
    done = 0
    for card in cards:
        art = by_key.get(ALIASES.get(key(card["name"]), key(card["name"])))
        if art is None:
            continue
        if card["effect"]:
            art["effect_en"] = card["effect"]
            done += 1
        if card["lore"]:
            art["lore_en"] = card["lore"]
    return done


# --- pages héros (/hero/<slug>) : compétences, temps de recharge, améliorations ------------
HERO_URL = "https://e7gw.xyz/hero/{slug}"
_SKILL_SPLIT = '<div class="rounded-lg border border-line bg-panel2 p-4">'


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def parse_hero_page(page: str) -> dict[str, Any]:
    """Nom et compétences d'une page héros : texte, recharge (après améliorations), étiquettes."""
    title = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S)
    section = page.split(">Abilities</h2>", 1)[-1].split("</section>", 1)[0]
    skills: list[dict[str, Any]] = []
    for block in section.split(_SKILL_SPLIT)[1:]:
        sid = re.search(r'text-brand">\s*(S\d)\s*<', block)
        desc = re.search(r'<p class="text-sm text-mut">(.*?)</p>', block, re.S)
        if not sid or not desc or any(s["id"] == sid.group(1).lower() for s in skills):
            continue  # bloc sans texte (vignette répétée plus bas dans la page)
        name = re.search(r'<span class="font-semibold">(.*?)</span>', block, re.S)
        cd = re.search(r"CD\s*(\d+)\s*Turn", _text(block))
        burn = re.search(r"Soulburn:</span>\s*<span[^>]*>(.*?)</span>", block, re.S)
        enhancements = [_text(li) for li in re.findall(r"<li>(.*?)</li>", block, re.S)]
        cooldown = int(cd.group(1)) if cd else 0
        cooldown -= sum(1 for e in enhancements if re.search(r"-\s*1 turn cooldown", e, re.I))
        skills.append(
            {
                "id": sid.group(1).lower(),
                "name": _text(name.group(1)) if name else "",
                "cooldown": max(cooldown, 0),
                "text": _text(desc.group(1)),
                "soulburn": _text(burn.group(1)) if burn else None,
                "tags": [html.unescape(t) for t in re.findall(r'data-fx-name="([^"]+)"', block)],
            }
        )
    return {"name": _text(title.group(1)) if title else "", "skills": skills}


def hero_slugs(heroes_page: str) -> list[str]:
    """Identifiants des pages héros listées sur /heroes."""
    return sorted(set(re.findall(r'href="https://e7gw\.xyz/hero/([a-z0-9-]+)"', heroes_page)))


def merge_skills(
    calc_heroes: dict[str, dict[str, Any]], pages: list[dict[str, Any]]
) -> tuple[int, int]:
    """Ajoute recharge, texte et effets (E7GW) aux compétences des héros d'E7Calc.

    Les compétences sans dégâts (soins, buffs) absentes d'E7Calc sont ajoutées sans taux.
    Renvoie (héros enrichis, compétences avec au moins un effet).
    """
    from e7showcase.parsers.skill_effects import parse_effects, parse_trigger

    by_key = {key(k.replace("_", " ")): v for k, v in calc_heroes.items()}
    heroes = with_effects = 0
    for page in pages:
        hero = by_key.get(key(page["name"].replace("&", "and")))
        if hero is None:
            continue
        heroes += 1
        barrier = hero.get("barrier") or {}
        for sk in page["skills"]:
            entry = hero["skills"].setdefault(sk["id"], {"rate": None, "pow": 1, "enhance": []})
            aoe = "AoE" in sk["tags"] or bool(entry.get("aoe"))
            ratios = barrier.get("ratios") if barrier.get("skill") in (None, sk["id"]) else None
            effects = parse_effects(sk["text"], sk["tags"], aoe=aoe, barrier=ratios)
            passive = sk["id"] != "s1" and sk["cooldown"] == 0
            entry.update(
                name=sk["name"],
                cooldown=sk["cooldown"],
                passive=passive,
                effects=effects,
            )
            if trigger := parse_trigger(sk["text"], passive=passive):
                entry["trigger"] = trigger
            entry.setdefault("aoe", aoe)
            with_effects += bool(effects)
    return heroes, with_effects
