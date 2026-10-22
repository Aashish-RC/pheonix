"""
Pheonix Component Registry Automated Tests
Validates version manifest schemas, SemVer matching, compatibility solving,
and verified blocking of incompatible updates with explicit diagnostic reasons.
"""

import json
from pathlib import Path
import pytest

from registry import (
    ComponentRegistry,
    ComponentManifest,
    DependencyRule,
    ChangelogEntry,
    IncompatibleUpdateError,
    parse_version,
    compare_versions,
    matches_constraint,
)

MANIFESTS_DIR = Path(__file__).resolve().parent.parent / "manifests"


def test_semver_parsing_and_matching():
    # Parsing
    assert parse_version("0.1.0") == (0, 1, 0)
    assert parse_version("v1.2.3") == (1, 2, 3)

    # Comparison
    assert compare_versions("0.1.0", "0.2.0") == -1
    assert compare_versions("1.0.0", "1.0.0") == 0
    assert compare_versions("2.1.0", "2.0.9") == 1

    # Constraints
    assert matches_constraint("0.1.0", "0.1.0")
    assert matches_constraint("0.1.5", ">=0.1.0, <1.0.0")
    assert not matches_constraint("1.0.0", ">=0.1.0, <1.0.0")
    assert not matches_constraint("0.0.9", ">=0.1.0, <1.0.0")

    # Caret matching
    assert matches_constraint("0.1.5", "^0.1.0")
    assert not matches_constraint("0.2.0", "^0.1.0")
    assert matches_constraint("1.5.2", "^1.0.0")
    assert not matches_constraint("2.0.0", "^1.0.0")


def test_default_manifests_registration():
    reg = ComponentRegistry()
    manifest_files = ["vault.json", "memory.json", "model_gateway.json", "auth.json", "agent.json"]

    for fname in manifest_files:
        fpath = MANIFESTS_DIR / fname
        assert fpath.exists(), f"Manifest file missing: {fname}"
        with open(fpath, "r", encoding="utf-8") as fp:
            data = json.load(fp)
            manifest = ComponentManifest(**data)
            res = reg.register_component(manifest)
            assert res.is_compatible, f"Failed to register {manifest.name}: {res.reasons}"

    comps = reg.list_components()
    assert len(comps) == 5
    comp_names = {c.name for c in comps}
    assert comp_names == {"vault", "auth", "model-gateway", "memory", "agent"}


def test_bad_update_blocked_with_clear_reason_reverse_dependency():
    """
    CRITICAL REQUIREMENT: "Done when: A bad update is blocked with a clear reason"
    Test breaking dependency update: Propose updating 'memory' to v2.0.0
    while 'agent' requires 'memory >=0.1.0, <1.0.0'.
    """
    reg = ComponentRegistry()
    # Register vault, memory, model-gateway, and agent
    for fname in ["vault.json", "memory.json", "model_gateway.json", "agent.json"]:
        with open(MANIFESTS_DIR / fname, "r", encoding="utf-8") as fp:
            reg.register_component(ComponentManifest(**json.load(fp)))

    # Propose breaking memory update
    bad_memory_candidate = ComponentManifest(
        name="memory",
        version="2.0.0",
        description="Breaking major memory rewrite",
        dependencies=[],
        changelog=[
            ChangelogEntry(
                version="2.0.0",
                date="2026-10-21",
                changes=["Breaking storage engine changes"],
                breaking=True,
            )
        ],
    )

    plan = reg.propose_update(bad_memory_candidate)
    assert not plan.can_apply, "Incompatible update should have been blocked!"
    assert len(plan.block_reasons) > 0

    reason = plan.block_reasons[0]
    assert "Blocked:" in reason
    assert "agent" in reason
    assert "memory" in reason
    assert "requires 'memory' >=0.1.0, <1.0.0" in reason
    assert "proposed version is 2.0.0" in reason

    # Applying the update must raise IncompatibleUpdateError with reasons
    with pytest.raises(IncompatibleUpdateError) as exc_info:
        reg.apply_update(bad_memory_candidate)

    assert "is blocked:" in str(exc_info.value)
    assert exc_info.value.reasons == plan.block_reasons

    # Verify that memory remained at initial version
    initial_version = reg.get_component("memory").version
    assert initial_version != "2.0.0"


