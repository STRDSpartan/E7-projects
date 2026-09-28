import pytest

from e7showcase.parsers.common import clean, parse_classes, parse_int, parse_level, parse_number


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2,835", (2835, False)),
        ("205,138", (205138, False)),
        ("94.0%", (94.0, True)),
        ("290.0%", (290.0, True)),
        ("%6", (9, True)),  # texte lu retourné par l'OCR
        (" 20% ", (20, True)),
        ("+15", (15, False)),
        ("　92", (92, False)),
        ("2O%", (20, True)),
    ],
)
def test_parse_number(text: str, expected: tuple[float, bool]) -> None:
    assert parse_number(text) == expected


def test_parse_number_garbage() -> None:
    assert parse_number("abc") is None


def test_clean_reverses_rotated_percent() -> None:
    assert clean("%6") == "9%"
    assert clean("%81") == "18%"


def test_parse_int_bounds() -> None:
    assert parse_int("00.", 50, 100) is None
    assert parse_int("88", 50, 100) == 88


@pytest.mark.parametrize(
    ("text", "level"), [("Lv.Max/60", 60), ("Lv. Max / 60", 60), ("Lv.55/60", 55)]
)
def test_parse_level(text: str, level: int) -> None:
    assert parse_level(text) == level


def test_parse_classes_fr() -> None:
    assert parse_classes("Glace Assassin QLion") == {"element": "ice", "role": "thief"}
    assert parse_classes("Glace Tireur Capricorne") == {
        "element": "ice",
        "role": "ranger",
        "zodiac": "capricorn",
    }
