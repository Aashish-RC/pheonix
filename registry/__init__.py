"""
Pheonix Component Registry Package
"""

from .core.engine import (
    ComponentRegistry,
    IncompatibleUpdateError,
)
from .core.validator import CompatibilityValidator
from .core.semver import (
    parse_version,
    compare_versions,
    matches_constraint,
    InvalidVersionError,
)
from .core.changelog import ChangelogLedger
from .models import (
    ComponentManifest,
    DependencyRule,
    ChangelogEntry,
    ValidationResult,
    UpdatePlan,
)

__all__ = [
    "ComponentRegistry",
    "IncompatibleUpdateError",
    "CompatibilityValidator",
    "parse_version",
    "compare_versions",
    "matches_constraint",
    "InvalidVersionError",
    "ChangelogLedger",
    "ComponentManifest",
    "DependencyRule",
    "ChangelogEntry",
    "ValidationResult",
    "UpdatePlan",
]
