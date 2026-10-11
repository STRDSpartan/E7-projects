"""Effets d'une compétence (soins, barrières, buffs, débuffs, jauge) à partir de son texte.

Entrée : le texte anglais de la compétence et ses étiquettes d'effets (base E7GW, ex.
« Increase Attack », « Heal », « Stun »). Les étiquettes disent QUELS effets existent ; le
texte précise la cible (lanceur, tous les alliés, cible, tous les ennemis), la durée
(« for 2 turns »), la probabilité (« has a 75% chance ») et les pourcentages de jauge.

Les textes du jeu donnent rarement le montant des soins et barrières (« proportionnel à
l'Attaque du lanceur ») : la statistique de référence est lue ici, le coefficient vient
d'E7Calc pour les barrières, sinon d'une valeur type (`estimated: True`).
"""

from __future__ import annotations

import re
from typing import Any

# étiquette E7GW → (type, effet, mot-clé recherché dans le texte)
BUFFS = {
    "Increase Attack": "atk_up",
    "Increase Defense": "def_up",
    "Increase Speed": "spd_up",
    "Increase Critical Hit Chance": "cc_up",
    "Increase Critical Hit Damage": "cd_up",
    "Immunity": "immunity",
    "Invincible": "invincible",
    "Stealth": "stealth",
    "Immortal": "immortal",
}
DEBUFFS = {
    "Decrease Defense": "def_down",
    "Decrease Attack": "atk_down",
    "Decrease Speed": "spd_down",
    "Stun": "stun",
    "Sleep": "sleep",
    "Silence": "silence",
    "Provoke": "provoke",
    "Unhealable": "unhealable",
}
KEYWORDS = {
    "atk_up": r"attack",
    "def_up": r"defense",
    "spd_up": r"speed",
    "cc_up": r"critical hit chance",
    "cd_up": r"critical hit damage",
    "immunity": r"immunity",
    "invincible": r"invincib",
    "stealth": r"stealth",
    "immortal": r"immortal",
    "def_down": r"defense",
    "atk_down": r"attack",
    "spd_down": r"speed",
    "stun": r"stun",
    "sleep": r"sleep",
    "silence": r"silence",
    "provoke": r"provok",
    "unhealable": r"unhealable",
}
# coefficients types quand le texte ne chiffre pas le montant (signalés comme estimés)
HEAL_DEFAULT = {"hp": 0.15, "atk": 0.6, "def": 0.8}
BARRIER_DEFAULT = {"hp": 0.15, "atk": 0.6, "def": 0.8}


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!])\s+", text) if s.strip()]


def _sentence_for(text: str, keyword: str, verbs: str) -> str | None:
    for s in _sentences(text):
        low = s.lower()
        if re.search(keyword, low) and re.search(verbs, low):
            return s
    for s in _sentences(text):
        if re.search(keyword, s.lower()):
            return s
    return None


TARGETS = (
    (r"\ball allies\b|\ballies\b", "allies"),
    (r"\b(an ally|the ally|ally with|an ally's)\b", "ally"),
    (r"\ball enemies\b", "enemies"),
    (r"\bthe caster\b|\bcaster's\b|\bthemsel\w*|\boneself\b", "self"),
    (r"\bthe (target|enemy)\b|\btarget's\b", "target"),
)


def _target(sentence: str, default: str, keyword: str | None = None) -> str:
    """Cible la plus proche du mot-clé de l'effet dans la phrase (sinon valeur par défaut)."""
    low = sentence.lower()
    found = re.search(keyword, low) if keyword else None
    anchor = found.start() if found else 0
    best: tuple[int, str] | None = None
    for pattern, name in TARGETS:
        if name == "self" and default in ("target", "enemies"):
            pattern = r"\b(from|to|on) the caster\b"  # débuff sur soi : « inflige ... au lanceur »
        for m in re.finditer(pattern, low):
            dist = abs(m.start() - anchor)
            if best is None or dist < best[0]:
                best = (dist, name)
    return best[1] if best else default


def _turns(sentence: str, default: int) -> int:
    m = re.search(r"for (\d+) turns?", sentence.lower())
    return int(m.group(1)) if m else default


def _chance(sentence: str) -> float:
    m = re.search(r"(\d+(?:\.\d+)?)% chance", sentence.lower())
    return float(m.group(1)) / 100 if m else 1.0


