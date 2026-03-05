#!/usr/bin/env python3
"""
rc-agent-starter: bootstrap a complete RevenueCat project via API.

Given an RC API key and a brief app description, creates:
  - App (app_store or play_store or test_store)
  - Products (monthly + annual subscriptions)
  - Entitlement (premium)
  - Offering (default, marked as current)
  - Packages ($rc_monthly, $rc_annual)
  - Attaches everything correctly

Usage:
    RC_API_KEY=sk_... uv run python setup.py \
        --project-id projXXX \
        --app-name "My App" \
        --bundle-id com.example.myapp \
        --platform app_store
"""

from __future__ import annotations

import os
import sys
import json
import argparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from dataclasses import dataclass

BASE_URL = "https://api.revenuecat.com/v2"

OK = "\033[32m✓\033[0m"
ERR = "\033[31m✗\033[0m"
INFO = "\033[34m→\033[0m"


def rc(
    method: str,
    path: str,
    key: str,
    body: dict | None = None,
    allow_conflict: bool = False,
) -> dict:
    data = json.dumps(body).encode() if body else None
    headers: dict[str, str] = {"Authorization": f"Bearer {key}"}
    if data:
        headers["Content-Type"] = "application/json"
    req = Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(req) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        result: dict = json.loads(e.read())
        if allow_conflict and e.code == 409:
            return result  # caller handles it
        print(f"  {ERR} API error: {result.get('message', result)}", file=sys.stderr)
        sys.exit(1)


def get_or_create(
    list_path: str,
    create_path: str,
    body: dict,
    match_field: str,
    match_value: str,
    key: str,
    label: str,
) -> dict:
    """Create a resource, or fetch and return existing if conflict (409)."""
    result = rc("POST", create_path, key, body, allow_conflict=True)
    if result.get("type") == "resource_already_exists":
        items: list[dict] = rc("GET", list_path, key).get("items", [])
        existing = next((r for r in items if r.get(match_field) == match_value), None)
        if existing:
            print(f"  {OK} {label} already exists, reusing  ({existing['id']})")
            return existing
    return result


def step(label: str) -> None:
    print(f"\n{INFO} {label}")


def done(label: str, id_: str = "") -> None:
    suffix = f"  ({id_})" if id_ else ""
    print(f"  {OK} {label}{suffix}")


@dataclass
class Config:
    project_id: str
    app_name: str
    bundle_id: str
    platform: str
    key: str
    with_credits: bool = False


def setup_virtual_currency(
    project_id: str,
    key: str,
    monthly_product_id: str,
    annual_product_id: str,
    currency_code: str = "CRED",
    currency_name: str = "Credits",
    monthly_grant: int = 100,
    annual_grant: int = 1200,
) -> dict:
    """Create a virtual currency and attach product grants to it.

    Monthly subscribers receive `monthly_grant` credits; annual subscribers
    receive `annual_grant` credits. Uses the subscription + credits hybrid
    monetization pattern.
    """
    step(f"Creating virtual currency: {currency_code} ({currency_name})")
    vc = rc(
        "POST",
        f"/projects/{project_id}/virtual_currencies",
        key,
        {
            "code": currency_code,
            "name": currency_name,
            "description": "AI inference credits — spend per API call",
        },
        allow_conflict=True,
    )
    if vc.get("type") == "resource_already_exists":
        vc = rc(
            "GET", f"/projects/{project_id}/virtual_currencies/{currency_code}", key
        )
        done(f"Virtual currency {currency_code} already exists, reusing")
    else:
        done(f"Virtual currency created: {currency_code}", vc.get("code", ""))

    step(f"Attaching product grants to {currency_code}")
    updated = rc(
        "POST",
        f"/projects/{project_id}/virtual_currencies/{currency_code}",
        key,
        {
            "product_grants": [
                {"product_ids": [monthly_product_id], "amount": monthly_grant},
                {"product_ids": [annual_product_id], "amount": annual_grant},
            ]
        },
    )
    done(
        f"Grants attached: monthly={monthly_grant} credits, annual={annual_grant} credits"
    )
    return updated


