"""Approved-egress allowlist: host normalisation, subdomain matching, and the
Sovereign-Mode enforcement that permits an approved host while blocking others.
"""
from __future__ import annotations

import pytest

from app.sovereign import egress as eg
from app.sovereign import enforce_backend


@pytest.fixture(autouse=True)
def _clean():
    eg.ensure_table()
    for h in list(eg.list_hosts()):
        eg.remove_host(h["host"])
    yield
    for h in list(eg.list_hosts()):
        eg.remove_host(h["host"])


class _BE:
    def __init__(self, name, base_url, in_boundary):
        self.name = name
        self.base_url = base_url
        self.in_boundary = in_boundary


def test_seed_oidc_egress_google(monkeypatch):
    # No-op unless Google OIDC is fully configured.
    monkeypatch.delenv("OIDC_ISSUER", raising=False)
    eg.seed_oidc_egress()
    assert eg.list_hosts() == []
    # issuer set but no client id/secret → still no-op (mirrors sso.is_configured)
    monkeypatch.setenv("OIDC_ISSUER", "https://accounts.google.com")
    eg.seed_oidc_egress()
    assert eg.list_hosts() == []
    # fully configured → the four Google OIDC hosts are approved (added_by system:oidc)
    monkeypatch.setenv("OIDC_CLIENT_ID", "x.apps.googleusercontent.com")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "secret")
    eg.seed_oidc_egress()
    hosts = {h["host"]: h for h in eg.list_hosts()}
    for h in ("accounts.google.com", "oauth2.googleapis.com",
              "openidconnect.googleapis.com", "www.googleapis.com"):
        assert h in hosts and hosts[h]["added_by"] == "system:oidc"
    # so the login flow (and any subdomain) is now allowed to egress
    assert eg.is_approved("https://oauth2.googleapis.com/token")
    # idempotent — re-seeding doesn't duplicate
    eg.seed_oidc_egress()
    assert len([h for h in eg.list_hosts() if h["host"] == "accounts.google.com"]) == 1


def test_seed_oidc_egress_ignores_non_google(monkeypatch):
    # A non-Google issuer (e.g. Okta) is not auto-seeded by this Google-specific hook.
    monkeypatch.setenv("OIDC_ISSUER", "https://acme.okta.com")
    monkeypatch.setenv("OIDC_CLIENT_ID", "x")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "y")
    eg.seed_oidc_egress()
    assert eg.list_hosts() == []


def test_host_of_variants():
    assert eg.host_of("https://api.huggingface.co/v1") == "api.huggingface.co"
    assert eg.host_of("huggingface.co:443") == "huggingface.co"
    assert eg.host_of("HuggingFace.CO") == "huggingface.co"
    assert eg.host_of("") == ""


def test_subdomain_match_but_not_unrelated():
    eg.add_host("huggingface.co", added_by="t")
    assert eg.is_approved("https://api.huggingface.co/v1") is True
    assert eg.is_approved("huggingface.co") is True
    assert eg.is_approved("https://openai.com/v1") is False
    # a host that merely ends in the string but isn't a subdomain must NOT match
    assert eg.is_approved("https://evilhuggingface.co") is False


def test_add_is_idempotent_and_removable():
    eg.add_host("neysa.ai", added_by="t")
    eg.add_host("neysa.ai", added_by="t", note="again")
    assert [h["host"] for h in eg.list_hosts()] == ["neysa.ai"]
    assert eg.remove_host("neysa.ai") is True
    assert eg.list_hosts() == []


def test_enforce_blocks_out_of_boundary_without_approval(monkeypatch):
    monkeypatch.setattr("app.controls.sovereign_enabled", lambda: True)
    be = _BE("hf", "https://api.huggingface.co/v1", in_boundary=False)
    reason = enforce_backend(be)
    assert reason is not None
    assert "api.huggingface.co" in reason
    assert "Egress" in reason


