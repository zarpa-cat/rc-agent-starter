"""Tests for rc-agent-starter bootstrap logic."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from setup import Config, get_or_create, bootstrap


class TestPlayStoreProductIds:
    """Play Store products require subscriptionId:basePlanId format."""

    def test_play_store_uses_colon_format(self) -> None:
        responses: list[dict] = [
            {"id": "app1", "object": "app", "type": "play_store"},
            {"id": "prod1", "object": "product"},
            {"id": "prod2", "object": "product"},
            {"id": "entl1", "lookup_key": "premium", "object": "entitlement"},
            {"id": "entl1", "lookup_key": "premium"},
            {"id": "off1", "lookup_key": "default", "is_current": True},
            {"id": "off1", "lookup_key": "default", "is_current": True},
            {"id": "pkg1", "lookup_key": "$rc_monthly"},
            {"id": "pkg1", "lookup_key": "$rc_monthly"},
            {"id": "pkg2", "lookup_key": "$rc_annual"},
            {"id": "pkg2", "lookup_key": "$rc_annual"},
            {"id": "pkg1"},
            {"id": "pkg2"},
        ]
        call_idx = 0

        def mock_rc(
            method: str,
            path: str,
            key: str,
            body: dict | None = None,
            allow_conflict: bool = False,
        ) -> dict:
            nonlocal call_idx
            if method == "POST" and "/products" in path and body:
                sid = body.get("store_identifier", "")
                display = (body.get("display_name") or "").lower()
                if "monthly" in display or "annual" in display:
                    assert ":" in sid, (
                        f"Play Store product ID must use subscriptionId:basePlanId format, got: {sid}"
                    )
            result = responses[min(call_idx, len(responses) - 1)]
            call_idx += 1
            return result

        cfg = Config(
            project_id="proj1",
            app_name="Test",
            bundle_id="com.test",
            platform="play_store",
            key="sk_test",
        )
        with patch("setup.rc", side_effect=mock_rc):
            bootstrap(cfg)

    def test_app_store_uses_bundle_id_prefix(self) -> None:
        call_idx = 0

        def mock_rc(
            method: str,
            path: str,
            key: str,
            body: dict | None = None,
            allow_conflict: bool = False,
        ) -> dict:
            nonlocal call_idx
            call_idx += 1
            if method == "POST" and "/products" in path and body:
                sid = body.get("store_identifier", "")
                display = (body.get("display_name") or "").lower()
                if "monthly" in display:
                    assert sid.startswith("com.myapp"), (
                        f"App Store product ID should start with bundle_id, got: {sid}"
                    )
            return {
                "id": f"r{call_idx}",
                "lookup_key": "default",
                "is_current": True,
                "items": [],
            }

        cfg = Config(
            project_id="proj1",
            app_name="Test",
            bundle_id="com.myapp",
            platform="app_store",
            key="sk_test",
        )
        with patch("setup.rc", side_effect=mock_rc):
            try:
                bootstrap(cfg)
            except (KeyError, IndexError):
                pass  # mock runs out — fine, we only care about product ID format


class TestVirtualCurrency:
    """Virtual currency (credits) bootstrap."""

    def test_credits_currency_created_when_flag_set(self) -> None:
        """With --with-credits, a CRED virtual currency is created."""
        calls: list[tuple[str, str]] = []

        def mock_rc(
            method: str,
            path: str,
            key: str,
            body: dict | None = None,
            allow_conflict: bool = False,
        ) -> dict:
            calls.append((method, path))
            if "virtual_currencies" in path and method == "POST":
                if body and body.get("code") == "CRED":
                    return {
                        "code": "CRED",
                        "name": "Credits",
                        "state": "active",
                        "product_grants": [],
                    }
                # update with product_grants
                return {
                    "code": "CRED",
                    "state": "active",
                    "product_grants": (body or {}).get("product_grants", []),
                }
            return {
                "id": f"res_{len(calls)}",
                "lookup_key": "default",
                "is_current": True,
                "items": [],
            }

        cfg = Config(
            project_id="proj1",
            app_name="Test",
            bundle_id="com.test",
            platform="test_store",
            key="sk_test",
            with_credits=True,
        )
        with patch("setup.rc", side_effect=mock_rc):
            try:
                bootstrap(cfg)
            except (KeyError, IndexError, SystemExit):
                pass

        vc_creates = [p for m, p in calls if "virtual_currencies" in p and m == "POST"]
        assert len(vc_creates) >= 1, "Expected at least one virtual_currency POST call"

    def test_no_credits_currency_without_flag(self) -> None:
        """Without --with-credits, no virtual currency endpoint is called."""
        calls: list[tuple[str, str]] = []

        def mock_rc(
            method: str,
            path: str,
            key: str,
            body: dict | None = None,
            allow_conflict: bool = False,
        ) -> dict:
            calls.append((method, path))
            return {
                "id": f"res_{len(calls)}",
                "lookup_key": "default",
                "is_current": True,
                "items": [],
            }

        cfg = Config(
            project_id="proj1",
            app_name="Test",
            bundle_id="com.test",
            platform="test_store",
            key="sk_test",
            with_credits=False,
        )
        with patch("setup.rc", side_effect=mock_rc):
            try:
                bootstrap(cfg)
            except (KeyError, IndexError, SystemExit):
                pass

        vc_calls = [p for _, p in calls if "virtual_currencies" in p]
        assert len(vc_calls) == 0, (
            f"Expected no virtual_currency calls, got: {vc_calls}"
        )

    def test_product_grants_attached_with_credits(self) -> None:
        """Credit grants (monthly=100, annual=1200) are attached after currency creation."""
        grant_bodies: list[dict] = []

        def mock_rc(
            method: str,
            path: str,
            key: str,
            body: dict | None = None,
            allow_conflict: bool = False,
        ) -> dict:
            if (
                "virtual_currencies/CRED" in path
                and method == "POST"
                and body
                and "product_grants" in body
            ):
                grant_bodies.append(body)
            return {
                "id": "res1",
                "code": "CRED",
                "state": "active",
                "lookup_key": "default",
                "is_current": True,
                "items": [],
                "product_grants": [],
            }

        monthly_id = "prodmonthly1"
        annual_id = "prodannual1"

        from setup import setup_virtual_currency

        with patch("setup.rc", side_effect=mock_rc):
            setup_virtual_currency(
                project_id="proj1",
                key="sk_test",
                monthly_product_id=monthly_id,
                annual_product_id=annual_id,
            )

        assert len(grant_bodies) == 1
        grants = grant_bodies[0]["product_grants"]
        amounts = {tuple(g["product_ids"]): g["amount"] for g in grants}
        assert amounts.get((monthly_id,)) == 100
        assert amounts.get((annual_id,)) == 1200


class TestGetOrCreate:
    def test_returns_existing_on_conflict(self) -> None:
        existing = {"id": "existing1", "lookup_key": "premium", "object": "entitlement"}

        def mock_rc(
            method: str,
            path: str,
            key: str,
            body: dict | None = None,
            allow_conflict: bool = False,
        ) -> dict:
            if method == "POST":
                return {"type": "resource_already_exists", "object": "error"}
            return {"items": [existing]}

        with patch("setup.rc", side_effect=mock_rc):
            result = get_or_create(
                list_path="/projects/p1/entitlements",
                create_path="/projects/p1/entitlements",
                body={"lookup_key": "premium"},
                match_field="lookup_key",
                match_value="premium",
                key="sk_test",
                label="Entitlement 'premium'",
            )
        assert result["id"] == "existing1"

    def test_returns_new_resource_on_success(self) -> None:
        new_resource = {"id": "new1", "lookup_key": "premium"}

        with patch("setup.rc", return_value=new_resource):
            result = get_or_create(
                list_path="/projects/p1/entitlements",
                create_path="/projects/p1/entitlements",
                body={"lookup_key": "premium"},
                match_field="lookup_key",
                match_value="premium",
                key="sk_test",
                label="Entitlement 'premium'",
            )
        assert result["id"] == "new1"