def bootstrap(cfg: Config) -> None:
    print(f"\nBootstrapping RevenueCat project: {cfg.project_id}")
    print(f"App: {cfg.app_name} ({cfg.platform})\n{'─' * 50}")

    # 1. Create app
    step(f"Creating {cfg.platform} app: {cfg.app_name}")
    platform_key = cfg.platform if cfg.platform != "test_store" else None
    body: dict = {"name": cfg.app_name, "type": cfg.platform}
    if platform_key and cfg.platform == "app_store":
        body["app_store"] = {"bundle_id": cfg.bundle_id}
    elif platform_key and cfg.platform == "play_store":
        body["play_store"] = {"package_name": cfg.bundle_id}
    app = rc("POST", f"/projects/{cfg.project_id}/apps", cfg.key, body)
    app_id: str = app["id"]
    done(f"App created: {cfg.app_name}", app_id)

    # 2. Create products
    step("Creating subscription products")
    # Play Store identifiers require subscriptionId:basePlanId format
    if cfg.platform == "play_store":
        monthly_id = "premium_monthly:monthly"
        annual_id = "premium_annual:annual"
    else:
        monthly_id = f"{cfg.bundle_id}.premium_monthly"
        annual_id = f"{cfg.bundle_id}.premium_annual"

    monthly = rc(
        "POST",
        f"/projects/{cfg.project_id}/products",
        cfg.key,
        {
            "store_identifier": monthly_id,
            "type": "subscription",
            "app_id": app_id,
            "display_name": "Premium Monthly",
        },
    )
    done("Premium Monthly", monthly["id"])

    annual = rc(
        "POST",
        f"/projects/{cfg.project_id}/products",
        cfg.key,
        {
            "store_identifier": annual_id,
            "type": "subscription",
            "app_id": app_id,
            "display_name": "Premium Annual",
        },
    )
    done("Premium Annual", annual["id"])

    # 3. Create entitlement (idempotent)
    step("Creating entitlement: premium")
    ent = get_or_create(
        list_path=f"/projects/{cfg.project_id}/entitlements?limit=100",
        create_path=f"/projects/{cfg.project_id}/entitlements",
        body={"lookup_key": "premium", "display_name": "Premium Access"},
        match_field="lookup_key",
        match_value="premium",
        key=cfg.key,
        label="Entitlement 'premium'",
    )
    ent_id: str = ent["id"]
    done("Entitlement: premium", ent_id)

    # 4. Attach products to entitlement
    step("Attaching products to entitlement")
    rc(
        "POST",
        f"/projects/{cfg.project_id}/entitlements/{ent_id}/actions/attach_products",
        cfg.key,
        {"product_ids": [monthly["id"], annual["id"]]},
    )
    done("Products attached to entitlement")

    # 5. Create offering (idempotent)
    step("Creating offering: default")
    offering = get_or_create(
        list_path=f"/projects/{cfg.project_id}/offerings?limit=50",
        create_path=f"/projects/{cfg.project_id}/offerings",
        body={"lookup_key": "default", "display_name": "Default Offering"},
        match_field="lookup_key",
        match_value="default",
        key=cfg.key,
        label="Offering 'default'",
    )
    offering_id: str = offering["id"]
    done("Offering: default", offering_id)

    # 6. Create packages (idempotent)
    step("Creating packages")
    monthly_pkg = get_or_create(
        list_path=f"/projects/{cfg.project_id}/offerings/{offering_id}/packages?limit=50",
        create_path=f"/projects/{cfg.project_id}/offerings/{offering_id}/packages",
        body={"lookup_key": "$rc_monthly", "display_name": "Monthly"},
        match_field="lookup_key",
        match_value="$rc_monthly",
        key=cfg.key,
        label="Package '$rc_monthly'",
    )
    done("Package: $rc_monthly", monthly_pkg["id"])

    annual_pkg = get_or_create(
        list_path=f"/projects/{cfg.project_id}/offerings/{offering_id}/packages?limit=50",
        create_path=f"/projects/{cfg.project_id}/offerings/{offering_id}/packages",
        body={"lookup_key": "$rc_annual", "display_name": "Annual"},
        match_field="lookup_key",
        match_value="$rc_annual",
        key=cfg.key,
        label="Package '$rc_annual'",
    )
    done("Package: $rc_annual", annual_pkg["id"])

    # 7. Attach products to packages
    step("Attaching products to packages")
    rc(
        "POST",
        f"/projects/{cfg.project_id}/packages/{monthly_pkg['id']}/actions/attach_products",
        cfg.key,
        {"products": [{"product_id": monthly["id"], "eligibility_criteria": "all"}]},
    )
    done("Monthly product → $rc_monthly package")

    rc(
        "POST",
        f"/projects/{cfg.project_id}/packages/{annual_pkg['id']}/actions/attach_products",
        cfg.key,
        {"products": [{"product_id": annual["id"], "eligibility_criteria": "all"}]},
    )
    done("Annual product → $rc_annual package")

    # 8. Virtual currency (optional)
    if cfg.with_credits:
        setup_virtual_currency(
            project_id=cfg.project_id,
            key=cfg.key,
            monthly_product_id=monthly["id"],
            annual_product_id=annual["id"],
        )

    # Summary
    print(f"\n{'─' * 50}")
    print(f"{OK} Done! Your RevenueCat config is ready.\n")
    print(f"  App ID:         {app_id}")
    print(f"  Entitlement:    premium ({ent_id})")
    print(f"  Offering:       default ({offering_id})")
    if cfg.with_credits:
        print("  Credits:        CRED (monthly=100, annual=1200)")
    print(f"\n  SDK key: run `uv run python setup.py --get-key --app-id {app_id}`")
    print("\n  Next: run subscription-sanity to verify everything is wired correctly.")
    print("  https://github.com/zarpa-cat/subscription-sanity\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap a RevenueCat project")
    parser.add_argument(
        "--project-id", default=os.environ.get("RC_PROJECT_ID"), required=True
    )
    parser.add_argument("--app-name", required=True)
    parser.add_argument("--bundle-id", required=True)
    parser.add_argument(
        "--platform",
        choices=["app_store", "play_store", "test_store"],
        default="app_store",
    )
    parser.add_argument(
        "--with-credits",
        action="store_true",
        default=False,
        help="Also create a CRED virtual currency with product grants (hybrid monetization)",
    )
    args = parser.parse_args()

    key = os.environ.get("RC_API_KEY", "")
    if not key:
        print("Error: RC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    bootstrap(
        Config(
            project_id=args.project_id,
            app_name=args.app_name,
            bundle_id=args.bundle_id,
            platform=args.platform,
            key=key,
            with_credits=args.with_credits,
        )
    )


if __name__ == "__main__":
    main()
