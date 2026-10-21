"""
Pheonix Component Compatibility & Update Validator
Enforces dependency rules, prevents breaking changes, and blocks bad updates with clear diagnostic reasons.
"""

from typing import Dict, List, Optional
from ..models import ComponentManifest, ValidationResult
from .semver import matches_constraint


class CompatibilityValidator:
    """
    Validates dependency graphs and evaluates candidate updates against installed components.
    Guarantees: A bad update is blocked with an explicit, readable reason.
    """

    @staticmethod
    def validate_installation(
        candidate: ComponentManifest,
        installed: Dict[str, ComponentManifest],
    ) -> ValidationResult:
        """
        Validate whether candidate manifest can be installed or updated
        without violating forward or reverse dependency constraints.
        """
        reasons: List[str] = []
        affected: List[str] = []

        # 1. Forward Dependency Check: Check all prerequisites required by candidate
        for rule in candidate.dependencies:
            dep_name = rule.component_name
            if dep_name not in installed:
                if not rule.optional:
                    reasons.append(
                        f"Blocked: Missing required prerequisite component '{dep_name}' "
                        f"(requires constraint '{rule.version_constraint}')."
                    )
                    affected.append(dep_name)
                continue

            dep_installed = installed[dep_name]
            if not matches_constraint(dep_installed.version, rule.version_constraint):
                reasons.append(
                    f"Blocked: Component '{candidate.name}' requires '{dep_name}' {rule.version_constraint}, "
                    f"but installed version is {dep_installed.version}."
                )
                affected.append(dep_name)

        # 2. Reverse Dependency Check: Verify that existing installed components won't break
        # if this candidate replaces an existing component
        simulated_installed = dict(installed)
        simulated_installed[candidate.name] = candidate

        for comp_name, comp in installed.items():
            if comp_name == candidate.name:
                continue

            for rule in comp.dependencies:
                if rule.component_name == candidate.name:
                    if not matches_constraint(candidate.version, rule.version_constraint):
                        reasons.append(
                            f"Blocked: Existing component '{comp.name}' requires '{candidate.name}' "
                            f"{rule.version_constraint}, but proposed version is {candidate.version}."
                        )
                        affected.append(comp.name)

        is_compatible = len(reasons) == 0
        return ValidationResult(
            is_compatible=is_compatible,
            reasons=reasons,
            affected_components=list(set(affected)),
        )
