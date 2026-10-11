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
    "Increase Attack (Greater)": "atk_up_great",
    "Increase Evasion": "evasion",
    "Skill Nullifier": "nullifier",
    "Increase Effectiveness": "eff_up",
    "Indomitable (Undispellable)": "indomitable",
    "Superhumanization (Undispellable)": "superhuman",
    "Morale": "morale",
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
    "Burn": "burn",
    "Bleed": "bleed",
    "Poison": "poison",
    "Decrease Hit Chance": "hit_down",
    "Cannot Buff": "no_buff",
    "Fear": "fear",
    "Bind": "bind",
    "Rupture": "rupture",
    "Seal": "seal",
    "Venom": "venom",
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
    "atk_up_great": r"attack",
    "evasion": r"evasion",
    "nullifier": r"nullifier",
    "burn": r"burn",
    "bleed": r"bleed",
    "poison": r"poison",
    "hit_down": r"hit chance",
    "no_buff": r"unable to be buffed|cannot be buffed|buff",
    "eff_up": r"effectiveness",
    "indomitable": r"indomitable",
    "superhuman": r"superhuman",
    "morale": r"morale",
    "fear": r"fear",
    "bind": r"bind",
    "rupture": r"rupture",
    "seal": r"seal",
    "venom": r"venom",
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
    (r"\b(the )?ally in the back row\b|\bback row ally\b", "back_row"),
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


def _buff_target(target: str) -> str:
    """Un buff ne vise jamais l'ennemi : « attaque tous les ennemis et augmente l'Attaque »."""
    return "self" if target in ("enemies", "target") else target


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
                "target": _buff_target(_target(s, "self", KEYWORDS[name])),
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
    if "Extra Turn" in tagset:
        s = _sentence_for(text, r"extra turn", r"grant|extra turn") or text
        low = s.lower()
        if "soulburn" not in low:  # tour supplémentaire de l'âme brûlée : non simulé
            effects.append(
                {
                    "type": "extra_turn",
                    "chance": _chance(s),
                    "on_kill": bool(re.search(r"defeat|kill", low)),
                }
            )
    if "Dual Attack" in tagset and "dual attack" in text.lower():  # sinon : âme brûlée
        effects.append({"type": "dual"})
    for tag, sign in (("Decrease Skill Cooldown (Self)", -1), ("Increase Skill Cooldown", 1)):
        if tag not in tagset:
            continue
        s = _sentence_for(text, r"cooldown", r"decreas|increas|reset") or text
        low = s.lower()
        m = re.search(r"cooldowns? (?:of [^.]*?)?by (\d+) turn", low)
        amount = 99 if re.search(r"reset|fully", low) else (int(m.group(1)) if m else 1)
        effects.append(
            {
                "type": "cooldown",
                "amount": sign * amount,
                "target": "self" if sign < 0 else ("enemies" if aoe else "target"),
                "chance": min(_chance(s), 1.0),
            }
        )
    if "Lifesteal" in tagset:
        s = _sentence_for(text, r"damage dealt|absorb|proportional to damage", r"health") or text
        m = re.search(r"(\d+)% of (?:the )?damage", s.lower())
        effects.append(
            {
                "type": "lifesteal",
                "ratio": int(m.group(1)) / 100 if m else 0.2,
                "estimated": m is None,
            }
        )
    if "Damage Reduction" in tagset:
        s = _sentence_for(text, r"damage suffered|damage reduction", r"decreas|grant") or text
        m = re.search(r"(?:by |grants )(\d+)%", s.lower())
        effects.append({"type": "damage_reduction", "value": int(m.group(1)) / 100 if m else 0.2})
    if "Damage Taken Cap" in tagset:
        m = re.search(r"exceed (\d+)% of max health", text.lower())
        effects.append({"type": "damage_cap", "value": int(m.group(1)) / 100 if m else 0.5})
    if "Immune to Debuffs Which Prevent Movement" in tagset:
        effects.append({"type": "static_immune", "effects": ["stun", "sleep"]})
    if "Damage Share" in tagset:
        m = re.search(r"(\d+)% damage sharing", text.lower())
        if m:
            effects.append({"type": "static_share", "value": int(m.group(1)) / 100})
    if "Injury" in tagset:
        m = re.search(r"up to (\d+)% injur", text.lower())
        effects.append(
            {"type": "injury", "max": int(m.group(1)) / 100 if m else 0.15, "estimated": m is None}
        )
    if "Detonate" in tagset:
        s = _sentence_for(text, r"detonat", r"detonat") or text
        what = [d for d in ("burn", "bleed", "bomb") if d in s.lower()] or ["burn", "bleed"]
        effects.append({"type": "detonate", "what": what})
    if "Extinction" in tagset:
        effects.append({"type": "extinction"})
    if {"Fixed Damage", "Additional Damage"} & tagset:
        m = re.search(r"(\d[\d,]*) (?:fixed|additional) damage", text.lower())
        if m:
            s = _sentence_for(text, re.escape(m.group(0)), r"damage") or text
            low = s.lower()
            effects.append(
                {
                    "type": "fixed",
                    "amount": int(m.group(1).replace(",", "")),
                    "per_debuff": "for each debuff" in low,
                    "on_crit": "critical hit" in low,
                }
            )
    if "Debuff Dispel (Cleanse)" in tagset:
        s = _sentence_for(text, r"remov|dispel", r"debuff") or text
        effects.append(
            {"type": "cleanse", "target": _target(s, "allies"), "all": "all debuff" in s.lower()}
        )
    return effects


