"""Unit tests for Artifact Diff Engine."""

from canvas.artifacts.diff import ArtifactDiffEngine
from canvas.core.models import Artifact, ArtifactRevision


def test_unified_diff_generation():
    old = "line 1\nline 2\nline 3\n"
    new = "line 1\nline 2 modified\nline 3\nline 4\n"
    diff = ArtifactDiffEngine.compute_diff(old, new, filename="script.py")

    assert "script.py" in diff
    assert "-line 2" in diff
    assert "+line 2 modified" in diff
    assert "+line 4" in diff


def test_diff_summarization():
    old = "apple\nbanana\ncherry\n"
    new = "apple\nblueberry\ncherry\ndate\n"
    summary = ArtifactDiffEngine.summarize_diff(old, new)
    assert "+2 lines" in summary
    assert "-1 lines" in summary


def test_find_revision():
    artifact = Artifact(
        title="Test Artifact",
        revisions=[
            ArtifactRevision(version=1, content="v1 content"),
            ArtifactRevision(version=2, content="v2 content"),
        ],
    )

    found, content = ArtifactDiffEngine.find_revision(artifact, 1)
    assert found is True
    assert content == "v1 content"

    found, content = ArtifactDiffEngine.find_revision(artifact, 2)
    assert found is True
    assert content == "v2 content"

    not_found, content = ArtifactDiffEngine.find_revision(artifact, 3)
    assert not_found is False
    assert content == ""
