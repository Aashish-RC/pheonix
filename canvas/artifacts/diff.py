"""Artifact Diff Engine: Unified diff calculation, summary metrics, and rollback validation."""

import difflib
from typing import Tuple
from ..core.models import Artifact, ArtifactRevision


class ArtifactDiffEngine:
    """Computes unified diffs and time-travel rollback transitions across artifact revisions."""

    @staticmethod
    def compute_diff(old_content: str, new_content: str, filename: str = "artifact") -> str:
        """Generates standard unified diff lines."""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"{filename} (prev)",
            tofile=f"{filename} (next)",
        )
        return "".join(diff)

    @staticmethod
    def summarize_diff(old_content: str, new_content: str) -> str:
        """Returns concise summary of additions and deletions."""
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()

        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        added = 0
        deleted = 0
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "insert":
                added += (j2 - j1)
            elif tag == "delete":
                deleted += (i2 - i1)
            elif tag == "replace":
                deleted += (i2 - i1)
                added += (j2 - j1)

        return f"+{added} lines, -{deleted} lines"

    @staticmethod
    def find_revision(artifact: Artifact, version: int) -> Tuple[bool, str]:
        """Validates if target version exists in revision history and retrieves content."""
        for rev in artifact.revisions:
            if rev.version == version:
                return True, rev.content
        return False, ""
