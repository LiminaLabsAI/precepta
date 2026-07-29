"""Reasoning techniques (ReasoningPort).

Each technique receives an injected async `call_model(messages) -> (result, backend)`
that routes every inner call back through the governed pipeline (Phase 3+), so
multi-call techniques stay inside the sovereign loop and fully audited.

`run` returns (openai_result_dict, backend_name).
"""
from __future__ import annotations

from collections import Counter

from ...ports import PolicyCheckContext


def _content(result: dict) -> str:
    try:
        return result["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        return ""


class Passthrough:
    name = "passthrough"

    def estimate_calls(self, ctx: PolicyCheckContext | None = None) -> int:
        return 1

    async def run(self, messages, ctx, call_model):
        return await call_model(messages)


class BestOfN:
    name = "best_of_n"

    def __init__(self, n: int = 3) -> None:
        self.n = n

    def estimate_calls(self, ctx: PolicyCheckContext | None = None) -> int:
        return self.n

    async def run(self, messages, ctx, call_model):
        results = [await call_model(messages) for _ in range(self.n)]
        # No external scorer yet → proxy "best" = most complete (longest) answer.
        return max(results, key=lambda rb: len(_content(rb[0])))


class SelfConsistency:
    name = "self_consistency"

    def __init__(self, n: int = 3) -> None:
        self.n = n

    def estimate_calls(self, ctx: PolicyCheckContext | None = None) -> int:
        return self.n

    async def run(self, messages, ctx, call_model):
        results = [await call_model(messages) for _ in range(self.n)]
        # Majority vote on normalized content; tie → first occurrence.
        counts = Counter(_content(r).strip().lower() for r, _ in results)
        winner, _ = counts.most_common(1)[0]
        for r, b in results:
            if _content(r).strip().lower() == winner:
                return r, b
        return results[0]


def get_reasoner(name: str):
    if name == "best_of_n":
        return BestOfN()
    if name == "self_consistency":
        return SelfConsistency()
    return Passthrough()