def test_enforce_allows_out_of_boundary_when_host_approved(monkeypatch):
    monkeypatch.setattr("app.controls.sovereign_enabled", lambda: True)
    eg.add_host("huggingface.co", added_by="owner")
    be = _BE("hf", "https://api.huggingface.co/v1", in_boundary=False)
    assert enforce_backend(be) is None            # approved → permitted


def test_enforce_ignores_allowlist_for_in_boundary(monkeypatch):
    monkeypatch.setattr("app.controls.sovereign_enabled", lambda: True)
    be = _BE("ollama", "http://ollama:11434/v1", in_boundary=True)
    assert enforce_backend(be) is None            # in-boundary is always fine


def test_internal_vs_external_host():
    for internal in ("ollama", "vllm", "localhost", "vllm.internal",
                     "api.svc", "10.0.0.5", "127.0.0.1", "192.168.1.9", ""):
        assert eg.is_internal_host(internal) is True, internal
    for external in ("router.huggingface.co", "api.huggingface.co",
                     "api.neysa.ai", "example.com"):
        assert eg.is_internal_host(external) is False, external


def test_is_approvable_only_for_external_unapproved():
    # external + not approved → approvable
    assert eg.is_approvable("https://router.huggingface.co/v1") is True
    # internal host → never approvable (approving egress is meaningless)
    assert eg.is_approvable("http://ollama:11434/v1") is False
    # once approved → no longer approvable
    eg.add_host("huggingface.co", added_by="owner")
    assert eg.is_approvable("https://router.huggingface.co/v1") is False


def test_sync_allowfile_writes_hosts(tmp_path, monkeypatch):
    f = tmp_path / "approved_egress.txt"
    monkeypatch.setenv("PRECEPTA_EGRESS_ALLOWFILE", str(f))
    eg.add_host("huggingface.co", added_by="owner")     # add → auto-sync
    eg.add_host("neysa.ai", added_by="owner")
    lines = [l.strip() for l in f.read_text().splitlines() if l and not l.startswith("#")]
    assert set(lines) == {"huggingface.co", "neysa.ai"}
    eg.remove_host("neysa.ai")                            # remove → auto-sync
    lines2 = [l.strip() for l in f.read_text().splitlines() if l and not l.startswith("#")]
    assert lines2 == ["huggingface.co"]


def test_sync_allowfile_noop_without_path(monkeypatch):
    monkeypatch.delenv("PRECEPTA_EGRESS_ALLOWFILE", raising=False)
    eg.add_host("example.com", added_by="owner")         # must not raise
    eg.sync_allowfile()                                   # no path → no-op


def test_broker_is_allowed_reads_allowfile(tmp_path, monkeypatch):
    f = tmp_path / "hosts.txt"
    f.write_text("# comment\nhuggingface.co\nneysa.ai\n")
    monkeypatch.setenv("PRECEPTA_EGRESS_ALLOWFILE", str(f))
    # broker reads the env at call time via module-level constant → reimport
    import importlib
    import app.sovereign.broker as broker
    importlib.reload(broker)
    assert broker.is_allowed("api.huggingface.co") is True     # subdomain
    assert broker.is_allowed("huggingface.co:443") is True     # port ignored
    assert broker.is_allowed("1.1.1.1") is False               # not approved
    assert broker.is_allowed("evilhuggingface.co") is False    # not a subdomain
    assert broker.is_allowed("") is False


def test_broker_denies_all_when_no_allowfile(tmp_path, monkeypatch):
    monkeypatch.setenv("PRECEPTA_EGRESS_ALLOWFILE", str(tmp_path / "missing.txt"))
    import importlib
    import app.sovereign.broker as broker
    importlib.reload(broker)
    assert broker.is_allowed("huggingface.co") is False        # deny-by-default


def test_attestation_reports_posture(monkeypatch):
    from app.sovereign.attestation import _egress_result
    # sealed by default
    res = _egress_result()
    assert res["posture"] == "sealed"
    assert res["approved_hosts"] == []
    # restricted once a host is approved
    eg.add_host("huggingface.co", added_by="owner")
    res2 = _egress_result()
    assert res2["posture"] == "restricted"
    assert "huggingface.co" in res2["approved_hosts"]
