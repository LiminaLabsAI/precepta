"""Phase 12 — BUG-001 regression guard: same-provider-type backends coexist.

BUG-001 was: backends keyed by provider *type* meant a 2nd HF (or vLLM) model
overwrote the first. The fix keys by a unique name-slug id (the caller-supplied
`provider`). These tests lock that behaviour so it can't regress: two backends
of the same type coexist; re-registering the *same* id updates in place.

The tests create clearly-named fixtures and clean them up in `finally`.
"""
from __future__ import annotations

from app.adapters.model import store


_A = "__test_bug001_hf_a"
_B = "__test_bug001_hf_b"


def _cleanup():
    for p in (_A, _B):
        try:
            store.delete_backend(p)
        except Exception:
            pass


def test_two_same_type_backends_coexist():
    _cleanup()
    try:
        store.save_backend(_A, "http://10.0.0.1/v1", None, "hf/model-a", True, 3)
        store.save_backend(_B, "http://10.0.0.2/v1", None, "hf/model-b", True, 3)
        rows = {r["provider"]: r for r in store.load_backends()}
        assert _A in rows and _B in rows, "both same-type backends must coexist"
        assert rows[_A]["model"] == "hf/model-a"
        assert rows[_B]["model"] == "hf/model-b"
        assert rows[_A]["base_url"] != rows[_B]["base_url"]
    finally:
        _cleanup()


def test_same_id_updates_in_place_no_duplicate():
    _cleanup()
    try:
        store.save_backend(_A, "http://old/v1", None, "hf/old", True, 1)
        store.save_backend(_A, "http://new/v1", None, "hf/new", False, 3)
        rows = [r for r in store.load_backends() if r["provider"] == _A]
        assert len(rows) == 1, "same id must update, not duplicate"
        assert rows[0]["base_url"] == "http://new/v1"
        assert rows[0]["model"] == "hf/new"
        assert rows[0]["in_boundary"] == 0
        assert rows[0]["tier"] == 3
    finally:
        _cleanup()


def test_registry_identity_is_the_slug_not_the_type():
    # documents the keying model: a dict keyed by the unique provider id — two
    # distinct ids coexist; the same id overwrites (which is the desired update).
    reg: dict[str, str] = {}
    reg["hf-gemma"] = "backend-1"
    reg["hf-deepseek"] = "backend-2"
    assert len(reg) == 2 and reg["hf-gemma"] != reg["hf-deepseek"]
    reg["hf-gemma"] = "backend-1b"
    assert len(reg) == 2 and reg["hf-gemma"] == "backend-1b"