# déclencheurs des passifs, du plus spécifique au plus général (premier trouvé retenu)
TRIGGERS = (
    ("counter", r"chance to counterattack|attacked, counterattacks?\b"),
    ("revive", r"upon receiving lethal damage, (revives?|regenerates?)"),
    ("lethal", r"(upon|when the caster) receiv\w* lethal damage"),
    ("battle_start", r"at the start of (the first )?battle|starts the first battle"),
    ("ally_attacked", r"\b(when|after) (an|any) ally (except for the caster )?(is|suffers an?) "),
    ("enemy_skill", r"\b(when|after) (an|the) enemy uses an?( non-attack)? skill"),
    ("enemy_turn_start", r"at the start of an enemy's turn"),
    ("enemy_turn_end", r"at the end of an enemy's turn|when an enemy's turn ends"),
    ("ally_turn_end", r"at the end of (an|every \d+) ally'?s? turns?"),
    ("any_turn_end", r"at the end of (someone's|a) turn"),
    ("death", r"when (the enemy is defeated|somebody dies|an? (ally|enemy) dies)"),
    ("crit", r"after delivering a critical hit|when (the caster )?(makes|lands) a critical hit"),
    ("turn_start", r"at the (start|beginning) of (the |each |the caster's )?turn"),
    ("turn_end", r"at the end of (the |each |the caster's )?turn"),
    (
        "attacked",
        r"\b(when|after|at the moment) (the caster is )?(being )?attacked\b"
        r"|\bafter being attacked\b|\bwhen suffering an attack\b",
    ),
    ("after_attack", r"\bafter (attacking|using a (basic )?skill)\b|\ba successful attack\b"),
)
RESOURCES = {"focus": (r"focus", 5, 1), "spirit": (r"fighting spirit", 100, 10)}


def _event(text: str, passive: bool) -> tuple[str, str] | None:
    """Premier déclencheur reconnu dans `text` : (événement, phrase)."""
    low = text.lower()
    for event, pattern in TRIGGERS:
        if not re.search(pattern, low) or (event != "counter" and not passive):
            continue
        sentence = next((s for s in _sentences(text) if re.search(pattern, s.lower())), text)
        return event, sentence
    return None


