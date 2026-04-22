# src/pet_infra/launcher.py
"""Multi-axis multirun launcher with cartesian-product sweep dispatch.

Phase 3B — closes Extensibility 4/5 debt from Phase 3A.

Public surface:
    launch_multirun(recipe_path, sweep_params, results_root, max_workers)
        → list[SweepResult]

Each combo in the cartesian product of sweep_params axes is dispatched as an
independent ExperimentRecipe run under results_root/<recipe_id>/<sweep_hash>/.

Failed axes do not block siblings; each appears with status='failed'.
sweep_summary.json is written to results_root/<recipe_id>/ on completion.

Environment:
    PET_MULTIRUN_SYNC=1  Force in-process synchronous loop (used by tests so
                         monkeypatch on _run_single works without pickling).
"""
from __future__ import annotations

import hashlib
import itertools
import json
import logging
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, TypedDict

import yaml

log = logging.getLogger(__name__)


class SweepResult(TypedDict):
    """Result record for one sweep combo."""

    overrides: dict[str, Any]
    card_path: Path
    status: str  # 'ok' | 'failed'
    error: str | None
    # P1-C: file:// URI of <out_dir>/resolved_config.yaml (None on failure).
    # Replay (P1-E) SHA-verifies against this dump, so it must be the
    # OmegaConf-resolved view (resolve=True).
    resolved_config_uri: str | None


