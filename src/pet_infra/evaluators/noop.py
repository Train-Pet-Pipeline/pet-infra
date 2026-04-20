"""No-op evaluator — used by Phase 2 smoke recipe to exercise preflight/DAG
without running real evaluation logic. Phase 3 replaces with real evaluators.
"""
from __future__ import annotations

from pet_infra.registry import EVALUATORS


@EVALUATORS.register_module(name="pet_infra.noop_evaluator", force=True)
class NoopEvaluator:
    """Returns an empty report; ignores model and dataset."""

    def evaluate(self, model, dataset) -> dict:
        return {"report_type": "noop", "metrics": {}}
