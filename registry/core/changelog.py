"""
Pheonix Component Changelog Generator & Ledger
Records release notes, breaking change markers, and migration steps.
"""

from typing import List
from ..models import ChangelogEntry


class ChangelogLedger:
    """Manages component changelog history."""

    @staticmethod
    def format_markdown(component_name: str, entries: List[ChangelogEntry]) -> str:
        lines = [f"# Changelog: {component_name}", ""]
        if not entries:
            lines.append("No release entries recorded.")
            return "\n".join(lines)

        for entry in sorted(entries, key=lambda e: e.version, reverse=True):
            breaking_badge = " [BREAKING]" if entry.breaking else ""
            lines.append(f"## [{entry.version}] - {entry.date}{breaking_badge}")
            for change in entry.changes:
                lines.append(f"- {change}")
            lines.append("")

        return "\n".join(lines)