def _scale(text: str) -> str:
    low = text.lower()
    if "max health" in low:
        return "hp"
    if "defense" in low and "proportional to the caster's defense" in low:
        return "def"
    return "atk" if "attack" in low else "hp"


def parse_effects(
    text: str, tags: list[str], *, aoe: bool = False, barrier: dict[str, float] | None = None
) -> list[dict[str, Any]]:
    """Effets reconnus d'une compétence ; `barrier` : coefficients E7Calc s'ils sont connus."""
    effects: list[dict[str, Any]] = []
    tagset = set(tags)
    ignores_resist = "Ignore Effect Resistance" in tagset
    for tag, name in BUFFS.items():
        if tag not in tagset:
            continue
        s = _sentence_for(text, KEYWORDS[name], r"increas|grant|gain") or text
        effects.append(
            {
                "type": "buff",
                "effect": name,
                "target": _target(s, "self", KEYWORDS[name]),
                "turns": _turns(s, 2),
            }
        )
    for tag, name in DEBUFFS.items():
        if tag not in tagset:
            continue
        s = (
            _sentence_for(text, KEYWORDS[name], r"decreas|inflict|chance|stun|silenc|provok")
            or text
        )
        effects.append(
            {
                "type": "debuff",
                "effect": name,
                "target": _target(s, "enemies" if aoe else "target", KEYWORDS[name]),
                "turns": _turns(s, 1 if name in ("stun", "sleep") else 2),
                "chance": _chance(s),
                "ignore_resist": ignores_resist,
            }
        )
    if "Heal" in tagset:
        s = _sentence_for(text, r"recover|heal", r"recover|heal") or text
        m = re.search(
            r"by (\d+(?:\.\d+)?)% of (?:the caster's )?(max health|attack|defense)", s.lower()
        )
        if m:
            stat = {"max health": "hp", "attack": "atk", "defense": "def"}[m.group(2)]
            ratio, estimated = float(m.group(1)) / 100, False
        else:
            stat = _scale(s)
            ratio, estimated = HEAL_DEFAULT[stat], True
        effects.append(
            {
                "type": "heal",
                "target": _target(s, "self", r"recover|heal"),
                "stat": stat,
                "ratio": ratio,
                "estimated": estimated,
            }
        )
    if "Barrier" in tagset or "Multilayer Barrier (Undispellable)" in tagset:
        s = _sentence_for(text, r"barrier", r"grant|barrier") or text
        if barrier:
            stat, ratio = next(iter(barrier.items()))
            estimated = False
        else:
            stat = _scale(_sentence_for(text, r"barrier strength|proportional", r"barrier") or s)
            ratio, estimated = BARRIER_DEFAULT[stat], True
        effects.append(
            {
                "type": "barrier",
                "target": _target(s, "self", r"barrier"),
                "stat": stat,
                "ratio": ratio,
                "turns": _turns(s, 2),
                "estimated": estimated,
            }
        )
    for tag, sign in (("Increase Combat Readiness", 1), ("Decrease Combat Readiness", -1)):
        if tag not in tagset:
            continue
        verb = r"increas\w*" if sign > 0 else r"decreas\w*"
        anchor = verb + r" combat readiness"
        s = _sentence_for(text, anchor, verb) or text
        low = s.lower()
        found = re.search(anchor, low)
        start = found.start() if found else 0
        m = re.search(r"combat readiness[^.]*?by (\d+)%", low[start:])
        effects.append(
            {
                "type": "gauge",
                "amount": sign * (int(m.group(1)) if m else 20),
                "target": _target(
                    s, "self" if sign > 0 else ("enemies" if aoe else "target"), anchor
                ),
                "chance": _chance(s) if sign < 0 else 1.0,
            }
        )
    if "Buff Dispel (Strip)" in tagset:
        s = _sentence_for(text, r"remov", r"buff") or text
        effects.append(
            {
                "type": "strip",
                "target": _target(s, "enemies" if aoe else "target"),
                "all": "all buff" in s.lower(),
            }
        )
    if "Debuff Dispel (Cleanse)" in tagset:
        s = _sentence_for(text, r"remov|dispel", r"debuff") or text
        effects.append(
            {"type": "cleanse", "target": _target(s, "allies"), "all": "all debuff" in s.lower()}
        )
    return effects
