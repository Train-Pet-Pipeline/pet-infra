# src/pet_infra/orchestrator/runner.py
"""Serial DAG runner with resume-from-cache and ExperimentLogger integration (§4.5)."""
from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace

import yaml
from pet_schema.model_card import ModelCard

from pet_infra.experiment_logger.factory import build_experiment_logger
from pet_infra.recipe.card_id import precompute_card_id
from pet_infra.recipe.compose import compose_recipe

from .cache import StageCache
from .dag import build_dag
from .hash import hash_stage_config
from .hooks import GateFailedError  # noqa: F401 — re-exported for callers
from .stage_executor import execute_stage

log = logging.getLogger(__name__)


def pet_run(
    recipe_path: Path,
    resume: bool = True,
    cache_root: Path | None = None,
    overrides: Sequence[str] = (),
) -> ModelCard:
    """Execute a recipe's stage DAG serially with resume-from-cache.

    Algorithm (§4.5):
    1. Compose YAML → ExperimentRecipe via compose_recipe().
    2. Build experiment logger from resolved config.
    3. Build topological DAG over recipe.stages.
    4. Walk DAG: for each stage compute config_sha → card_id.
       - If resume and cache hit: restore card from cache and continue.
       - Else: execute plugin, assert card.id == card_id, save to cache.
    5. On evaluator stage: check gate_status. If "failed" → raise GateFailedError.

    Args:
        recipe_path: Path to the recipe YAML file.
        resume: If True, skip stages whose card is already in cache.
        cache_root: Root directory for stage cache. Defaults to ``~/.pet-cache``.
        overrides: Hydra-style list of "key.path=value" strings applied to the
            recipe before validation. Used by the multirun launcher to apply
            sweep combo overrides.

    Returns:
        The last stage's ModelCard.

    Raises:
        GateFailedError: When an evaluator stage returns gate_status="failed".
        AssertionError: When a plugin returns a card with a mismatched id.
    """
    # 1. Compose YAML → ExperimentRecipe
    recipe_path = Path(recipe_path).resolve()
    recipe, resolved_dict, _config_sha = compose_recipe(recipe_path, overrides=overrides)

    # 2. Logger (key is "name" not "type" — factory.py convention)
    logger_cfg = resolved_dict.get("experiment_logger", {"name": "null"})
    experiment_logger = build_experiment_logger(logger_cfg)

    # 3. DAG + cache
    dag = build_dag(recipe.stages)
    cache = StageCache(root=cache_root or Path.home() / ".pet-cache")

    # 4. Walk DAG
    prev_card: ModelCard | None = None
    last_card: ModelCard | None = None

    for stage in dag.topological_order():
        # Load stage config from filesystem path (§ adaptation 4)
        _raw = yaml.safe_load(Path(stage.config_path).read_text())
        stage_config_dict = _raw if _raw is not None else {}
        stage_adapter = SimpleNamespace(config=stage_config_dict)

        config_sha = hash_stage_config(stage_adapter, prev_card)
        card_id = precompute_card_id(recipe.recipe_id, stage.name, config_sha)

        if resume and cache.has(card_id):
            cached = cache.load(card_id)
            if cached is not None:
                log.info("cache hit: %s", card_id)
                prev_card = ModelCard.model_validate(cached)
                last_card = prev_card
                continue
            # corrupt cache → fall through to re-execute

        task_id = experiment_logger.start(recipe, stage.name)
        try:
            # Attach pre-loaded config dict as .config so stage_executor can use it
            stage_with_config = _StageWithConfig(stage, stage_config_dict)
            card = execute_stage(stage_with_config, recipe, prev_card, card_id)
            assert card.id == card_id, (
                f"plugin {stage.component_type!r} must return card with id={card_id!r} "
                f"(got {card.id!r})"
            )
        except Exception:
            experiment_logger.finish("failed")
            raise

        if task_id is not None:
            card.clearml_task_id = task_id
        experiment_logger.log_model_card(card)
        cache.save(card_id, card.model_dump(mode="json"))
        experiment_logger.finish("success")

        # 5. Gate short-circuit (§6.5)
        if stage.component_registry == "evaluators" and card.gate_status == "failed":
            raise GateFailedError(
                f"evaluator stage {stage.name!r} returned gate_status='failed'; "
                "stopping DAG walk."
            )

        prev_card = card
        last_card = card

    assert last_card is not None, "recipe has no stages"
    return last_card


class _StageWithConfig:
    """Thin adapter that overlays a pre-loaded config dict onto a real RecipeStage.

    This allows stage_executor.execute_stage to consume ``stage.component_registry``,
    ``stage.component_type``, and ``stage.config`` without modifying RecipeStage.
    """

    __slots__ = ("_stage", "config")

    def __init__(self, stage, config: dict) -> None:
        object.__setattr__(self, "_stage", stage)
        object.__setattr__(self, "config", config)

    def __getattr__(self, name: str):
        return getattr(object.__getattribute__(self, "_stage"), name)
