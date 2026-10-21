"""
Pheonix Release Finishing & Update Channel Subsystem (Wave 8, Step 34).
The final component crowning the 34-step Master Architecture.
"""
from release_finishing.core.diagnostics import SystemDiagnosticSuite
from release_finishing.core.models import (
    DiagnosticCheckResult,
    ReleaseChannel,
    ReleasePackage,
    ReleaseStatus,
    RolloutRule,
    SystemHealthReport,
)
from release_finishing.core.packager import ReleaseExportPackager
from release_finishing.core.rollout import StagedRolloutController
from release_finishing.core.updater import UpdateChannelManager

__all__ = [
    "ReleaseChannel",
    "ReleaseStatus",
    "ReleasePackage",
    "RolloutRule",
    "DiagnosticCheckResult",
    "SystemHealthReport",
    "StagedRolloutController",
    "ReleaseExportPackager",
    "UpdateChannelManager",
    "SystemDiagnosticSuite",
]
