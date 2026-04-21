# tests/orchestrator/test_dag.py
import pytest

from pet_infra.orchestrator.dag import DAGCycleError, build_dag


def _stage(name, depends_on=()):
    class S:
        pass

    s = S()
    s.name = name
    s.depends_on = list(depends_on)
    return s


def test_linear_order():
    dag = build_dag([_stage("train"), _stage("eval", ["train"])])
    assert [s.name for s in dag.topological_order()] == ["train", "eval"]


def test_diamond_order():
    stages = [
        _stage("a"),
        _stage("b", ["a"]),
        _stage("c", ["a"]),
        _stage("d", ["b", "c"]),
    ]
    order = [s.name for s in build_dag(stages).topological_order()]
    assert order.index("a") < order.index("b") < order.index("d")
    assert order.index("a") < order.index("c") < order.index("d")


def test_cycle_raises():
    with pytest.raises(DAGCycleError):
        build_dag([_stage("a", ["b"]), _stage("b", ["a"])])


def test_missing_dep_raises():
    with pytest.raises(KeyError, match="ghost"):
        build_dag([_stage("a", ["ghost"])])