def _condition(text: str) -> dict[str, Any] | None:
    low = text.lower()
    m = re.search(
        r"when (?:the caster's )?health (?:of the caster )?is (\d+)% or (less|lower)", low
    )
    if m:
        return {"kind": "hp_below", "value": int(m.group(1)) / 100}
    m = re.search(r"when (?:the )?target's health is (\d+)% or (less|lower)", low)
    if m:
        return {"kind": "target_hp_below", "value": int(m.group(1)) / 100}
    if re.search(r"(caster|ally) is at max health|health is full", low):
        return {"kind": "full_hp"}
    if re.search(r"caster does not have a debuff|caster is free of debuffs", low):
        return {"kind": "no_debuff"}
    if re.search(r"caster (has a debuff|is debuffed)", low):
        return {"kind": "has_debuff"}
    if "non-attack skill" in low:
        return {"kind": "non_attack"}
    return None


def _resource(text: str, passive: bool) -> dict[str, Any] | None:
    """Jauge (Concentration, Esprit combatif) qui active le passif une fois pleine."""
    low = text.lower()
    for kind, (word, full, default_gain) in RESOURCES.items():
        need = re.search(
            rf"when (?:the caster's )?(?:stacked )?{word} is (full|(\d+) or higher|(\d+)\b)", low
        )
        if not need:
            continue
        value = need.group(2) or need.group(3)
        res: dict[str, Any] = {"kind": kind, "need": int(value) if value else full}
        start = re.search(
            rf"(?:starts the first battle with|gains) (\d+) {word}[^.]*first battle"
            rf"|first battle, (?:gains|fully recovers) (\d+)? ?{word}",
            low,
        )
        if start:
            res["start"] = int(start.group(1) or start.group(2) or res["need"])
        gain = next(
            (
                (s, g)
                for s in _sentences(text)
                if (g := re.search(rf"gains? (\d+) {word}", s.lower()))
                and "first battle" not in s.lower()
            ),
            None,
        )
        found = _event(gain[0], passive) if gain else None
        res["gain"] = int(gain[1].group(1)) if gain else default_gain
        # sans gain explicite : Concentration à chaque tour, Esprit quand on est attaqué (estimé)
        res["on"] = found[0] if found else ("turn_end" if kind == "focus" else "attacked")
        res["estimated"] = gain is None
        return res
    return None


def parse_trigger(text: str, *, passive: bool) -> dict[str, Any] | None:
    """Déclencheur d'une compétence passive ou de contre-attaque (`None` si non reconnu).

    `event` : counter (contre-attaque avec cette compétence si elle inflige des dégâts, sinon
    S1), revive, lethal (dégâts mortels), battle_start, turn_start, turn_end (tour du porteur),
    attacked, after_attack, ally_attacked, enemy_skill, enemy_turn_start, enemy_turn_end,
    ally_turn_end, any_turn_end, death, crit, resource (jauge pleine). `chance` : « has a 30%
    chance » ; `every` : « once every 3 turns » (99 = une fois par combat) ; `health` : PV
    rendus à la résurrection ; `condition` : seuil de PV, débuff... ; `resource` : jauge
    (Concentration ou Esprit combatif) remplie par l'événement `on`.
    """
    resource = _resource(text, passive) if passive else None
    found = _event(text, passive)
    if found is None and resource is None:
        return None
    event, sentence = found if found else ("resource", text)
    low = text.lower()
    trigger: dict[str, Any] = {"event": event, "chance": _chance(sentence)}
    every = re.search(r"once every (\d+) t", low)
    if every:
        trigger["every"] = int(every.group(1))
    elif re.search(r"once per battle|only be activated once\b", low) or event == "revive":
        trigger["every"] = 99
    if event == "revive":
        hp = re.search(r"(?:revives?|regenerates?) (?:with|to) (\d+)% (?:of )?(?:max )?health", low)
        trigger["health"] = int(hp.group(1)) / 100 if hp else 0.5
    whole = _condition(text)
    condition = _condition(sentence) if found else whole
    if condition is None and whole is not None and whole["kind"].endswith("hp_below"):
        condition = whole  # seuil de PV énoncé dans une autre phrase
    if condition is not None:
        trigger["condition"] = condition
    if resource is not None and event not in ("counter", "revive", "lethal"):
        trigger["event"] = "resource"
        trigger["resource"] = resource
        trigger["chance"] = 1.0
    return trigger
