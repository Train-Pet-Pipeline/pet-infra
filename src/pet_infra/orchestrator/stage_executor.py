# src/pet_infra/orchestrator/stage_executor.py
"""Dispatch a RecipeStage to the appropriate stage runner and execute it."""
from __future__ import annotations

from typing import Any

from pet_infra.orchestrator.hooks import STAGE_RUNNERS


def execute_stage(stage: Any, recipe: Any, prev_card: Any, card_id: str) -> Any:
    """Instantiate the plugin for ``stage`` and invoke its ``.run()`` method.

    Delegates to the appropriate runner in ``STAGE_RUNNERS`` keyed on
    ``stage.component_registry``.

    Args:
        stage: A ``RecipeStage`` (or adapter) with ``.component_registry``,
               ``.component_type``, and optionally a pre-loaded ``.config`` dict.
        recipe: The ``ExperimentRecipe`` (passed through to the plugin).
        prev_card: ``ModelCard`` from the previous stage, or ``None``.
        card_id: Precomputed deterministic card ID; written back to the returned card.

    Returns:
        The ``ModelCard`` returned by the plugin, with ``.id`` set to ``card_id``.

    Raises:
        KeyError: If ``stage.component_registry`` is not one of the known registries.
        GateFailedError: If ``stage.component_registry == 'ota'`` and
            ``prev_card.gate_status != 'passed'``.
    """
    runner = STAGE_RUNNERS[stage.component_registry]
    card = runner.run(stage, prev_card, recipe)
    card.id = card_id  # orchestrator contract: write back deterministic id
    return card
