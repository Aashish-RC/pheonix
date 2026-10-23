#!/usr/bin/env python3
"""
Pheonix Unified Test Runner
Runs automated tests across all 35 repository components (Python / Pytest and TypeScript / Vitest):
- Intelligence: model-gateway, serving, memory, knowledge, search, web_search, guardrails, rules, recommender, resource_optimizer
- Agency: orchestrator, agent_builder, sandboxes, internal_agents, workflow_builder, tools_mcp, browser_automation, skills_packaging, permissions, agent
- Trust & Ops: vault, auth, providers, tracker, observability, release_finishing, remote_access, sync_engine
- Shared Services: storage, notifications, voice_speech, media_gen, translation, canvas, registry
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

import re

def parse_test_count(output: str) -> int:
    """Extracts test count from pytest or vitest terminal output."""
    # Vitest format: Tests  X passed (X)
    vitest_match = re.search(r"Tests\s+(\d+)\s+passed", output)
    if vitest_match:
        return int(vitest_match.group(1))

    # Pytest format: == X passed in Ys ==
    pytest_match = re.search(r"(=+\s*(\d+)\s+passed|collected\s+(\d+)\s+items)", output)
    if pytest_match:
        return int(pytest_match.group(2) or pytest_match.group(3))

    # Fallback to any '\b\d+ passed\b'
    generic_match = re.search(r"(\d+)\s+passed", output)
    if generic_match:
        return int(generic_match.group(1))

    return 0

def run_step(name: str, cmd: list[str], cwd: Path) -> tuple[bool, int, float]:
    log_header(f"Running: {name} in {cwd.relative_to(ROOT_DIR)}")
    start = time.time()
    try:
        is_windows = sys.platform.startswith("win")
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            str(ROOT_DIR) + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
        )
        result = subprocess.run(
            cmd,
            cwd=cwd,
            shell=is_windows,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        duration = time.time() - start
        output = result.stdout or ""
        test_count = parse_test_count(output)

        if result.returncode == 0:
            print(output[-800:] if len(output) > 800 else output)
            print(f"[PASS] {name} completed: {test_count} tests in {duration:.2f}s")
            return True, test_count, duration
        else:
            print(output[-1200:] if len(output) > 1200 else output)
            print(f"[FAIL] {name} failed with code {result.returncode} in {duration:.2f}s")
            return False, test_count, duration
    except Exception as e:
        duration = time.time() - start
        print(f"[ERROR] {name} error: {e} in {duration:.2f}s")
        return False, 0, duration

def main():
    print("Starting Pheonix Unified Test Suite across all layers...")
    start_total = time.time()

    steps = [
        ("Component Registry (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "registry"),
        ("Cryptographic Vault (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "vault"),
        ("Auth & Identity (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "auth"),
        ("Unified Audit Log (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "audit"),
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
        ("Resource Optimizer (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "resource_optimizer"),
        ("Agent Layer (Pytest)", [sys.executable, "-m", "pytest", "tests/"], ROOT_DIR / "agent"),
    ]

    results = []
    total_tests = 0
    for name, cmd, cwd in steps:
        if not cwd.exists():
            print(f"[SKIP] Directory {cwd} does not exist, skipping {name}")
            results.append((name, False, 0, 0.0))
            continue
        passed, count, duration = run_step(name, cmd, cwd)
        total_tests += count
        results.append((name, passed, count, duration))

    total_duration = time.time() - start_total
    all_passed = all(p for _, p, _, _ in results)

    # Formatted aligned matrix output
    sep_line = "=" * 80
    sub_sep = "-" * 80
    print(f"\n{sep_line}")
    print(f"{f'Pheonix Test Suite Matrix ({len(steps)} Modules)':^80}")
    print(f"{sep_line}")
    print(f"{'Module':<45} | {'Tests':>8} | {'Duration':>10} | {'Status':^8}")
    print(sub_sep)

    for name, passed, count, duration in results:
        status_str = "PASS" if passed else "FAIL"
        count_str = str(count) if count > 0 else "-"
        print(f"{name:<45} | {count_str:>8} | {duration:>9.2f}s | {status_str:^8}")

    print(sep_line)
    summary_status = "ALL PASSED" if all_passed else "FAILED"
    print(f"{f'TOTAL: {len(steps)} Modules':<45} | {total_tests:>8} | {total_duration:>9.2f}s | {summary_status:^8}")
    print(f"{sep_line}\n")

    if all_passed:
        print(f"[SUCCESS] All {len(results)} module test suites passed ({total_tests} tests in {total_duration:.2f}s).\n")
        sys.exit(0)
    else:
        print("[FAILURE] Some test suites failed.\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
