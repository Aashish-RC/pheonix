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
