# CLAUDE.md — rc-agent-starter codebase guide

## What this is

`rc-agent-starter` bootstraps a complete RevenueCat project configuration via
the v2 REST API — no dashboard required. Idempotent: safe to re-run.

## Stack

- **Python 3.12**, strict typing
- **`uv`** for dependency management
- **`ruff`** for lint + format — always `uv run ruff`, never bare `ruff`
- **`pytest`** for tests
- **stdlib only** (`urllib.request`) — no external HTTP dependencies

## Usage

```bash
RC_API_KEY=sk_... uv run python setup.py \
  --project-id projXXX \
  --app-name "My App" \
  --bundle-id com.example.myapp \
  --platform app_store \
  --with-credits        # optional: add CRED virtual currency
```

## What it creates

1. App (app_store / play_store / test_store)
2. Products: monthly + annual subscriptions
3. Entitlement: `premium`
4. Offering: `default` (marked current)
5. Packages: `$rc_monthly`, `$rc_annual`
6. Product → entitlement + package attachments
7. (Optional) `CRED` virtual currency with product grants (monthly=100, annual=1200)

## Conventions

- TDD: tests first in `tests/test_setup.py`
- Always `uv run ruff format` (not bare `ruff`)
- `get_or_create()` pattern: POST → if 409, GET and return existing
- Error type field is `resource_already_exists` (not `already_exists`)

## RevenueCat API gotchas

- Play Store product IDs: must be `subscriptionId:basePlanId` (e.g. `premium:monthly`)
- App Store product IDs: `{bundle_id}.product_name`
- Packages endpoint: `POST /offerings/{id}/packages` (not `/packages` directly)
- Attach products to packages: `/packages/{id}/actions/attach_products`
- Virtual currency update: `POST` not `PATCH`
- `product_grants` uses `product_ids` (array), not `product_id`

## Running tests

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```
