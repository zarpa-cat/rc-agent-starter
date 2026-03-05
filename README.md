# rc-agent-starter

Bootstrap a complete RevenueCat project in one command. No dashboard required.

```
$ RC_API_KEY=sk_... uv run python setup.py \
    --project-id projXXXXXXXX \
    --app-name "My App" \
    --bundle-id com.example.myapp \
    --platform app_store

Bootstrapping RevenueCat project: projXXXXXXXX
App: My App (app_store)
──────────────────────────────────────────────────

→ Creating app_store app: My App
  ✓ App created: My App  (appXXXXXXXX)

→ Creating subscription products
  ✓ Premium Monthly  (prodXXXXXXXX)
  ✓ Premium Annual   (prodXXXXXXXX)

→ Creating entitlement: premium
  ✓ Entitlement: premium  (entlXXXXXXXX)

→ Attaching products to entitlement
  ✓ Products attached to entitlement

→ Creating offering: default
  ✓ Offering: default  (ofrngXXXXXXXX)

→ Creating packages
  ✓ Package: $rc_monthly  (pkgeXXXXXXXX)
  ✓ Package: $rc_annual   (pkgeXXXXXXXX)

→ Attaching products to packages
  ✓ Monthly product → $rc_monthly package
  ✓ Annual product → $rc_annual package

──────────────────────────────────────────────────
✓ Done! Your RevenueCat config is ready.
```

**Idempotent**: run it again on the same project and it reuses existing entitlements, offerings, and packages rather than failing.

---

## What it creates

The minimal working RevenueCat setup:

```
Project
└── App (iOS/Android/Play Store/test_store)
    ├── Products
    │   ├── Premium Monthly  (com.example.myapp.premium_monthly)
    │   └── Premium Annual   (com.example.myapp.premium_annual)
    ├── Entitlement: premium
    │   ├── → Premium Monthly
    │   └── → Premium Annual
    └── Offering: default (is_current: true)
        ├── $rc_monthly → Premium Monthly
        └── $rc_annual  → Premium Annual
```

After this runs, your app can initialize the SDK and check `CustomerInfo.entitlements["premium"].isActive`.

---

## Usage

```bash
# Get your API key from app.revenuecat.com → Project Settings → API keys
export RC_API_KEY=sk_...

# Run
uv run python setup.py \
  --project-id projXXXXXXXX \
  --app-name "My App" \
  --bundle-id com.example.myapp \
  --platform app_store   # or: play_store, test_store
```

**Platforms:**
- `app_store` — iOS / macOS (requires bundle ID)
- `play_store` — Android (requires package name in `subscriptionId:basePlanId` format — handled automatically)
- `test_store` — Sandbox testing, no store credentials needed

**Requirements:** Python 3.9+, `uv` (`pip install uv`)

---

## After setup

Verify with [subscription-sanity](https://github.com/zarpa-cat/subscription-sanity):

```bash
RC_API_KEY=sk_... RC_PROJECT_ID=projXXX python src/audit.py
```

Then grab your public SDK key from the dashboard (Project Settings → API keys → Public key) and initialize the SDK in your app.

---

## Platform notes

### iOS / App Store
Bundle ID must match exactly what's registered in App Store Connect.
Products are linked by `bundle_id.product_name` identifier.

### Android / Play Store  
Product identifiers follow `subscriptionId:basePlanId` format (e.g., `premium_monthly:monthly`).
This script handles the formatting automatically.

### Test Store
No credentials needed. Good for local development and CI.
RC creates a test_store app automatically when you create a project — check if one already exists.

---

## Roadmap

- [ ] `--dry-run` mode — show what would be created, don't create it
- [ ] Fetch and display SDK keys after setup
- [ ] Support custom entitlement names and product slugs
- [ ] `--with-paywall` flag — call `mcp_RC_create_design_system_paywall_generation_job` after setup

---

Built by [Zarpa](https://zarpa-cat.github.io). Pair with [subscription-sanity](https://github.com/zarpa-cat/subscription-sanity) to audit what you've built.
