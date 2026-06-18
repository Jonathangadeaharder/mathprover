#!/usr/bin/env python3
"""Non-destructive status check / re-attach for an already-submitted Aristotle task."""
import asyncio, sys
from aristotlelib import project as P
from aristotlelib import agent_task as T

PROJECT_ID = "eeda73ed-3d18-4d4a-bf5e-3b1d95483eca"
TASK_ID = "96b968b5-43f8-48c6-8ef6-4964b82c692d"


def show_api():
    print("Project public:", [m for m in dir(P.Project) if not m.startswith("_")])
    print("agent_task module:", [m for m in dir(T) if not m.startswith("_")])
    for cand in ("AgentTask", "Task"):
        if hasattr(T, cand):
            print(f"{cand} public:", [m for m in dir(getattr(T, cand)) if not m.startswith("_")])


async def check():
    # Try the most likely re-attach entry points; print whatever works.
    for ctor_name in ("from_id", "get", "load", "fetch", "from_project_id"):
        ctor = getattr(P.Project, ctor_name, None)
        if ctor is None:
            continue
        try:
            proj = ctor(PROJECT_ID)
            if asyncio.iscoroutine(proj):
                proj = await proj
            print(f"Project.{ctor_name} OK ->", proj)
            tasks, _ = await proj.get_tasks(limit=5)
            for t in tasks:
                print("  task", getattr(t, "agent_task_id", "?"), "status", getattr(getattr(t, "status", None), "name", t.status if hasattr(t, "status") else "?"))
            return
        except Exception as e:  # noqa: BLE001
            print(f"Project.{ctor_name} failed: {e!r}")
    print("No working re-attach constructor found; see API dump above.")


if __name__ == "__main__":
    show_api()
    if "--check" in sys.argv:
        asyncio.run(check())
