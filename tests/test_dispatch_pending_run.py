"""A pending run must be distinguishable from a failure by exit code and by run record."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

import dispatch  # noqa: E402


def test_pending_exit_code_differs_from_success_and_failure() -> None:
    assert dispatch.EXIT_PENDING not in (0, 1)


def test_pending_run_is_not_marked_ended() -> None:
    status, result, ended_at, code = dispatch.run_outcome(ok=False, pending=True)
    assert (status, result, ended_at) == ("running", "RUNNING", None)
    assert code == dispatch.EXIT_PENDING


def test_failed_run_is_marked_ended() -> None:
    status, result, ended_at, code = dispatch.run_outcome(ok=False, pending=False)
    assert (status, result, code) == ("failed", "FAILED", 1)
    assert ended_at is not None


def test_successful_run_is_marked_ended() -> None:
    status, result, ended_at, code = dispatch.run_outcome(ok=True, pending=False)
    assert (status, result, code) == ("ok", "PROVEN", 0)
    assert ended_at is not None


def test_pending_wins_over_a_successful_verify() -> None:
    # A cloud task can still be running even when the last local build happened to pass.
    assert dispatch.run_outcome(ok=True, pending=True)[3] == dispatch.EXIT_PENDING
