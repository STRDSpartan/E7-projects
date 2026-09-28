from e7showcase.parsers.hero_parser import match_hero_name, parse_hero_stats


def test_parse_hero_stats_panel() -> None:
    lines = [
        "Attaque 1 203",
        "PV 18 540",
        "Défense 1 101",
        "Vitesse 251",
        "Chances de critique 15%",
        "Dégâts critiques 150%",
        "Efficacité 20%",
        "Résistance aux effets 120%",
    ]
    stats = parse_hero_stats(
        [line.replace(" ", "", 1) if line[-1].isdigit() else line for line in lines]
    )
    assert stats.spd == 251
    assert stats.crit_chance == 15 and stats.effect_res == 120


def test_match_hero_name_with_ocr_noise() -> None:
    assert match_hero_name("Cecilia dechue") == "Cécilia déchue"
    assert match_hero_name("Cecilia") == "Cécilia"
    assert match_hero_name("Kise") == "Kise"  # pas « Juge Kise »
    assert match_hero_name("Coli tactiqe") == "Coli tactique"
    assert match_hero_name("Ravi Apocalypes") == "Ravi Apocalypse"


def test_unknown_name_returns_none() -> None:
    assert match_hero_name("zzzzzz") is None
