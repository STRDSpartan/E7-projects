"""Chargement de la configuration (TOML par défaut + fichier utilisateur + variables d'env)."""

from __future__ import annotations

import os
import tomllib
from functools import cache
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir, user_data_dir

_REPO_CFG = Path(__file__).resolve().parents[2] / "config"
_PKG_CFG = Path(__file__).resolve().parent / "_config"


def config_dir() -> Path:
    return _REPO_CFG if _REPO_CFG.is_dir() else _PKG_CFG


def data_dir() -> Path:
    path = Path(os.environ.get("E7_DATA_DIR") or user_data_dir("e7showcase"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        out[k] = (
            _deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
        )
    return out


@cache
def settings() -> dict[str, Any]:
    with (config_dir() / "default.toml").open("rb") as f:
        cfg = tomllib.load(f)
    user_file = Path(user_config_dir("e7showcase")) / "config.toml"
    if user_file.is_file():
        with user_file.open("rb") as f:
            cfg = _deep_merge(cfg, tomllib.load(f))
    if lang := os.environ.get("E7_GAME_LANG"):
        cfg["game"]["lang"] = lang
    cfg["discord"]["webhook_url"] = os.environ.get("E7_DISCORD_WEBHOOK_URL", "")
    cfg["discord"]["bot_token"] = os.environ.get("E7_DISCORD_BOT_TOKEN", "")
    return cfg


def regions(profile: str | None = None) -> dict[str, dict[str, list[float]]]:
    name = profile or settings()["game"]["region_profile"]
    with (config_dir() / "regions" / f"{name}.toml").open("rb") as f:
        return tomllib.load(f)
