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
