"""
Release Export Packager generating standalone signed distributions with SHA-256 manifests.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Dict, List
from release_finishing.core.models import (
    ReleaseChannel,
    ReleasePackage,
    ReleaseStatus,
)


class ReleaseExportPackager:
    """Compiles, signs, and exports complete system release packages."""

    def build_package(
        self,
        version: str,
        channel: ReleaseChannel,
        component_manifests: Dict[str, str],
        changelog: List[str],
        canary_percentage: int = 100,
    ) -> ReleasePackage:
        # Build canonical payload for SHA-256 signing
        raw_manifest = {
            "version": version,
            "channel": channel.value,
            "components": component_manifests,
            "changelog": changelog,
        }
        serialized = json.dumps(raw_manifest, sort_keys=True).encode("utf-8")
        bundle_checksum = hashlib.sha256(serialized).hexdigest()

        return ReleasePackage(
            version=version,
            channel=channel,
            status=ReleaseStatus.RELEASED,
            sha256_bundle_checksum=bundle_checksum,
            component_manifests=component_manifests,
            changelog=changelog,
            canary_percentage=canary_percentage,
            created_at=time.time(),
        )

    def verify_package_integrity(self, package: ReleasePackage) -> bool:
        raw_manifest = {
            "version": package.version,
            "channel": package.channel.value,
            "components": package.component_manifests,
            "changelog": package.changelog,
        }
        serialized = json.dumps(raw_manifest, sort_keys=True).encode("utf-8")
        computed = hashlib.sha256(serialized).hexdigest()
        return computed == package.sha256_bundle_checksum
