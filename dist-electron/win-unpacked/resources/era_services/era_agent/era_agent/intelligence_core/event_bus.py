"""EventBus for ERA Intelligence Core event-driven architecture."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, List


class EventBus:
    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable[[Dict[str, Any]], Any]]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, event_type: str, callback: Callable[[Dict[str, Any]], Any]) -> None:
        async with self._lock:
            self._subscribers.setdefault(event_type, []).append(callback)

    async def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        callbacks = list(self._subscribers.get(event_type, []))
        callbacks += list(self._subscribers.get("*", []))
        for cb in callbacks:
            try:
                result = cb(payload)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                # Event subscribers must never crash the main event loop.
                pass
