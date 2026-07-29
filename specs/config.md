---
type: Config
---

# Project Config

> Recipes read these at execution time. Edit freely.

| Key | Value |
|-----|-------|
| language | python |
| framework | fastapi |
| test_command | ./run.sh test |
| build_command | none |
| publish_target | none |
| git_forge | none |
| release_command | none |
| release_flow | none |
| end_state | none |
| branch_flow | main |
| protected_branches | main |

## Notes
- Python 3.14 + FastAPI + SQLite (existing `preceptaai.db`). Deps in `requirements.txt`; venv at `.venv`.
- Run: `./run.sh` (serve), `./run.sh test` (pytest, 88 tests), `./run.sh reset` (clear audit/telemetry).
- Local config/secrets via `.env` (loaded by `run.sh`) — OIDC creds, backend endpoints, `PRECEPTA_ADMIN_EMAILS`.
- Not a git repository yet; momentum CLI not installed. Founding wrote content only.
