"""Run the router eval against LIVE in-boundary backends + judge (backend-real).

    ./.venv/bin/python -m tests.benchmarks            # automatic routing, rules brain
    PRECEPTA_BRAIN=classifier ./.venv/bin/python -m tests.benchmarks --route cheapest

Needs Ollama running (the judge + at least one backend). Writes the full report
to tests/benchmarks/reports/latest.json and prints the summary. This is the
Rule-12 evidence run; the deterministic unit tests live in
tests/test_eval_harness.py.
"""
from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
from pathlib import Path

from .harness import run_eval
from .judge import OllamaJudge


def main() -> None:
    ap = argparse.ArgumentParser(prog="tests.benchmarks")
    ap.add_argument("--route", default="automatic",
                    help="route mode: automatic | cheapest | fastest | best-quality")
    args = ap.parse_args()

    report = asyncio.run(run_eval(OllamaJudge(), route_mode=args.route))
    print(report.summary())

    out = Path(__file__).with_name("reports") / "latest.json"
    out.parent.mkdir(exist_ok=True)
    with out.open("w") as fh:
        json.dump(dataclasses.asdict(report), fh, indent=2)
    print(f"\nreport → {out}")


if __name__ == "__main__":
    main()
