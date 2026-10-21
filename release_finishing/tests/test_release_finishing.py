"""
Comprehensive automated test suite for Release Finishing & Update Channels (Step 34).
"""
import pytest
from release_finishing.core.diagnostics import SystemDiagnosticSuite
from release_finishing.core.models import (
    ReleaseChannel,
    ReleaseStatus,
)
from release_finishing.core.packager import ReleaseExportPackager
from release_finishing.core.rollout import StagedRolloutController
from release_finishing.core.updater import UpdateChannelManager


def test_packager_creates_and_verifies_bundle_integrity():
    packager = ReleaseExportPackager()

    components = {
        "registry": "0.1.0",
        "vault": "0.1.0",
        "model-gateway": "0.1.0",
        "orchestrator": "0.1.0",
        "release_finishing": "0.1.0",
    }
    changelog = [
        "Initial Pheonix Master Architecture release",
        "All 34 steps completed and verified",
    ]

    pkg = packager.build_package(
        version="1.0.0",
        channel=ReleaseChannel.STABLE,
        component_manifests=components,
        changelog=changelog,
        canary_percentage=100,
    )

    assert len(pkg.sha256_bundle_checksum) == 64
    assert packager.verify_package_integrity(pkg) is True

    # Tampering with component version breaks checksum
    pkg.component_manifests["vault"] = "0.2.0-malicious"
    assert packager.verify_package_integrity(pkg) is False


def test_staged_rollout_canary_eligibility():
    rollout = StagedRolloutController()
    packager = ReleaseExportPackager()

    pkg_canary = packager.build_package(
        version="1.1.0",
        channel=ReleaseChannel.BETA,
        component_manifests={"core": "1.1.0"},
        changelog=["Canary build"],
        canary_percentage=50,
    )
    rollout.register_release(pkg_canary)

    # 100% canary always eligible
    pkg_full = packager.build_package(
        version="1.0.0",
        channel=ReleaseChannel.STABLE,
        component_manifests={},
        changelog=[],
        canary_percentage=100,
    )
    assert rollout.is_eligible_for_update("any_client_123", pkg_full) is True

    # 0% canary never eligible
    pkg_zero = packager.build_package(
        version="2.0.0-draft",
        channel=ReleaseChannel.ALPHA,
        component_manifests={},
        changelog=[],
        canary_percentage=0,
    )
    assert rollout.is_eligible_for_update("client_xyz", pkg_zero) is False

    # 50% canary splits cohort deterministically
    results = [rollout.is_eligible_for_update(f"device_{i}", pkg_canary) for i in range(100)]
    eligible_count = sum(1 for r in results if r)
    assert 20 <= eligible_count <= 80  # Demonstrates statistical distribution around 50%


def test_staged_rollout_channel_graduation():
    rollout = StagedRolloutController()
    packager = ReleaseExportPackager()

    pkg = packager.build_package(
        version="1.0.0-rc1",
        channel=ReleaseChannel.ALPHA,
        component_manifests={},
        changelog=["Release candidate"],
    )
    rollout.register_release(pkg)

    # Cannot graduate to STABLE if health score is too low (< 0.98)
    with pytest.raises(ValueError, match="below minimum threshold"):
        rollout.graduate_channel(pkg.release_id, ReleaseChannel.STABLE, current_health_score=0.92)

    # Can graduate to BETA if health score satisfies threshold (>= 0.90)
    graduated_beta = rollout.graduate_channel(pkg.release_id, ReleaseChannel.BETA, current_health_score=0.94)
    assert graduated_beta.channel == ReleaseChannel.BETA

    # Can graduate to STABLE if health score satisfies threshold (>= 0.98)
    graduated_stable = rollout.graduate_channel(pkg.release_id, ReleaseChannel.STABLE, current_health_score=0.99)
    assert graduated_stable.channel == ReleaseChannel.STABLE
    assert graduated_stable.status == ReleaseStatus.RELEASED


def test_updater_check_and_apply_successful():
    updater = UpdateChannelManager(current_version="0.1.0", channel=ReleaseChannel.STABLE)
    packager = ReleaseExportPackager()

    new_release = packager.build_package(
        version="0.2.0",
        channel=ReleaseChannel.STABLE,
        component_manifests={"all": "0.2.0"},
        changelog=["Wave 8 features"],
        canary_percentage=100,
    )
    updater.publish_release(new_release)

    # Check for update
    available = updater.check_for_updates("my-desktop-node")
    assert available is not None
    assert available.version == "0.2.0"

    # Apply upgrade
    success, msg = updater.apply_update(available)
    assert success is True
    assert updater.current_version == "0.2.0"
    assert "0.2.0" in updater.version_history


def test_updater_automatic_rollback_on_failure():
    updater = UpdateChannelManager(current_version="0.1.0", channel=ReleaseChannel.STABLE)
    packager = ReleaseExportPackager()

    faulty_release = packager.build_package(
        version="0.3.0-faulty",
        channel=ReleaseChannel.STABLE,
        component_manifests={},
        changelog=["Experimental changes"],
        canary_percentage=100,
    )
    updater.publish_release(faulty_release)

    # Apply upgrade with simulated health failure
    success, msg = updater.apply_update(faulty_release, simulate_failure=True)
    assert success is False
    assert "cleanly rolled back to 0.1.0" in msg
    assert updater.current_version == "0.1.0"
    assert faulty_release.status == ReleaseStatus.ROLLED_BACK


def test_system_diagnostics_suite():
    diagnostics = SystemDiagnosticSuite()

    # All components healthy
    report = diagnostics.run_diagnostics()
    assert report.overall_healthy is True
    assert report.health_score == 1.0
    assert len(report.checks) == 33

    # One component failure degrades score
    degraded = diagnostics.run_diagnostics(simulate_component_failure="vault")
    assert degraded.health_score < 1.0
    vault_check = next(c for c in degraded.checks if c.component == "vault")
    assert vault_check.healthy is False
    assert "Simulated component health failure" in vault_check.message
