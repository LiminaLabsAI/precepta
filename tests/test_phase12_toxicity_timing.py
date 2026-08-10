"""Phase 12 — Group 3 · toxicity detector + enforcement-timing tests."""
from __future__ import annotations

import asyncio

import pytest

from app.governance import toxicity as tox
from app.router import timing


# ── toxicity ─────────────────────────────────────────────────────────────────

def test_detects_abusive_phrase():
    is_tox, matched = tox.scan_toxicity("Honestly you should just kill yourself")
    assert is_tox is True and matched == "kill yourself"


def test_case_insensitive():
    assert tox.scan_toxicity("GO TO HELL")[0] is True


def test_clean_text_is_not_toxic():
    for s in ("How do I cache a response?", "The class started at noon",
              "kill the background process", "assistant, please summarise this"):
        assert tox.scan_toxicity(s)[0] is False, s


def test_empty_and_none_are_safe():
    assert tox.scan_toxicity("") == (False, "")
    assert tox.scan_toxicity(None) == (False, "")


def test_runtime_extension():
    tox.add_terms(["get lost loser"])
    try:
        assert tox.scan_toxicity("just get lost loser")[0] is True
    finally:
        tox._extra.discard("get lost loser")


def test_word_boundary_avoids_false_positive_substring():
    # 'die' is not a default term; 'you should die' is — a substring must not trip
    assert tox.scan_toxicity("the diesel engine died")[0] is False


# ── enforcement timing ───────────────────────────────────────────────────────

def test_default_stages():
    assert timing.stage_of("firewall") == timing.PRE
    assert timing.stage_of("inference") == timing.DURING
    assert timing.stage_of("output") == timing.POST
    assert timing.stage_of("toxicity") == timing.POST


def test_unknown_check_has_no_stage():
    assert timing.stage_of("nonexistent") is None


def test_checks_at_groups_by_stage():
    pre = timing.checks_at(timing.PRE)
    assert "firewall" in pre and "policy" in pre and "routing" in pre
    assert "output" not in pre


def test_stages_are_ordered_pre_during_post():
    assert timing.stages() == (timing.PRE, timing.DURING, timing.POST)


def test_set_stage_updates_and_validates():
    original = timing.stage_of("toxicity")
    try:
        timing.set_stage("toxicity", timing.DURING)
        assert timing.stage_of("toxicity") == timing.DURING
    finally:
        timing.set_stage("toxicity", original)
    with pytest.raises(ValueError):
        timing.set_stage("firewall", "whenever")


def test_as_map_is_a_copy():
    m = timing.as_map()
    m["firewall"] = "mutated"
    assert timing.stage_of("firewall") == timing.PRE   # internal map untouched


# ── toxicity wired into the governed pipeline (opt-in) ───────────────────────

def _run_pipeline(response_text: str, filter_on: bool):
    from app.gateway import pipeline
    from app.ports import Principal
    from app import org

    async def fake_infer(msgs, route_ctx=None):
        return ({"choices": [{"message": {"role": "assistant", "content": response_text}}],
                 "usage": {"prompt_tokens": 3, "completion_tokens": 2}},
                {"backend_used": "ollama", "in_boundary": True, "model": "m",
                 "reason": "test"})

    org.update({"toxicity_filter": "true" if filter_on else "false"})
    try:
        return asyncio.run(pipeline.governed_chat(
            [{"role": "user", "content": "hi"}], {"temperature": 0.5},
            Principal("u@x", "user"), False, fake_infer))
    finally:
        org.update({"toxicity_filter": "false"})


def test_toxic_output_blocked_when_filter_on():
    status, payload = _run_pipeline("Honestly, you should kill yourself.", filter_on=True)
    assert status == 403
    assert "toxic" in payload["error"]["message"].lower()


def test_toxic_output_passes_when_filter_off():
    status, _ = _run_pipeline("you should kill yourself", filter_on=False)
    assert status == 200          # safe-by-default: off unless enabled


def test_clean_output_passes_when_filter_on():
    status, payload = _run_pipeline("Here is a helpful, friendly answer.", filter_on=True)
    assert status == 200
