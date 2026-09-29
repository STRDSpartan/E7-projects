"""Diffusion temps réel des messages de chat (WebSocket).

Implémentation en mémoire : suffisante pour un seul processus serveur. Pour plusieurs
processus ou machines, remplacer par un bus Redis pub/sub (même interface).
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class ChannelHub:
    def __init__(self) -> None:
        self._sockets: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def join(self, channel_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._sockets[channel_id].add(ws)

    async def leave(self, channel_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._sockets[channel_id].discard(ws)

    async def broadcast(self, channel_id: int, payload: dict[str, Any]) -> None:
        async with self._lock:
            targets = list(self._sockets.get(channel_id, ()))
        for ws in targets:
            try:
                await ws.send_json(payload)
            except Exception:  # connexion fermée entre-temps
                await self.leave(channel_id, ws)