def _sweep_hash(overrides: dict[str, Any]) -> str:
    """Return a stable 8-hex-char digest for an overrides dict.

    Args:
        overrides: Key-value overrides dict for one sweep combo.

    Returns:
        8-character hex string derived from SHA-256 of JSON-sorted payload.
    """
    payload = json.dumps(overrides, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()[:8]


def _run_single(recipe_path: Path, overrides: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    """Execute one ExperimentRecipe instance with the given overrides.

    Extracted as a module-level function so tests can monkeypatch it.

    Side effect (P1-C): writes ``<out_dir>/resolved_config.yaml`` containing the
    OmegaConf-resolved view of the recipe with overrides applied. The returned
    dict carries ``resolved_config_uri`` as a ``file://`` URI to that dump so
    the replay flow (P1-E) can SHA-verify it against ``ModelCard.resolved_config_uri``.

    Args:
        recipe_path: Path to the recipe YAML file.
        overrides: Axis-override key-value pairs for this combo.
        out_dir: Output directory for this sweep combo.

    Returns:
        Dict with ``card_path``, ``status``, ``overrides``, and ``resolved_config_uri``.
    """
    # Lazy imports to avoid circular dependencies at module load time.
    from pet_infra.orchestrator.runner import pet_run  # noqa: PLC0415
    from pet_infra.recipe.compose import compose_recipe  # noqa: PLC0415

    out_dir.mkdir(parents=True, exist_ok=True)
    # Convert dict overrides → Hydra-style list before passing to pet_run.
    override_list = [f"{k}={v}" for k, v in overrides.items()]

    # Dump the resolved config BEFORE pet_run executes so replay can verify even
    # if a downstream stage fails. compose_recipe is the same call pet_run makes
    # internally; resume-from-cache makes the duplicate work cheap.
    _, resolved_dict, _ = compose_recipe(recipe_path, overrides=override_list)
    cfg_path = (out_dir / "resolved_config.yaml").resolve()
    cfg_path.write_text(yaml.safe_dump(resolved_dict, sort_keys=True))
    resolved_config_uri = f"file://{cfg_path}"

    card = pet_run(recipe_path, overrides=override_list)
    card_path = out_dir / "card.json"
    card_path.write_text(card.model_dump_json(indent=2))
    return {
        "card_path": card_path,
        "status": "ok",
        "overrides": overrides,
        "resolved_config_uri": resolved_config_uri,
    }


def launch_multirun(
    recipe_path: Path,
    sweep_params: dict[str, list[Any]],
    results_root: Path | None = None,
    max_workers: int | None = None,
) -> list[SweepResult]:
    """Dispatch a cartesian product of sweep_params as parallel recipe runs.

    Each axis combo runs as an independent ExperimentRecipe instance in its own
    output directory. Failed axes do not block siblings — they appear in the
    result list with status='failed' and error=<str(exc)>.

    A sweep_summary.json is written to results_root/<recipe_id>/ aggregating all
    run results.

    Args:
        recipe_path: Path to the recipe YAML file (passed verbatim to _run_single).
        sweep_params: Dict mapping axis name → list of values.  Cartesian product
            is computed over all axes.
        results_root: Root directory for all sweep output.  Defaults to ``results/``
            relative to cwd.
        max_workers: Maximum parallel workers for ProcessPoolExecutor.  Defaults to
            min(len(combos), cpu_count).

    Returns:
        List of SweepResult TypedDicts, one per combo.

    Note:
        Set ``PET_MULTIRUN_SYNC=1`` in the environment to force in-process
        synchronous execution (required for monkeypatch in tests).
    """
    from pet_infra.compose import compose_recipe  # noqa: PLC0415

    recipe = compose_recipe(recipe_path)
    recipe_id = recipe.recipe_id
    results_root = results_root or Path("results")
    sweep_dir = results_root / recipe_id
    sweep_dir.mkdir(parents=True, exist_ok=True)

    keys = list(sweep_params.keys())
    if keys:
        combos = list(itertools.product(*(sweep_params[k] for k in keys)))
    else:
        combos = [()]
    overrides_list = [dict(zip(keys, combo)) for combo in combos]

    results: list[SweepResult] = []

    if os.environ.get("PET_MULTIRUN_SYNC") == "1":
        # In-process synchronous loop — used by tests so monkeypatch works.
        for ov in overrides_list:
            out_dir = sweep_dir / _sweep_hash(ov)
            try:
                outcome = _run_single(recipe_path, ov, out_dir)
                results.append(
                    SweepResult(
                        overrides=ov,
                        card_path=outcome["card_path"],
                        status="ok",
                        error=None,
                        resolved_config_uri=outcome.get("resolved_config_uri"),
                    )
                )
            except Exception as exc:
                log.warning("sweep combo %s failed: %s", ov, exc)
                results.append(
                    SweepResult(
                        overrides=ov,
                        card_path=out_dir / "card.json",
                        status="failed",
                        error=str(exc),
                        resolved_config_uri=None,
                    )
                )
    else:
        n_workers = max_workers or min(len(overrides_list), os.cpu_count() or 1)
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            future_to_ov: dict[Any, tuple[dict[str, Any], Path]] = {}
            for ov in overrides_list:
                out_dir = sweep_dir / _sweep_hash(ov)
                future = pool.submit(_run_single, recipe_path, ov, out_dir)
                future_to_ov[future] = (ov, out_dir)
            for future in as_completed(future_to_ov):
                ov, out_dir = future_to_ov[future]
                try:
                    outcome = future.result()
                    results.append(
                        SweepResult(
                            overrides=ov,
                            card_path=outcome["card_path"],
                            status="ok",
                            error=None,
                            resolved_config_uri=outcome.get("resolved_config_uri"),
                        )
                    )
                except Exception as exc:
                    log.warning("sweep combo %s failed: %s", ov, exc)
                    results.append(
                        SweepResult(
                            overrides=ov,
                            card_path=out_dir / "card.json",
                            status="failed",
                            error=str(exc),
                            resolved_config_uri=None,
                        )
                    )

    summary_path = sweep_dir / "sweep_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "recipe_id": recipe_id,
                "runs": [
                    {
                        "overrides": r["overrides"],
                        "status": r["status"],
                        "card_path": str(r["card_path"]),
                        "error": r["error"],
                        "resolved_config_uri": r["resolved_config_uri"],
                    }
                    for r in results
                ],
            },
            indent=2,
        )
    )
    log.info("sweep complete: %d runs, summary at %s", len(results), summary_path)
    return results
