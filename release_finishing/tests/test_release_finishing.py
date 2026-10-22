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


def test_staged_rollout_zero_percent_blocks_all_cohorts():
    """Verify that a 0% canary release is never eligible for any device."""
    rollout = StagedRolloutController()
    packager = ReleaseExportPackager()
    pkg = packager.build_package(
        version="1.2.0-canary0",
        channel=ReleaseChannel.BETA,
        component_manifests={"core": "1.2.0"},
        changelog=["0% canary test"],
        canary_percentage=0,
    )
    rollout.register_release(pkg)

    for i in range(50):
        assert rollout.is_eligible_for_update(f"node_{i}", pkg) is False


def test_staged_rollout_one_hundred_percent_allows_all_cohorts():
    """Verify that a 100% canary release is immediately eligible for all devices."""
    rollout = StagedRolloutController()
    packager = ReleaseExportPackager()
    pkg = packager.build_package(
        version="1.2.0-full",
        channel=ReleaseChannel.STABLE,
        component_manifests={"core": "1.2.0"},
        changelog=["100% rollout"],
        canary_percentage=100,
    )
    rollout.register_release(pkg)

    for i in range(50):
        assert rollout.is_eligible_for_update(f"device_{i}", pkg) is True


def test_staged_rollout_twenty_five_percent_distribution():
    """Verify that a 25% rollout splits client cohorts proportionally."""
    rollout = StagedRolloutController()
    packager = ReleaseExportPackager()
    pkg = packager.build_package(
        version="1.3.0-canary25",
        channel=ReleaseChannel.BETA,
        component_manifests={},
        changelog=["25% rollout"],
        canary_percentage=25,
    )
    rollout.register_release(pkg)

    results = [rollout.is_eligible_for_update(f"client_test_{i}", pkg) for i in range(200)]
    eligible_count = sum(1 for r in results if r)
    # 25% of 200 is 50; statistical variance expected between 30 and 70
    assert 25 <= eligible_count <= 75


def test_staged_rollout_canary_deterministic_reproducibility():
    """Verify eligibility decision for a given client_id and version is completely deterministic."""
    rollout = StagedRolloutController()
    packager = ReleaseExportPackager()
    pkg = packager.build_package(
        version="1.4.0-canary50",
        channel=ReleaseChannel.BETA,
        component_manifests={},
        changelog=["Canary check"],
        canary_percentage=50,
    )
    rollout.register_release(pkg)

    client_id = "reproducible-device-id-999"
    first_eval = rollout.is_eligible_for_update(client_id, pkg)
    for _ in range(20):
        assert rollout.is_eligible_for_update(client_id, pkg) == first_eval


def test_major_version_upgrade_blocked_by_default():
    """Verify that major-version upgrades (e.g. 0.1.0 -> 1.0.0 or 1.0.0 -> 2.0.0) are blocked by default."""
    updater = UpdateChannelManager(current_version="1.0.0", channel=ReleaseChannel.STABLE)
    packager = ReleaseExportPackager()

    major_release = packager.build_package(
        version="2.0.0",
        channel=ReleaseChannel.STABLE,
        component_manifests={"core": "2.0.0"},
        changelog=["Breaking 2.0 overhaul"],
        canary_percentage=100,
    )
    updater.publish_release(major_release)

    # Attempting major upgrade without allow_major fails
    success, msg = updater.apply_update(major_release)
    assert success is False
    assert "Major-version upgrade" in msg
    assert "is blocked" in msg
    assert updater.current_version == "1.0.0"


def test_major_version_upgrade_allowed_with_explicit_flag():
    """Verify that passing allow_major=True permits a major version upgrade."""
    updater = UpdateChannelManager(current_version="1.0.0", channel=ReleaseChannel.STABLE)
    packager = ReleaseExportPackager()

    major_release = packager.build_package(
        version="2.0.0",
        channel=ReleaseChannel.STABLE,
        component_manifests={"core": "2.0.0"},
        changelog=["Breaking 2.0 overhaul"],
        canary_percentage=100,
    )
    updater.publish_release(major_release)

    success, msg = updater.apply_update(major_release, allow_major=True)
    assert success is True
    assert updater.current_version == "2.0.0"
    assert "Successfully upgraded" in msg