def test_bad_update_blocked_missing_prerequisite():
    reg = ComponentRegistry()
    # Register only memory
    with open(MANIFESTS_DIR / "memory.json", "r", encoding="utf-8") as fp:
        reg.register_component(ComponentManifest(**json.load(fp)))

    # Attempt to install 'agent' without 'model-gateway'
    with open(MANIFESTS_DIR / "agent.json", "r", encoding="utf-8") as fp:
        agent_manifest = ComponentManifest(**json.load(fp))

    plan = reg.propose_update(agent_manifest)
    assert not plan.can_apply
    assert any("Missing required prerequisite component 'model-gateway'" in r for r in plan.block_reasons)


def test_compatible_update_succeeds():
    reg = ComponentRegistry()
    for fname in ["vault.json", "memory.json", "model_gateway.json", "agent.json"]:
        with open(MANIFESTS_DIR / fname, "r", encoding="utf-8") as fp:
            reg.register_component(ComponentManifest(**json.load(fp)))

    initial_version = reg.get_component("memory").version
    next_minor = "0.9.0"  # satisfies 'agent's >=0.1.0, <1.0.0

    # Propose compatible memory minor update
    compatible_memory = ComponentManifest(
        name="memory",
        version=next_minor,
        description="Enhanced memory indexing",
        dependencies=[],
        changelog=[
            ChangelogEntry(
                version=next_minor,
                date="2026-10-21",
                changes=["Optimized hybrid retrieval index"],
                breaking=False,
            )
        ],
    )

    plan = reg.propose_update(compatible_memory)
    assert plan.can_apply is True
    assert len(plan.block_reasons) == 0

    applied_plan = reg.apply_update(compatible_memory)
    assert applied_plan.from_version == initial_version
    assert applied_plan.to_version == next_minor
    assert reg.get_component("memory").version == next_minor


def test_export_system_manifest():
    reg = ComponentRegistry()
    for fname in ["vault.json", "memory.json", "model_gateway.json", "auth.json", "agent.json"]:
        with open(MANIFESTS_DIR / fname, "r", encoding="utf-8") as fp:
            reg.register_component(ComponentManifest(**json.load(fp)))

    exported = reg.export_system_manifest()
    assert exported["schema_version"] == "1.0"
    assert exported["component_count"] == 5
    assert "vault" in exported["components"]
    assert "agent" in exported["components"]


def test_semver_patch_compatibility():
    """Verify patch updates satisfy strict patch and minor constraints."""
    assert matches_constraint("1.0.1", ">=1.0.0, <1.1.0")
    assert matches_constraint("1.0.9", ">=1.0.0, <1.1.0")
    assert not matches_constraint("1.1.0", ">=1.0.0, <1.1.0")
    assert matches_constraint("1.0.2", "^1.0.0")


def test_semver_minor_compatibility():
    """Verify minor version updates are compatible under caret ranges."""
    assert matches_constraint("1.1.0", "^1.0.0")
    assert matches_constraint("1.9.9", "^1.0.0")
    assert not matches_constraint("2.0.0", "^1.0.0")


def test_semver_major_breaking_compatibility():
    """Verify breaking major version updates are rejected by caret and upper-bound constraints."""
    assert not matches_constraint("2.0.0", "^1.0.0")
    assert not matches_constraint("3.0.0", "<2.0.0")
    assert not matches_constraint("2.1.0", ">=1.0.0, <2.0.0")


def test_corrupt_manifest_missing_name():
    """Verify manifest parsing fails when mandatory name field is missing."""
    corrupt_data = {
        "version": "1.0.0",
        "description": "Missing component name",
    }
    with pytest.raises(Exception):
        ComponentManifest(**corrupt_data)


def test_corrupt_manifest_invalid_semver():
    """Verify manifest parsing fails when SemVer string is malformed."""
    corrupt_data = {
        "name": "faulty-module",
        "version": "not.a.valid.semver",
        "description": "Malformed version",
    }
    with pytest.raises(Exception):
        ComponentManifest(**corrupt_data)


