"""
Staged Rollout Controller managing Alpha, Beta, and Stable channel rings.
"""
from __future__ import annotations

import hashlib
from typing import Dict, List, Optional
from release_finishing.core.models import (
    ReleaseChannel,
    ReleasePackage,
    ReleaseStatus,
    RolloutRule,
)


class StagedRolloutController:
    """Manages channel rings and canary percentage gates."""

    def __init__(self):
        self._releases: Dict[str, ReleasePackage] = {}
        self._rules: Dict[ReleaseChannel, RolloutRule] = {
            ReleaseChannel.ALPHA: RolloutRule(channel=ReleaseChannel.ALPHA, min_health_score=0.80),
            ReleaseChannel.BETA: RolloutRule(channel=ReleaseChannel.BETA, min_health_score=0.90),
            ReleaseChannel.STABLE: RolloutRule(channel=ReleaseChannel.STABLE, min_health_score=0.98),
        }

    def register_release(self, release: ReleasePackage) -> None:
        self._releases[release.release_id] = release

    def get_release(self, release_id: str) -> Optional[ReleasePackage]:
        return self._releases.get(release_id)

    def is_eligible_for_update(self, client_id: str, release: ReleasePackage) -> bool:
        """Determines if a specific client is in the canary cohort for the release."""
        if release.status != ReleaseStatus.RELEASED and release.status != ReleaseStatus.STAGED:
            return False

        if release.canary_percentage >= 100:
            return True

        if release.canary_percentage <= 0:
            return False

        # Deterministic bucket: SHA-256(client_id + release.version) % 100
        digest = hashlib.sha256(f"{client_id}:{release.version}".encode("utf-8")).hexdigest()
        bucket = int(digest[:8], 16) % 100
        return bucket < release.canary_percentage

    def graduate_channel(
        self,
        release_id: str,
        target_channel: ReleaseChannel,
        current_health_score: float,
    ) -> ReleasePackage:
        """Graduates a release to a more mature channel if health score criteria is satisfied."""
        release = self._releases.get(release_id)
        if not release:
            raise ValueError(f"Unknown release '{release_id}'")

        rule = self._rules[target_channel]
        if current_health_score < rule.min_health_score:
            raise ValueError(
                f"Cannot graduate to {target_channel.value}: health score {current_health_score:.2f} "
                f"below minimum threshold {rule.min_health_score:.2f}"
            )

        release.channel = target_channel
        release.status = ReleaseStatus.RELEASED
        release.canary_percentage = 100
        return release
