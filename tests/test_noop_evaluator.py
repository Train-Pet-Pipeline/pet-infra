"""Tests for pet_infra.noop_evaluator — Phase 2 smoke recipe dependency."""
from __future__ import annotations

from pet_infra import _register
from pet_infra.registry import EVALUATORS


def test_noop_evaluator_registered() -> None:
    """register_all() registers pet_infra.noop_evaluator in EVALUATORS."""
    _register.register_all()
    cls = EVALUATORS.module_dict.get("pet_infra.noop_evaluator")
    assert cls is not None, "noop_evaluator should be in EVALUATORS after register_all"


def test_noop_evaluator_evaluate_returns_noop_report() -> None:
    """evaluate() returns a dict with report_type='noop' and empty metrics."""
    _register.register_all()
    cls = EVALUATORS.module_dict["pet_infra.noop_evaluator"]
    inst = cls()
    out = inst.evaluate(model=None, dataset=[])
    assert isinstance(out, dict)
    assert out.get("report_type") == "noop"
    assert out.get("metrics") == {}
