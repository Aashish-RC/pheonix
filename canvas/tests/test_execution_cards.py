"""Unit tests for Card Execution Runner."""

import pytest
from canvas.execution.runner import LocalCardExecutor


@pytest.fixture
def executor():
    return LocalCardExecutor(default_timeout=3.0)


def test_execute_python_success(executor):
    code = "import math\nprint(f'PI={round(math.pi, 2)}')\n"
    res = executor.execute_python(card_id="card-math", code=code)

    assert res.card_id == "card-math"
    assert res.status == "success"
    assert res.exit_code == 0
    assert "PI=3.14" in res.stdout
    assert res.stderr == ""
    assert res.duration_ms >= 0


def test_execute_python_error(executor):
    code = "raise ValueError('Intentional error in card')"
    res = executor.execute_python(card_id="card-err", code=code)

    assert res.card_id == "card-err"
    assert res.status == "error"
    assert res.exit_code != 0
    assert "ValueError: Intentional error" in res.stderr


def test_execute_python_timeout(executor):
    code = "import time\ntime.sleep(2.0)\n"
    # Set short timeout
    res = executor.execute_python(card_id="card-timeout", code=code, timeout_seconds=0.3)

    assert res.card_id == "card-timeout"
    assert res.status == "timeout"
    assert res.exit_code == -1
    assert "timed out" in res.stderr.lower()


def test_execute_command(executor):
    res = executor.execute_command(card_id="card-cmd", command="echo CanvasCommandOutput")

    assert res.card_id == "card-cmd"
    assert res.status == "success"
    assert res.exit_code == 0
    assert "CanvasCommandOutput" in res.stdout
