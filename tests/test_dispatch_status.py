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
