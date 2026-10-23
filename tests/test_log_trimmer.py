"""
Tests for automatic log trimming and data/ size ceiling enforcement.
"""

from pathlib import Path
from scripts.trim_logs import trim_log_file, trim_data_directory


def test_trim_log_file(tmp_path: Path):
    log_file = tmp_path / "test_overflow.log"
    # Write 1000 lines
    lines = [f"Log entry line {i}: " + ("x" * 100) + "\n" for i in range(1000)]
    log_file.write_text("".join(lines), encoding="utf-8")

    file_size_kb = log_file.stat().st_size / 1024
    assert file_size_kb > 100

    # Set tiny threshold (0.05 MB = ~50 KB) to trigger trimming
    trimmed = trim_log_file(log_file, max_mb=0.05, keep_lines=100)
    assert trimmed is True

    # Validate that only 100 lines remain
    content = log_file.read_text(encoding="utf-8").splitlines()
    assert len(content) == 100
    assert "Log entry line 999" in content[-1]


def test_trim_data_directory(tmp_path: Path):
    d = tmp_path / "data"
    d.mkdir()

    f1 = d / "trace.jsonl"
    f2 = d / "audit.log"
    f3 = d / "small.txt"

    f1.write_text("".join([f'{{"span": {i}, "data": "{"a" * 150}"}}\n' for i in range(800)]), encoding="utf-8")
    f2.write_text("".join([f'event {i}: {"b" * 150}\n' for i in range(800)]), encoding="utf-8")
    f3.write_text("tiny file\n", encoding="utf-8")

    rotated = trim_data_directory(d, max_mb=0.05, keep_lines=50)
    assert rotated == 2

    lines_f1 = f1.read_text(encoding="utf-8").splitlines()
    assert len(lines_f1) == 50
