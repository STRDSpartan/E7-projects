"""Localisation de la fenêtre du client PC Epic Seven (Windows)."""

from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class WindowRect:
    left: int
    top: int
    width: int
    height: int

    @property
    def aspect(self) -> float:
        return self.width / self.height


class WindowNotFoundError(RuntimeError):
    pass


def find_game_window(title: str = "Epic Seven") -> WindowRect:
    """Retourne la zone cliente (sans bordures) de la fenêtre du jeu."""
    if sys.platform != "win32":
        raise WindowNotFoundError(
            "La capture du client PC n'est supportée que sous Windows. "
            "Utilisez `e7showcase scan --from-dir` avec des captures existantes."
        )
    import win32gui

    hwnd = win32gui.FindWindow(None, title)
    if not hwnd:
        matches: list[int] = []
        win32gui.EnumWindows(
            lambda h, _: (
                matches.append(h) if title.lower() in win32gui.GetWindowText(h).lower() else None
            ),
            None,
        )
        if not matches:
            raise WindowNotFoundError(f"Fenêtre « {title} » introuvable. Le jeu est-il lancé ?")
        hwnd = matches[0]
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    left, top = win32gui.ClientToScreen(hwnd, (left, top))
    right, bottom = win32gui.ClientToScreen(hwnd, (right, bottom))
    return WindowRect(left, top, right - left, bottom - top)


def focus_game_window(title: str = "Epic Seven") -> None:
    if sys.platform != "win32":
        return
    import win32gui

    if hwnd := win32gui.FindWindow(None, title):
        win32gui.SetForegroundWindow(hwnd)
