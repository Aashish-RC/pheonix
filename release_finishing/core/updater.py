"""
Update Channel Manager handling upgrade execution, compatibility checks, and rollback safety.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from release_finishing.core.models import (
    ReleaseChannel,
    ReleasePackage,
    ReleaseStatus,
)
from release_finishing.core.rollout import StagedRolloutController


class UpdateChannelManager:
    """Coordinates version upgrades, channel selection, and automated rollback."""

    def __init__(
        self,
        current_version: str = "0.1.0",
        channel: ReleaseChannel = ReleaseChannel.STABLE,
        rollout_controller: Optional[StagedRolloutController] = None,
    ):
        self.current_version = current_version
        self.channel = channel
        self.rollout = rollout_controller or StagedRolloutController()
        self.version_history: List[str] = [current_version]
        self._available_releases: Dict[str, ReleasePackage] = {}

    def publish_release(self, release: ReleasePackage) -> None:
        self._available_releases[release.version] = release
        self.rollout.register_release(release)

    def check_for_updates(self, client_id: str = "local-device") -> Optional[ReleasePackage]:
        """Finds the newest available release matching channel and canary cohort."""
        candidates = [
            r for r in self._available_releases.values()
            if r.channel == self.channel and r.version != self.current_version
        ]
        candidates.sort(key=lambda r: r.created_at, reverse=True)

        for rel in candidates:
            if self.rollout.is_eligible_for_update(client_id, rel):
                return rel
        return None

    def apply_update(
        self,
        release: ReleasePackage,
        simulate_failure: bool = False,
    ) -> Tuple[bool, str]:
        """Applies upgrade with automatic rollback guard if validation fails."""
        previous_version = self.current_version

        # 1. Integrity check
        if release.status == ReleaseStatus.ROLLED_BACK:
            return False, "Cannot apply previously rolled-back release"

        # 2. Simulate health gate during upgrade
        if simulate_failure:
            # Trigger rollback
            release.status = ReleaseStatus.ROLLED_BACK
            self.current_version = previous_version
            return False, f"Upgrade to {release.version} failed health gate; cleanly rolled back to {previous_version}"

        # 3. Successful upgrade
        self.current_version = release.version
        self.version_history.append(release.version)
        return True, f"Successfully upgraded from {previous_version} to {release.version}"
