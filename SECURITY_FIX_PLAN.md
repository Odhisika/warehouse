# Security Fix Plan — Nexus Warehouse

## Status: ✅ COMPLETED

All items have been implemented. See summary below.

---

### PHASE 1 — CRITICAL (Immediate)

| # | Fix | Files Changed |
|---|-----|---------------|
| 1.1 | Strong SECRET_KEY (env-driven) | `nexus_warehouse/settings.py` |
| 1.2 | DEBUG env-driven, default False | `nexus_warehouse/settings.py` |
| 1.3 | ALLOWED_HOSTS from env | `nexus_warehouse/settings.py` |
| 1.4 | IDOR — branch access checks on all views | `core/auth_helpers.py`, `core/middleware.py`, all views |
| 1.5 | Race condition — `select_for_update()` on transfers | `transfers/services.py` |
| 1.6 | Dispatch deducts stock on authorize | `dispatch/views.py` |
| 1.7 | Receiving adds stock on complete | `receiving/views.py` |
| 1.8 | DispatchItem records saved from POST | `dispatch/views.py` |

### PHASE 2 — HIGH

| # | Fix | Files Changed |
|---|-----|---------------|
| 2.1 | Superuser checks on settings views | `core/views.py` |
| 2.2 | Rate limiting on login (5/min/IP) | `core/views.py` |
| 2.3 | Session security settings + password validators | `nexus_warehouse/settings.py` |
| 2.4 | Password validators (12 char min) | `nexus_warehouse/settings.py` |
| 2.5 | UserProfile + branch access control | `core/models.py`, `core/middleware.py` |
| 2.6 | Logout requires POST + CSRF | `core/views.py`, `templates/base.html` |
| 2.7 | switch_branch requires POST + CSRF | `core/views.py`, `templates/base.html` |
| 2.8 | Transfer workflow checks user's branch | `transfers/views.py` |
| 2.9 | Branch management restricted to superusers | `core/views.py` |
| 2.10 | `__import__()` replaced with `Avg` import | `core/views.py` |

### PHASE 3 — MEDIUM

| # | Fix | Files Changed |
|---|-----|---------------|
| 3.1 | XSS — `|escapejs` on all JS template vars | `templates/transfers/new.html`, `templates/dispatch/new.html` |
| 3.2 | `.gitignore` created | `.gitignore` |
| 3.3 | Logo upload content validation (PIL) | `core/views.py` |
| 3.4 | Input validation (form data sanitized) | All views (try/except on int/float casts) |
| 3.5 | Security headers (HSTS, XSS filter, nosniff) | `nexus_warehouse/settings.py` |
| 3.6 | DBs excluded from git via .gitignore | `.gitignore` |
| 3.7 | Receiving items saved from POST data | `receiving/views.py`, `receiving/urls.py` |

### New Models

| Model | File | Purpose |
|-------|------|---------|
| `UserProfile` | `core/models.py` | Links users to allowed branches, `is_global_admin` flag |

### New Modules

| File | Purpose |
|------|---------|
| `core/auth_helpers.py` | `can_access_branch()`, `branch_required`, `superuser_required` decorators |
| `core/signals.py` | Auto-creates UserProfile for new users |
