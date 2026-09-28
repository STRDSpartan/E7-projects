"""Déclencheurs de capture.

- ManualNavigator  : l'utilisateur navigue lui-même dans le jeu et appuie sur une touche
                     pour chaque capture. Aucune entrée n'est envoyée au jeu.
- AssistedNavigator: clique sur les emplacements d'équipement et la flèche « suivant ».
                     Désactivé par défaut — lire docs/COMPLIANCE.md avant de l'activer.
"""

from __future__ import annotations

import time
from typing import Protocol

from e7showcase.capture.window import WindowRect
from e7showcase.vision.regions import center


class Navigator(Protocol):
    def wait_for_capture(self, prompt: str) -> bool:
        """Bloque jusqu'à ce qu'une capture doive être prise. False = arrêt demandé."""
        ...

    def open_slot(self, rect: WindowRect, region: list[float]) -> None: ...

    def next_hero(self, rect: WindowRect, region: list[float]) -> None: ...


class ManualNavigator:
    def __init__(self, hotkey: str = "f9", stop_hotkey: str = "f10", skip_hotkey: str = "f8"):
        self.hotkey, self.stop_hotkey, self.skip_hotkey = hotkey, stop_hotkey, skip_hotkey
        self.last_skipped = False

    def wait_for_capture(self, prompt: str) -> bool:
        import keyboard

        print(
            f"{prompt}  [{self.hotkey.upper()}=capturer · {self.skip_hotkey.upper()}=passer · "
            f"{self.stop_hotkey.upper()}=terminer]"
        )
        key = keyboard.read_hotkey(suppress=False).lower()
        while key not in {self.hotkey, self.stop_hotkey, self.skip_hotkey}:
            key = keyboard.read_hotkey(suppress=False).lower()
        self.last_skipped = key == self.skip_hotkey
        return bool(key != self.stop_hotkey)

    def open_slot(self, rect: WindowRect, region: list[float]) -> None:
        return None  # l'utilisateur ouvre lui-même l'infobulle

    def next_hero(self, rect: WindowRect, region: list[float]) -> None:
        return None


class AssistedNavigator(ManualNavigator):
    def __init__(self, delay_ms: int = 900, **kwargs: str):
        super().__init__(**kwargs)
        self.delay = delay_ms / 1000

    def _click(self, rect: WindowRect, region: list[float]) -> None:
        import win32api
        import win32con

        x, y = center(region, (rect.width, rect.height))
        win32api.SetCursorPos((rect.left + x, rect.top + y))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
        time.sleep(self.delay)

    def wait_for_capture(self, prompt: str) -> bool:
        self.last_skipped = False
        return True

    def open_slot(self, rect: WindowRect, region: list[float]) -> None:
        self._click(rect, region)

    def next_hero(self, rect: WindowRect, region: list[float]) -> None:
        self._click(rect, region)
