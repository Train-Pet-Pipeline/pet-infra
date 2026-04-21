# src/pet_infra/orchestrator/dag.py
"""Stage-agnostic topological sort + cycle detection for the orchestrator DAG."""
from __future__ import annotations

from dataclasses import dataclass, field


class DAGCycleError(ValueError):
    """Raised when a cycle is detected in the stage dependency graph."""


@dataclass
class DAG:
    """Ordered DAG of stages produced by :func:`build_dag`."""

    stages: list
    _order: list = field(default_factory=list)

    def topological_order(self) -> list:
        """Return stages in dependency-safe execution order."""
        return self._order


def build_dag(stages: list) -> DAG:
    """Build a DAG from a list of stage-like objects with ``.name`` and ``.depends_on``.

    Args:
        stages: Any objects exposing ``.name: str`` and ``.depends_on: list[str]``.

    Returns:
        A :class:`DAG` with a topologically sorted ``.topological_order()``.

    Raises:
        KeyError: If a dependency references a non-existent stage name.
        DAGCycleError: If the dependency graph contains a cycle.
    """
    by_name = {s.name: s for s in stages}
    for s in stages:
        for d in getattr(s, "depends_on", []):
            if d not in by_name:
                raise KeyError(f"stage {s.name!r} depends on unknown {d!r}")
    order, visiting, visited = [], set(), set()

    def visit(n: str) -> None:
        if n in visited:
            return
        if n in visiting:
            raise DAGCycleError(f"cycle at {n}")
        visiting.add(n)
        for d in getattr(by_name[n], "depends_on", []):
            visit(d)
        visiting.remove(n)
        visited.add(n)
        order.append(by_name[n])

    for s in stages:
        visit(s.name)
    return DAG(stages=stages, _order=order)
