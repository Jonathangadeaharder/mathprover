"""A pending run must be distinguishable from a failure by exit code and by run record."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

import dispatch  # noqa: E402


def test_pending_exit_code_differs_from_success_and_failure() -> None:
    # 0 ok, 1 failed, 2 dispatch error, 3 refuted are all already in use.
    assert dispatch.EXIT_PENDING not in (0, 1, 2, 3)


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


def test_dispatch_error_is_not_a_proof_failure_in_the_run_record() -> None:
    status, result, ended_at, code = dispatch.run_outcome(
        ok=False, pending=False, dispatch_error=True
    )
    assert (status, result) == ("error", "DISPATCH_ERROR")
    assert code == 2  # main()'s error code: a dispatch error is an error, not a failed proof
    assert ended_at is not None  # it did end, unlike a pending run


def test_pending_wins_over_dispatch_error() -> None:
    assert dispatch.run_outcome(ok=False, pending=True, dispatch_error=True)[3] == (
        dispatch.EXIT_PENDING
    )
