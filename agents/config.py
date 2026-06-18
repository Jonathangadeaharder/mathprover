"""Load mathprover.toml configuration."""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


_ENV_VAR = re.compile(r"^\$\{([^}:]+)(?::-([^}]*))?\}$")


def expand_config_value(value: str) -> str:
    match = _ENV_VAR.fullmatch(value.strip())
    if not match:
        return os.path.expanduser(value)
    var, default = match.group(1), match.group(2) or ""
    return os.environ.get(var, default)


@dataclass
class ProverConfig:
    name: str
    type: str
    command: str
    model: str = ""
    base_url: str = ""
    max_attempts: int = 4
    max_tokens: int = 32768
    correction_rounds: int = 2
    initial_max_tokens: int = 28000
    correction_max_tokens: int = 8000
    temperature: float = 1.0
    top_p: float = 0.95
    poll_interval_seconds: int = 30
    max_wait_minutes: int = 120
    requires_env: list[str] = field(default_factory=list)


@dataclass
class RoutingConfig:
    default_leaf: str
    default_capstone: str
    escalate_after_failures: int
    capstone_node: str
    leaves: list[dict[str, str]]
    second_wave: list[dict[str, Any]]
    capstone: list[dict[str, Any]]
    default_mid: str = ""  # 3-tier escalation: leaf -> mid -> capstone (empty = 2-tier)


@dataclass
class ResourceLimitsConfig:
    max_concurrent_goedel: int = 1
    min_free_memory_gib: float = 12.0
    forbid_parallel_dispatch: bool = True


@dataclass
class MathProverConfig:
    project_root: Path
    provers: dict[str, ProverConfig]
    routing: RoutingConfig
    resources: ResourceLimitsConfig


def resolve_project_root(project_root: Path | None = None) -> Path:
    if project_root is not None:
        return project_root.resolve()
    env = os.environ.get("MATHPROVER_PROJECT_PATH")
    if env:
        return Path(env).resolve()
    cwd = Path.cwd().resolve()
    if (cwd / "mathprover.toml").exists():
        return cwd
    raise FileNotFoundError(
        "Lean project root required: pass --root or set MATHPROVER_PROJECT_PATH "
        "(directory containing mathprover.toml and lakefile.lean)."
    )


def load_config(project_root: Path | None = None) -> MathProverConfig:
    root = resolve_project_root(project_root)
    path = root / "mathprover.toml"
    if not path.exists():
        raise FileNotFoundError(f"Missing config: {path}")

    with path.open("rb") as f:
        raw = tomllib.load(f)

    provers: dict[str, ProverConfig] = {}
    for name, block in raw.get("provers", {}).items():
        provers[name] = ProverConfig(
            name=name,
            type=block["type"],
            command=expand_config_value(block.get("command", "")),
            model=str(block.get("model", "")),
            base_url=expand_config_value(block.get("base_url", ""))
            if block.get("base_url")
            else "",
            max_attempts=int(block.get("max_attempts", 4)),
            max_tokens=int(block.get("max_tokens", 32768)),
            correction_rounds=int(block.get("correction_rounds", 2)),
            initial_max_tokens=int(block.get("initial_max_tokens", 28000)),
            correction_max_tokens=int(block.get("correction_max_tokens", 8000)),
            temperature=float(block.get("temperature", 1.0)),
            top_p=float(block.get("top_p", 0.95)),
            poll_interval_seconds=int(block.get("poll_interval_seconds", 30)),
            max_wait_minutes=int(block.get("max_wait_minutes", 120)),
            requires_env=list(block.get("requires_env", [])),
        )

    routing_raw = raw["routing"]
    routing = RoutingConfig(
        default_leaf=routing_raw["default_leaf"],
        default_capstone=routing_raw["default_capstone"],
        default_mid=routing_raw.get("default_mid", ""),
        escalate_after_failures=int(routing_raw["escalate_after_failures"]),
        capstone_node=routing_raw["capstone_node"],
        leaves=list(routing_raw.get("leaves", [])),
        second_wave=list(routing_raw.get("second_wave", [])),
        capstone=list(routing_raw.get("capstone", [])),
    )
    resources_raw = raw.get("resources", {})
    resources = ResourceLimitsConfig(
        max_concurrent_goedel=int(resources_raw.get("max_concurrent_goedel", 1)),
        min_free_memory_gib=float(resources_raw.get("min_free_memory_gib", 12.0)),
        forbid_parallel_dispatch=bool(resources_raw.get("forbid_parallel_dispatch", True)),
    )
    return MathProverConfig(
        project_root=root,
        provers=provers,
        routing=routing,
        resources=resources,
    )
