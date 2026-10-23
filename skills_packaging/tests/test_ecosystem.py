"""Unit tests for Phase 4 Ecosystem: DependencySolver, MarketplaceCatalog, and LicenseService."""

from datetime import timedelta
import pytest
from skills_packaging.core.models import PackageBundle, PackageType
from skills_packaging.marketplace.catalog import (
    MarketplaceCatalog,
    MarketplaceCategory,
    MarketplaceItem,
)
from skills_packaging.marketplace.license import (
    EntitlementTier,
    LicenseService,
    utc_now,
)
from skills_packaging.packaging.dependency_solver import DependencySolver, VersionConstraint


def test_version_constraint():
    vc_gte = VersionConstraint(">=1.2.0")
    assert vc_gte.satisfies("1.2.0") is True
    assert vc_gte.satisfies("1.3.1") is True
    assert vc_gte.satisfies("1.1.9") is False

    vc_eq = VersionConstraint("==2.0.0")
    assert vc_eq.satisfies("2.0.0") is True
    assert vc_eq.satisfies("2.0.1") is False


def test_dependency_solver_success():
    packages = {
        "pkg_core": {},
        "pkg_auth": {"pkg_core": ">=1.0.0"},
        "pkg_app": {"pkg_auth": ">=1.0.0", "pkg_core": ">=1.0.0"},
    }
    available = {
        "pkg_core": "1.2.0",
        "pkg_auth": "1.0.1",
        "pkg_app": "2.0.0",
    }
    order = DependencySolver.resolve_install_order(packages, available)
    assert order.index("pkg_core") < order.index("pkg_auth")
    assert order.index("pkg_auth") < order.index("pkg_app")


def test_dependency_solver_cycle_detection():
    packages = {
        "pkg_a": {"pkg_b": ">=1.0.0"},
        "pkg_b": {"pkg_a": ">=1.0.0"},
    }
    available = {
        "pkg_a": "1.0.0",
        "pkg_b": "1.0.0",
    }
    with pytest.raises(ValueError, match="Circular dependency detected"):
        DependencySolver.resolve_install_order(packages, available)


def test_marketplace_catalog():
    catalog = MarketplaceCatalog()
    item = MarketplaceItem(
        item_id="ext_code_helper",
        name="Code Helper Pro",
        package_type=PackageType.PLUGIN,
        category=MarketplaceCategory.CODING,
        version="1.0.0",
        description="Assists with code refactoring",
        tags=["python", "refactor"],
        required_tier="free",
    )
    bundle = PackageBundle.create(
        package_type=PackageType.PLUGIN,
        package_id="ext_code_helper",
        version="1.0.0",
        manifest_data={"name": "Code Helper Pro"},
        files={"helper.py": "# Code helper"},
    )
    catalog.publish_item(item, bundle)

    # Search
    results = catalog.search(query="refactor", category=MarketplaceCategory.CODING)
    assert len(results) == 1
    assert results[0].item_id == "ext_code_helper"

    # Download bundle
    downloaded = catalog.get_bundle("ext_code_helper")
    assert downloaded is not None
    assert downloaded.sha256_checksum == bundle.sha256_checksum
    assert catalog.get_item("ext_code_helper").downloads == 1


def test_license_service_tamper_evidence():
    service = LicenseService(secret_key="unit_test_secret_key")
    lic = service.generate_license(
        user_id="user_developer",
        tier=EntitlementTier.PRO,
        features=["advanced_tools", "browser_automation"],
    )

    # Verify valid license
    assert service.verify_license(lic) is True
    assert service.check_entitlement(lic, "free") is True
    assert service.check_entitlement(lic, "pro", feature="advanced_tools") is True
    assert service.check_entitlement(lic, "enterprise") is False

    # Tamper with tier
    lic.tier = EntitlementTier.ENTERPRISE
    assert service.verify_license(lic) is False


def test_license_expiration():
    service = LicenseService(secret_key="unit_test_secret_key")
    past = utc_now() - timedelta(days=1)
    expired_lic = service.generate_license(
        user_id="user_expired",
        tier=EntitlementTier.PRO,
        expires_at=past,
    )
    assert service.verify_license(expired_lic) is False
