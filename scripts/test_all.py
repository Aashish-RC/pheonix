#!/usr/bin/env python3
"""
Pheonix Unified Test Runner
Runs automated tests across all repository components:
1. model-gateway (TypeScript / Vitest)
2. memory (Python / Pytest)
3. agent (Python / Pytest)
"""

import os
import sys
import subprocess
import time
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent

class Colors:
    GREEN = "\033[92m" if sys.stdout.isatty() else ""
    RED = "\033[91m" if sys.stdout.isatty() else ""
    BLUE = "\033[94m" if sys.stdout.isatty() else ""
    BOLD = "\033[1m" if sys.stdout.isatty() else ""
    RESET = "\033[0m" if sys.stdout.isatty() else ""

def log_header(title: str):
    print(f"\n{'=' * 60}")
    print(f">> {title}")
    print(f"{'=' * 60}")

def run_step(name: str, cmd: list[str], cwd: Path) -> bool:
    log_header(f"Running: {name} in {cwd.relative_to(ROOT_DIR)}")
    start = time.time()
    try:
        is_windows = sys.platform.startswith("win")
        result = subprocess.run(cmd, cwd=cwd, shell=is_windows)
        duration = time.time() - start
        if result.returncode == 0:
            print(f"[PASS] {name} completed in {duration:.2f}s")
            return True
        else:
            print(f"[FAIL] {name} failed with code {result.returncode} in {duration:.2f}s")
            return False
    except Exception as e:
        duration = time.time() - start
        print(f"[ERROR] {name} error: {e} in {duration:.2f}s")
        return False

def main():
    print("Starting Pheonix Unified Test Suite across all layers...")
    start_total = time.time()

    steps = [
        ("Component Registry (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "registry"),
        ("Cryptographic Vault (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "vault"),
        ("Auth & Identity (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "auth"),
        ("Rules Layer (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "rules"),
        ("Provider Activation (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "providers"),
        ("Model Gateway (Vitest)", ["pnpm", "test"], ROOT_DIR / "model-gateway"),
        ("Model Serving (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "serving"),
        ("Observability (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "observability"),
        ("Guardrails and Safety (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "guardrails"),
        ("Subscription Tracker (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "tracker"),
        ("Storage and Files (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "storage"),
        ("Memory Engine (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "memory"),
        ("Knowledge & Docs (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "knowledge"),
        ("Global Search (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "search"),
        ("Web Search & Verification (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "web_search"),
        ("Canvas & Live Artifacts (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "canvas"),
        ("Permission Modes (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "permissions"),
        ("Orchestrator (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "orchestrator"),
        ("Agent Sandboxes (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "sandboxes"),
        ("Tool & MCP Registry (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "tools_mcp"),
        ("Internal Agents (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "internal_agents"),
        ("Empirical Recommender (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "recommender"),
        ("Browser Automation (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "browser_automation"),
        ("Agent Builder (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "agent_builder"),
        ("Workflow Builder (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "workflow_builder"),
        ("Skills & Plugin Packaging (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "skills_packaging"),
        ("Notifications (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "notifications"),
        ("Voice & Speech (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "voice_speech"),
        ("Media Generation (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "media_gen"),
        ("Translation (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "translation"),
        ("Remote Access & Pairing (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "remote_access"),
        ("State Sync Engine (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "sync_engine"),
        ("Release Finishing & Update Channel (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "release_finishing"),
        ("Agent Layer (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "agent"),
    ]

    results = []
    for name, cmd, cwd in steps:
        if not cwd.exists():
            print(f"[SKIP] Directory {cwd} does not exist, skipping {name}")
            results.append((name, False))
            continue
        passed = run_step(name, cmd, cwd)
        results.append((name, passed))

    total_duration = time.time() - start_total
    log_header("Test Summary")
    all_passed = True
    for name, passed in results:
        status_text = "[PASS]" if passed else "[FAIL]"
        print(f" - {name:<30}: {status_text}")
        if not passed:
            all_passed = False

    print(f"\nTotal execution time: {total_duration:.2f}s")
    if all_passed:
        print("[SUCCESS] All test suites passed successfully!\n")
        sys.exit(0)
    else:
        print("[FAILURE] Some test suites failed.\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