def test_major_version_upgrade_manager_level_permission():
    """Verify that setting allow_major_upgrades=True on the manager permits major upgrades."""
    updater = UpdateChannelManager(
        current_version="1.5.0", channel=ReleaseChannel.STABLE, allow_major_upgrades=True
    )
    packager = ReleaseExportPackager()

    major_release = packager.build_package(
        version="2.0.0",
        channel=ReleaseChannel.STABLE,
        component_manifests={"core": "2.0.0"},
        changelog=["Breaking 2.0 overhaul"],
        canary_percentage=100,
    )
    updater.publish_release(major_release)

    success, msg = updater.apply_update(major_release)
    assert success is True
    assert updater.current_version == "2.0.0"


def test_check_for_updates_hides_major_upgrades_when_blocked():
    """Verify check_for_updates filters out major upgrades if not permitted."""
    updater = UpdateChannelManager(current_version="1.0.0", channel=ReleaseChannel.STABLE)
    packager = ReleaseExportPackager()

    major_release = packager.build_package(
        version="2.0.0",
        channel=ReleaseChannel.STABLE,
        component_manifests={},
        changelog=["Major 2.0"],
        canary_percentage=100,
    )
    updater.publish_release(major_release)

    # Without allow_major, none found
    assert updater.check_for_updates("device-1", allow_major=False) is None

    # With allow_major, discovered
    found = updater.check_for_updates("device-1", allow_major=True)
    assert found is not None
    assert found.version == "2.0.0"


def test_rollback_trigger_on_simulated_health_failure():
    """Verify that health failure triggers a rollback to the exact previous version."""
    updater = UpdateChannelManager(current_version="1.2.0", channel=ReleaseChannel.STABLE)
    packager = ReleaseExportPackager()

    bad_release = packager.build_package(
        version="1.3.0",
        channel=ReleaseChannel.STABLE,
        component_manifests={},
        changelog=["Regression build"],
        canary_percentage=100,
    )
    updater.publish_release(bad_release)

    success, msg = updater.apply_update(bad_release, simulate_failure=True)
    assert success is False
    assert "cleanly rolled back to 1.2.0" in msg
    assert updater.current_version == "1.2.0"
    assert bad_release.status == ReleaseStatus.ROLLED_BACK


def test_rollback_cannot_reapply_failed_release():
    """Verify that a release in ROLLED_BACK status cannot be reapplied."""
    updater = UpdateChannelManager(current_version="1.0.0", channel=ReleaseChannel.STABLE)
    packager = ReleaseExportPackager()

    rel = packager.build_package(
        version="1.1.0",
        channel=ReleaseChannel.STABLE,
        component_manifests={},
        changelog=["Testing rollback lock"],
        canary_percentage=100,
    )
    rel.status = ReleaseStatus.ROLLED_BACK
    updater.publish_release(rel)

    success, msg = updater.apply_update(rel)
    assert success is False
    assert "Cannot apply previously rolled-back release" in msg


def test_sequential_upgrades_and_rollbacks_state_consistency():
    """Verify state consistency across multiple upgrades and rollbacks."""
    updater = UpdateChannelManager(current_version="1.0.0", channel=ReleaseChannel.STABLE)
    packager = ReleaseExportPackager()

    rel1 = packager.build_package(version="1.1.0", channel=ReleaseChannel.STABLE, component_manifests={}, changelog=[], canary_percentage=100)
    rel2 = packager.build_package(version="1.2.0", channel=ReleaseChannel.STABLE, component_manifests={}, changelog=[], canary_percentage=100)
    rel3 = packager.build_package(version="1.3.0", channel=ReleaseChannel.STABLE, component_manifests={}, changelog=[], canary_percentage=100)

    # 1. 1.0.0 -> 1.1.0 success
    s1, _ = updater.apply_update(rel1)
    assert s1 is True and updater.current_version == "1.1.0"

    # 2. 1.1.0 -> 1.2.0 failure -> rolls back to 1.1.0
    s2, _ = updater.apply_update(rel2, simulate_failure=True)
    assert s2 is False and updater.current_version == "1.1.0"

    # 3. 1.1.0 -> 1.3.0 success
    s3, _ = updater.apply_update(rel3)
    assert s3 is True and updater.current_version == "1.3.0"
    assert updater.version_history == ["1.0.0", "1.1.0", "1.3.0"]