def test_corrupt_manifest_malformed_json(tmp_path):
    """Verify loading a truncated/corrupted JSON file raises decoding error."""
    bad_file = tmp_path / "corrupt.json"
    bad_file.write_text('{"name": "broken", "version": "1.0.0", "desc', encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        with open(bad_file, "r", encoding="utf-8") as fp:
            json.load(fp)


def test_missing_dependency_blocks_installation():
    """Verify that installing a component with an uninstalled required dependency is blocked."""
    reg = ComponentRegistry()
    manifest = ComponentManifest(
        name="web-service",
        version="1.0.0",
        description="Requires postgres backend",
        dependencies=[DependencyRule(component_name="postgres", version_constraint=">=14.0.0")],
    )
    val = reg.register_component(manifest)
    assert val.is_compatible is False
    assert any("Missing required prerequisite component 'postgres'" in r for r in val.reasons)
    assert reg.get_component("web-service") is None


def test_optional_missing_dependency_allows_installation():
    """Verify that an optional missing dependency does not block component installation."""
    reg = ComponentRegistry()
    manifest = ComponentManifest(
        name="logger",
        version="1.0.0",
        description="Logger with optional cloud sync",
        dependencies=[DependencyRule(component_name="cloud-sync", version_constraint=">=1.0.0", optional=True)],
    )
    val = reg.register_component(manifest)
    assert val.is_compatible is True
    assert reg.get_component("logger") is not None


def test_circular_dependency_self_reference_blocked():
    """Verify that a component depending on itself is blocked immediately."""
    reg = ComponentRegistry()
    manifest = ComponentManifest(
        name="ouroboros",
        version="1.0.0",
        description="Self-referencing component",
        dependencies=[DependencyRule(component_name="ouroboros", version_constraint="^1.0.0")],
    )
    val = reg.register_component(manifest)
    assert val.is_compatible is False
    assert any("cannot depend on itself (circular dependency)" in r for r in val.reasons)


def test_circular_dependency_direct_cycle_blocked():
    """Verify that two components mutually depending on each other are detected as circular."""
    reg = ComponentRegistry()
    # Install component A with dependency on B (force registration for initial state)
    comp_a = ComponentManifest(
        name="comp-a",
        version="1.0.0",
        description="Depends on B",
        dependencies=[DependencyRule(component_name="comp-b", version_constraint="^1.0.0")],
    )
    reg.register_component(comp_a, force=True)

    # Attempt to install component B that depends on A
    comp_b = ComponentManifest(
        name="comp-b",
        version="1.0.0",
        description="Depends on A",
        dependencies=[DependencyRule(component_name="comp-a", version_constraint="^1.0.0")],
    )
    val = reg.register_component(comp_b)
    assert val.is_compatible is False
    assert any("Circular dependency detected" in r for r in val.reasons)


def test_circular_dependency_transitive_cycle_blocked():
    """Verify transitive circular dependency: A -> B -> C -> A is detected."""
    reg = ComponentRegistry()
    comp_a = ComponentManifest(
        name="node-a",
        version="1.0.0",
        description="A depends on B",
        dependencies=[DependencyRule(component_name="node-b", version_constraint="^1.0.0")],
    )
    comp_b = ComponentManifest(
        name="node-b",
        version="1.0.0",
        description="B depends on C",
        dependencies=[DependencyRule(component_name="node-c", version_constraint="^1.0.0")],
    )
    reg.register_component(comp_a, force=True)
    reg.register_component(comp_b, force=True)

    # Propose C that depends on A -> forms A -> B -> C -> A cycle
    comp_c = ComponentManifest(
        name="node-c",
        version="1.0.0",
        description="C depends on A",
        dependencies=[DependencyRule(component_name="node-a", version_constraint="^1.0.0")],
    )
    val = reg.register_component(comp_c)
    assert val.is_compatible is False
    assert any("Circular dependency detected" in r for r in val.reasons)


def test_registry_force_registration_bypasses_validation():
    """Verify that force=True registers component even when validation fails."""
    reg = ComponentRegistry()
    manifest = ComponentManifest(
        name="standalone-test",
        version="1.0.0",
        description="Missing prereq",
        dependencies=[DependencyRule(component_name="nonexistent", version_constraint="^1.0.0")],
    )
    val = reg.register_component(manifest, force=True)
    assert val.is_compatible is True
    assert reg.get_component("standalone-test") is not None

