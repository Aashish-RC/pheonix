"""
Log Trimmer Utility: Cross-platform disk guard for ./data and application logs.
Ensures log files never exceed LOG_MAX_MB, retaining the most recent LOG_KEEP_LINES.
"""

import os
from pathlib import Path


def trim_log_file(file_path: Path, max_mb: float = 10.0, keep_lines: int = 5000) -> bool:
    """If file exceeds max_mb, truncates oldest entries keeping the last keep_lines."""
    if not file_path.exists() or not file_path.is_file():
        return False

    max_bytes = int(max_mb * 1024 * 1024)
    file_size = file_path.stat().st_size
    if file_size < max_bytes:
        return False

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        trimmed_lines = lines[-keep_lines:] if len(lines) > keep_lines else lines
        temp_path = file_path.with_suffix(file_path.suffix + ".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            f.writelines(trimmed_lines)
        temp_path.replace(file_path)
        return True
    except Exception:
        return False


def trim_data_directory(
    dir_path: Path = Path("./data"),
    max_mb: float = 10.0,
    keep_lines: int = 5000,
) -> int:
    """Rotates and trims all log/jsonl files in the given directory."""
    if not dir_path.exists() or not dir_path.is_dir():
        return 0

    rotated = 0
    for p in dir_path.glob("*"):
        if p.is_file() and p.suffix in (".log", ".jsonl", ".txt"):
            if trim_log_file(p, max_mb=max_mb, keep_lines=keep_lines):
                rotated += 1
    return rotated


if __name__ == "__main__":
    import sys
    max_mb = float(os.environ.get("LOG_MAX_MB", "10"))
    keep_lines = int(os.environ.get("LOG_KEEP_LINES", "5000"))
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./data")
    count = trim_data_directory(target, max_mb=max_mb, keep_lines=keep_lines)
    print(f"Trimmed {count} oversized log file(s) in {target}")
