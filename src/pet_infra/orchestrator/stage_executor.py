# src/pet_infra/orchestrator/stage_executor.py
"""Dispatch a RecipeStage to the appropriate plugin registry and execute it."""
from __future__ import annotations

from pet_infra.registry import TRAINERS, EVALUATORS, CONVERTERS

# Maps component_registry literal (plural) to mmengine Registry object.
STAGE_REGISTRIES = {
    "trainers": TRAINERS,
    "evaluators": EVALUATORS,
    "converters": CONVERTERS,
}


def execute_stage(stage, recipe, prev_card, card_id):
    """Instantiate the plugin for ``stage`` and invoke its ``.run()`` method.

    Args:
        stage: A ``RecipeStage`` with ``.component_registry``, ``.component_type``,
               and a pre-loaded ``.config`` dict (injected by the runner).
        recipe: The ``ExperimentRecipe`` (passed through to the plugin).
        prev_card: ``ModelCard`` from the previous stage, or ``None``.
        card_id: Precomputed deterministic card ID; written back to the returned card.

    Returns:
        The ``ModelCard`` returned by the plugin, with ``.id`` set to ``card_id``.

    Raises:
        KeyError: If ``stage.component_registry`` is not one of the known registries.
    """
    registry = STAGE_REGISTRIES[stage.component_registry]
    plugin = registry.build({"type": stage.component_type, **stage.config})
    card = plugin.run(input_card=prev_card, recipe=recipe)
    card.id = card_id  # orchestrator contract: write back deterministic id
    return card
