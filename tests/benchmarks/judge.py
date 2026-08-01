"""In-boundary answer judge for the router eval (FEAT-006).

Sovereignty (non-negotiable): the judge is a helper model, so it must run
**inside the boundary** — never an external service. V1 uses the local Ollama
model at temperature 0 with a frozen prompt, so the score is reproducible.

LOCKED per Rule 11. The judge model, prompt, and parsing below are part of the
`v1` evaluator — do not edit to make a run look better; bump to `judge_v2` and
re-baseline instead.

Honest limitation: a small local judge (3B) is a weak grader. The harness is
correct and the score is real, but it only becomes discriminating with a
stronger in-boundary judge. That is a model swap behind this same interface.
"""
from __future__ import annotations

import re

import httpx

JUDGE_VERSION = "v1"
JUDGE_MODEL = "llama3.2:3b"          # in-boundary, local Ollama
_JUDGE_TEMP = 0.0

_SYSTEM = (
    "You are a strict grader. You are given a QUESTION, a reference answer, a "
    "grading rubric, and a candidate answer. Score how well the CANDIDATE answer "
    "satisfies the rubric and matches the reference, from 0 to 100 (100 = fully "
    "correct and complete, 0 = wrong or empty). Judge correctness and completeness "
    "only — ignore style, length, and extra caveats. Reply with ONLY the integer "
    "score, nothing else."
)


def _prompt(question: str, answer: str, reference: str, rubric: str) -> str:
    return (f"QUESTION:\n{question}\n\nREFERENCE ANSWER:\n{reference}\n\n"
            f"RUBRIC:\n{rubric}\n\nCANDIDATE ANSWER:\n{answer}\n\n"
            "Score (0-100), integer only:")


def parse_score(text: str) -> float:
    """Extract the judge's 0-100 integer and normalize to 0..1 (clamped)."""
    m = re.search(r"-?\d+(?:\.\d+)?", text or "")
    if not m:
        return 0.0
    val = float(m.group())
    return max(0.0, min(100.0, val)) / 100.0


class OllamaJudge:
    """LLM judge over the local (in-boundary) Ollama OpenAI-compatible endpoint."""

    name = f"ollama-judge/{JUDGE_MODEL}@{JUDGE_VERSION}"

    def __init__(self, port: int = 11434, model: str = JUDGE_MODEL,
                 timeout: float = 60.0) -> None:
        self._url = f"http://127.0.0.1:{port}/v1/chat/completions"
        self._model = model
        self._timeout = timeout

    def score(self, question: str, answer: str, reference: str, rubric: str) -> float:
        resp = httpx.post(self._url, timeout=self._timeout, json={
            "model": self._model,
            "temperature": _JUDGE_TEMP,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": _prompt(question, answer, reference, rubric)},
            ],
        })
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return parse_score(content)
