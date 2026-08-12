"""Phase 15 · Group 0 — contract foundations: manage-scope keys, require_manage
guard, the in-boundary catalog, and the error envelope."""
from __future__ import annotations

from app.adapters.identity.keys import issue_key, get_api_identity, revoke_key
from app.api.deps import require_manage, require_auth
from app.api.errors import error_json, forbidden
from app.ports import Principal
from app import catalog


# ── manage-scope keys ───────────────────────────────────────────────────────
def test_manage_key_rw_authenticates_as_admin_scope():
    kid, token = issue_key("mgr-rw", scope="manage", manage_write=True, expires_in_days=None)
    try:
        p = get_api_identity().authenticate(token)
        assert p is not None
        assert p.scope == "manage:rw"
        assert p.role == "admin"           # rw manage → admin-tier can()
    finally:
        revoke_key(kid)


def test_manage_key_ro_is_read_only_scope():
    kid, token = issue_key("mgr-ro", scope="manage", manage_write=False, expires_in_days=None)
    try:
        p = get_api_identity().authenticate(token)
        assert p.scope == "manage:ro"
        assert p.role == "auditor"
    finally:
        revoke_key(kid)


def test_inference_key_has_inference_scope():
    kid, token = issue_key("app-key", expires_in_days=None)   # default scope
    try:
        p = get_api_identity().authenticate(token)
        assert p.scope == "inference"
        assert p.role == "user"
    finally:
        revoke_key(kid)


# ── require_manage guard ────────────────────────────────────────────────────
def test_require_manage_matrix():
    admin = Principal("owner", "admin", scope="inference")
    ro = Principal("k", "auditor", scope="manage:ro")
    rw = Principal("k", "admin", scope="manage:rw")
    inf = Principal("app", "user", scope="inference")

    assert require_manage(admin, write=True) is None
    assert require_manage(rw, write=True) is None
    assert require_manage(ro, write=False) is None          # read allowed
    assert require_manage(ro, write=True) is not None       # write blocked (read-only key)
    assert require_manage(inf, write=False) is not None     # inference key can't manage
    assert require_manage(None, write=False) is not None    # unauth


def test_require_auth_rejects_anonymous():
    assert require_auth(Principal("anonymous", "user")) is not None
    assert require_auth(Principal("real@x", "user")) is None


# ── catalog ─────────────────────────────────────────────────────────────────
def test_catalog_lists_and_filters():
    all_models = catalog.list_models()
    assert len(all_models) >= 5
    chats = catalog.list_models(mode="chat")
    assert all(m["mode"] == "chat" for m in chats)
    hf = catalog.list_models(provider="hf")
    assert all(m["provider"] == "hf" for m in hf)
    assert catalog.get_provider("hf") is not None
    assert catalog.get_provider("nope") is None


def test_catalog_lookup_hit_and_miss():
    hit = catalog.catalog_lookup("ollama", "llama3.2:3b")
    assert hit and hit["max_input_tokens"] == 131072
    # basename match across a slug-prefixed model id
    hit2 = catalog.catalog_lookup("hf", "meta-llama/Llama-3.1-8B-Instruct")
    assert hit2 and hit2["capabilities"]["function_calling"] is True
    assert catalog.catalog_lookup("ollama", "totally-unknown-model") is None


# ── error envelope ──────────────────────────────────────────────────────────
def test_error_envelope_shape():
    import json
    r = error_json(403, "forbidden", "nope", code="x")
    body = json.loads(bytes(r.body))
    assert body == {"error": {"message": "nope", "type": "forbidden", "code": "x"}}
    assert forbidden("y").status_code == 403
