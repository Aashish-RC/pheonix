"""Unit tests for Live Artifacts: Versioned history, time-travel, rollback, and storage."""

from uuid import uuid4
import pytest

from canvas.artifacts.manager import SQLiteArtifactManager
from canvas.core.models import ArtifactType


@pytest.fixture
def manager():
    return SQLiteArtifactManager(db_path=":memory:")


def test_create_and_read_artifact(manager):
    initial_code = "def hello():\n    return 'world'\n"
    artifact = manager.create_artifact(
        project_id="proj-demo",
        title="hello.py",
        artifact_type=ArtifactType.CODE,
        initial_content=initial_code,
        author="agent",
    )

    assert artifact.id is not None
    assert artifact.title == "hello.py"
    assert artifact.current_version == 1
    assert artifact.current_content == initial_code
    assert len(artifact.revisions) == 1
    assert artifact.revisions[0].author == "agent"

    fetched = manager.get_artifact(artifact.id)
    assert fetched is not None
    assert fetched.current_content == initial_code
    assert fetched.project_id == "proj-demo"


def test_update_artifact_revisions(manager):
    artifact = manager.create_artifact(
        project_id="proj-demo",
        title="doc.md",
        artifact_type=ArtifactType.MARKDOWN,
        initial_content="# Initial Title\nLine 1\n",
    )

    # Version 2
    v2_content = "# Updated Title\nLine 1\nLine 2\n"
    v2_art = manager.update_artifact(
        artifact.id,
        new_content=v2_content,
        author="user",
    )
    assert v2_art.current_version == 2
    assert v2_art.current_content == v2_content
    assert len(v2_art.revisions) == 2
    assert "+1 lines" in v2_art.revisions[1].diff_summary or "lines" in v2_art.revisions[1].diff_summary

    # Version 3
    v3_content = "# Final Title\nLine 1\nLine 2\nLine 3\n"
    v3_art = manager.update_artifact(
        artifact.id,
        new_content=v3_content,
        author="agent",
    )
    assert v3_art.current_version == 3
    assert len(v3_art.revisions) == 3


def test_artifact_rollback(manager):
    v1_code = "x = 10"
    artifact = manager.create_artifact(
        project_id="proj-demo",
        title="calc.py",
        artifact_type=ArtifactType.CODE,
        initial_content=v1_code,
    )
    manager.update_artifact(artifact.id, "x = 20")
    manager.update_artifact(artifact.id, "x = 30")

    curr = manager.get_artifact(artifact.id)
    assert curr.current_version == 3
    assert curr.current_content == "x = 30"

    # Rollback to version 1
    rolled_back = manager.rollback_artifact(artifact.id, target_version=1)
    assert rolled_back.current_version == 4
    assert rolled_back.current_content == v1_code
    assert "Rollback to version 1" in rolled_back.revisions[-1].diff_summary

    # Invalid rollback version should raise ValueError
    with pytest.raises(ValueError, match="does not exist"):
        manager.rollback_artifact(artifact.id, target_version=99)


def test_artifact_listing_and_isolation(manager):
    manager.create_artifact("proj-a", "A1", ArtifactType.CODE, "code a1")
    manager.create_artifact("proj-a", "A2", ArtifactType.MARKDOWN, "doc a2")
    manager.create_artifact("proj-b", "B1", ArtifactType.TABLE, "table b1")

    proj_a_list = manager.list_artifacts("proj-a")
    assert len(proj_a_list) == 2
    titles_a = [a.title for a in proj_a_list]
    assert "A1" in titles_a and "A2" in titles_a

    proj_b_list = manager.list_artifacts("proj-b")
    assert len(proj_b_list) == 1
    assert proj_b_list[0].title == "B1"


def test_artifact_deletion(manager):
    art = manager.create_artifact("proj-c", "ToDelete", ArtifactType.CODE, "print('bye')")
    assert manager.get_artifact(art.id) is not None

    deleted = manager.delete_artifact(art.id)
    assert deleted is True
    assert manager.get_artifact(art.id) is None
    assert manager.delete_artifact(art.id) is False
