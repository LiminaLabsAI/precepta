"""In-memory router state — latency observations + circuit breakers.

Kept in-process for V1; `circuit_breaker_state` in the DB can back this later.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

# backend name -> last observed latency (ms), for `fastest` routing
_latency: dict[str, float] = {}


def record_latency(backend: str, ms: float) -> None:
    _latency[backend] = ms


def latency(backend: str) -> float:
    return _latency.get(backend, float("inf"))


@dataclass
class Breaker:
    fail_threshold: int = 3
    cooldown_s: float = 30.0
    consecutive: int = 0
    open_until: float = 0.0

    def is_open(self) -> bool:
        return time.monotonic() < self.open_until

    def record_success(self) -> None:
        self.consecutive = 0
        self.open_until = 0.0

    def record_failure(self) -> None:
        self.consecutive += 1
        if self.consecutive >= self.fail_threshold:
            self.open_until = time.monotonic() + self.cooldown_s


_breakers: dict[str, Breaker] = {}


def breaker(backend: str) -> Breaker:
    return _breakers.setdefault(backend, Breaker())


def reset_all() -> None:  # test helper
    _latency.clear()
    _breakers.clear()
