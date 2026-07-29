"""A cloud task that outlives the local poll cap must not be recorded as a failure."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from dispatch import append_status  # noqa: E402


def test_failure_marks_node_todo(tmp_path: Path) -> None:
    append_status(tmp_path, prover="aristotle", ok=False, log_rel="log.txt")
    text = (tmp_path / "status.md").read_text(encoding="utf-8")
    assert "state: todo" in text
    assert "aristotle: failed" in text


def test_success_marks_node_done(tmp_path: Path) -> None:
    append_status(tmp_path, prover="aristotle", ok=True, log_rel="log.txt")
    text = (tmp_path / "status.md").read_text(encoding="utf-8")
    assert "state: done" in text
    assert "aristotle: ok" in text


def test_pending_is_not_a_failure(tmp_path: Path) -> None:
    append_status(
        tmp_path,
        prover="aristotle",
        ok=False,
        log_rel="log.txt",
        pending="python3 agents/aristotle_attach.py --project-id P --task-id T --node N --wait",
    )
    text = (tmp_path / "status.md").read_text(encoding="utf-8")
    assert "failed" not in text
    assert "state: running" in text
    assert "aristotle: running" in text
    assert "aristotle_attach.py --project-id P --task-id T" in text


def test_pending_does_not_overwrite_an_existing_state(tmp_path: Path) -> None:
    (tmp_path / "status.md").write_text("state: PROVEN\n", encoding="utf-8")
    append_status(tmp_path, prover="aristotle", ok=False, log_rel="log.txt", pending="reattach cmd")
    text = (tmp_path / "status.md").read_text(encoding="utf-8")
    assert text.startswith("state: PROVEN")
    assert "failed" not in text
    assert "reattach cmd" in text


def test_pending_rewrites_a_stale_state_header(tmp_path: Path) -> None:
    # scripts/build_graph.py reads only `^state:`, so a stale header hides a pending run.
    (tmp_path / "status.md").write_text("state: todo\n\nsome notes\n", encoding="utf-8")
    append_status(tmp_path, prover="aristotle", ok=False, log_rel="log.txt", pending="reattach cmd")
    text = (tmp_path / "status.md").read_text(encoding="utf-8")
    assert text.startswith("state: running")
    assert "state: todo" not in text
    assert "some notes" in text
    assert "reattach cmd" in text


def test_non_pending_leaves_an_existing_header_alone(tmp_path: Path) -> None:
    (tmp_path / "status.md").write_text("state: PROVEN\n", encoding="utf-8")
    append_status(tmp_path, prover="aristotle", ok=False, log_rel="log.txt")
    assert (tmp_path / "status.md").read_text(encoding="utf-8").startswith("state: PROVEN")


def test_dispatch_error_is_not_a_proof_failure(tmp_path: Path) -> None:
    # A 502 at submit time means the prover never ran; the node is untouched.
    (tmp_path / "status.md").write_text("state: todo\n", encoding="utf-8")
    append_status(
        tmp_path,
        prover="aristotle",
        ok=False,
        log_rel="log.txt",
        dispatch_error="Request failed: 502 Server Error",
    )
    text = (tmp_path / "status.md").read_text(encoding="utf-8")
    assert "aristotle: failed" not in text
    assert "dispatch error" in text
    assert "502" in text


def test_dispatch_error_leaves_a_proved_node_proved(tmp_path: Path) -> None:
    (tmp_path / "status.md").write_text("state: PROVEN\n", encoding="utf-8")
    append_status(tmp_path, prover="aristotle", ok=False, log_rel="log.txt", dispatch_error="boom")
    assert (tmp_path / "status.md").read_text(encoding="utf-8").startswith("state: PROVEN")


def test_dispatch_error_clears_a_stale_running_header(tmp_path: Path) -> None:
    # Left `running` by an earlier pending run. No cloud task is alive after a
    # submit failure.
    (tmp_path / "status.md").write_text("state: running\n\nnotes\n", encoding="utf-8")
    append_status(tmp_path, prover="aristotle", ok=False, log_rel="log.txt", dispatch_error="502")
    text = (tmp_path / "status.md").read_text(encoding="utf-8")
    assert text.startswith("state: todo")
    assert "notes" in text


def test_pending_line_carries_a_runnable_reattach_command(tmp_path: Path) -> None:
    # The printed command is the only way back to a run that outlived the poll
    # cap. `python3` alone cannot import aristotlelib.
    append_status(
        tmp_path,
        prover="aristotle",
        ok=False,
        log_rel="log.txt",
        pending="cd agents && uv run python aristotle_attach.py --project-id P --wait",
    )
    text = (tmp_path / "status.md").read_text(encoding="utf-8")
    assert "uv run python aristotle_attach.py" in text
    assert "python3 agents/aristotle_attach.py" not in text
