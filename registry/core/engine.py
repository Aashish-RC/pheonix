"""
Pheonix Component Registry Engine
Manages registered component manifests, evaluates updates, and gates changes.
"""

from typing import Dict, List, Optional, Any
import time

from ..models import ComponentManifest, ValidationResult, UpdatePlan
from .validator import CompatibilityValidator


class IncompatibleUpdateError(Exception):
    """Raised when an update is blocked due to incompatibility."""
    def __init__(self, message: str, reasons: List[str]):
        super().__init__(message)
        self.reasons = reasons


class ComponentRegistry:
    """
    Central registry for versioned Pheonix components.
    Guarantees that incompatible or broken component updates are blocked with clear diagnostics.
    """

    def __init__(self):
        self._components: Dict[str, ComponentManifest] = {}
        self._history: List[Dict[str, Any]] = []

    def get_component(self, name: str) -> Optional[ComponentManifest]:
        return self._components.get(name)

    def list_components(self) -> List[ComponentManifest]:
        return list(self._components.values())

    def register_component(
        self,
        manifest: ComponentManifest,
        force: bool = False,
    ) -> ValidationResult:
        """Register a new component into the registry."""
        if not force:
            val_res = CompatibilityValidator.validate_installation(manifest, self._components)
            if not val_res.is_compatible:
                return val_res

        self._components[manifest.name] = manifest
        self._history.append({
            "action": "REGISTER",
            "component": manifest.name,
            "version": manifest.version,
            "timestamp": time.time(),
        })
        return ValidationResult(is_compatible=True, reasons=[], affected_components=[])

    def propose_update(self, candidate: ComponentManifest) -> UpdatePlan:
        """
        Evaluate an update proposal without applying it.
        Returns an UpdatePlan detailing whether it can be applied and any block reasons.
        """
        current = self._components.get(candidate.name)
        from_v = current.version if current else None

        val_res = CompatibilityValidator.validate_installation(candidate, self._components)
        return UpdatePlan(
            component_name=candidate.name,
            from_version=from_v,
            to_version=candidate.version,
            can_apply=val_res.is_compatible,
            block_reasons=val_res.reasons,
        )

    def apply_update(self, candidate: ComponentManifest) -> UpdatePlan:
        """
        Apply an update to a component.
        BLOCKS and raises IncompatibleUpdateError if compatibility validation fails.
        """
        plan = self.propose_update(candidate)
        if not plan.can_apply:
            reason_str = "; ".join(plan.block_reasons)
            raise IncompatibleUpdateError(
                f"Update for component '{candidate.name}' to v{candidate.version} is blocked: {reason_str}",
                reasons=plan.block_reasons,
            )

        self._components[candidate.name] = candidate
        self._history.append({
            "action": "UPDATE",
            "component": candidate.name,
            "from_version": plan.from_version,
            "to_version": candidate.version,
            "timestamp": time.time(),
        })
        return plan

    def export_system_manifest(self) -> Dict[str, Any]:
        """Export system-wide component manifest."""
        return {
            "schema_version": "1.0",
            "generated_at": time.time(),
            "component_count": len(self._components),
            "components": {
                name: comp.model_dump()
                for name, comp in self._components.items()
            },
        }
