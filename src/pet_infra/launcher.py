# src/pet_infra/launcher.py
"""Multi-axis multirun launcher with cartesian-product sweep dispatch.

Phase 3B introduced the cartesian sweep launcher (Extensibility 4/5 debt).
Phase 4 P1-D adds:

- ``ExperimentRecipe.variations`` consumption (recipe-baked sweeps; spec §1.3).
- ``link_to`` co-iteration (linked axes are zipped, not crossed; spec §2.2).
- Fail-fast guards: variations + CLI ``-m``, variations + ``hydra.sweeper.params``,
  ``link_to`` length mismatch / unknown target (spec §1.3, §3.3).
- Cartesian preflight via ``pet_infra.sweep_preflight`` (warn >16, fail >64;
  ``PET_ALLOW_LARGE_SWEEP=1`` override; spec §1.3, R6).
- ClearML per-variation tag injection (one ``variation:<axis>=<value>`` tag per
  axis, recorded in ``SweepResult.clearml_tags``; spec §1.3 final bullet).

Public surface:
    launch_multirun(
        recipe_path,
        sweep_params=None,           # legacy signature (returns list[SweepResult])
        results_root=None,           # legacy signature
        max_workers=None,
        overrides=None,              # new P1-D signature: list[str]
        output_dir=None,             # new P1-D signature alias for results_root
    )
        → list[SweepResult]   when called with sweep_params (legacy)
        → dict (with "variations": list[SweepResult] + "recipe_id") when
          called with overrides/output_dir (new P1-D path)

Each combo in the cartesian product is dispatched as an independent
ExperimentRecipe run under ``<root>/<recipe_id>/<sweep_hash>/``. Failed axes
do not block siblings; each appears with ``status='failed'``.
``sweep_summary.json`` is written to ``<root>/<recipe_id>/`` on completion.

Environment:
    PET_MULTIRUN_SYNC=1           In-process synchronous loop (used by tests so
                                  monkeypatch on _run_single works).
    PET_FORCE_CLEARML_OFFLINE=1   Force ClearML into offline mode for the
                                  per-variation tag collection codepath.
    PET_ALLOW_LARGE_SWEEP=1       Override cartesian preflight fail threshold.
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

from pet_infra.sweep_preflight import check_cartesian_size

log = logging.getLogger(__name__)


class SweepResult(TypedDict):
    """Result record for one sweep combo / variation."""

    overrides: dict[str, Any]
    card_path: Path
    status: str  # 'ok' | 'failed'
    error: str | None
    # P1-C: file:// URI of <out_dir>/resolved_config.yaml (None on failure).
    # Replay (P1-E) SHA-verifies against this dump, so it must be the
    # OmegaConf-resolved view (resolve=True).
    resolved_config_uri: str | None
    # P1-D: per-variation ClearML tags (e.g. ["variation:lr=0.001",
    # "variation:batch_size=4"]). Empty list when the recipe has no variations
    # (legacy sweep_params path) or when the dispatch came via plain Hydra
    # overrides without recipe.variations metadata.
    clearml_tags: list[str]
    # P1-D: 8-hex-char digest derived from the variation's axis-value bindings.
    # Stable across re-runs so replay can address a single variation.
    variation_id: str


def _sweep_hash(overrides: dict[str, Any]) -> str:
    """Return a stable 8-hex-char digest for an overrides dict.

    Args:
        overrides: Key-value overrides dict for one sweep combo.

    Returns:
        8-character hex string derived from SHA-256 of JSON-sorted payload.
    """
    payload = json.dumps(overrides, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()[:8]


def _variation_id(axis_values: dict[str, Any]) -> str:
    """Return a stable 8-hex-char SHA-1 digest for a variation's axis bindings.

    SHA-1 is used (per plan spec) because the digest is non-cryptographic and
    only needs collision resistance across a sweep's worth of variations.

    Args:
        axis_values: Dict mapping axis name → bound value for one variation.

    Returns:
        8-character hex string derived from SHA-1 of JSON-sorted payload.
    """
    payload = json.dumps(axis_values, sort_keys=True).encode()
    return hashlib.sha1(payload, usedforsecurity=False).hexdigest()[:8]


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
    # Lazy imports to avoid circular dependencies at module load time AND to keep
    # `pet_run` monkeypatch-able from tests (`tests/test_variations.py` patches
    # `pet_infra.launcher.pet_run` indirectly via the runner module).
    from pet_infra.compose import compose_recipe  # noqa: PLC0415
    from pet_infra.orchestrator.runner import pet_run  # noqa: PLC0415

    out_dir.mkdir(parents=True, exist_ok=True)
    # Convert dict overrides → Hydra-style list before passing to pet_run.
    override_list = [f"{k}={v}" for k, v in overrides.items()]

    # Dump the resolved config BEFORE pet_run executes so replay can verify even
    # if a downstream stage fails. compose_recipe is the same call pet_run makes
    # internally; resume-from-cache makes the duplicate work cheap.
    _, resolved_dict, _ = compose_recipe(recipe_path, overrides=override_list)
    cfg_path = (out_dir / "resolved_config.yaml").resolve()
    # resolved_dict is OmegaConf.to_container(..., resolve=True); yaml.safe_dump on
    # it == OmegaConf.to_yaml(cfg, resolve=True) modulo formatting. P1-E SHA-verifies
    # against the same canonical resolved-dict form (see recipe/compose.py).
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


def _load_raw_yaml(path: Path) -> dict[str, Any]:
    """Load a recipe YAML file as a raw dict (no Pydantic validation).

    Used to inspect non-recipe sections like ``hydra.sweeper.params`` that
    ``compose_recipe`` strips before handing to ``ExperimentRecipe``.
    """
    raw = yaml.safe_load(path.read_text())
    return raw if isinstance(raw, dict) else {}


def _has_hydra_sweeper_params(raw_yaml: dict[str, Any]) -> bool:
    """Return True if the raw YAML defines a non-empty ``hydra.sweeper.params``."""
    hydra = raw_yaml.get("hydra") or {}
    if not isinstance(hydra, dict):
        return False
    sweeper = hydra.get("sweeper") or {}
    if not isinstance(sweeper, dict):
        return False
    params = sweeper.get("params")
    return bool(params)


def _validate_link_to(variations: list[Any]) -> None:
    """Enforce the link_to fail-fast conditions from spec §1.3.

    Raises:
        ValueError: When an axis's ``link_to`` references an unknown axis name
            or links to a target whose ``values`` list has a different length.
    """
    by_name = {axis.name: axis for axis in variations}
    for axis in variations:
        if axis.link_to is None:
            continue
        target = by_name.get(axis.link_to)
        if target is None:
            raise ValueError(
                f"link_to: unknown axis {axis.link_to!r} (referenced by axis "
                f"{axis.name!r})"
            )
        if len(axis.values) != len(target.values):
            raise ValueError(
                f"link_to: length mismatch — axis {axis.name!r} has "
                f"{len(axis.values)} values but link target {target.name!r} "
                f"has {len(target.values)} values"
            )


def _compile_variation_overrides(variations: list[Any]) -> list[dict[str, Any]]:
    """Compile recipe variations into a list of per-run override dicts.

    Linked axes (``link_to`` set) are co-iterated with the target via ``zip``;
    each link group becomes one logical axis whose values are tuples of the
    co-iterated bindings. Unlinked axes form independent groups. The cartesian
    product is then taken across groups.

    Each emitted dict maps ``axis.hydra_path`` → bound value, ready to feed
    ``_run_single``.

    Returns:
        Ordered list of override dicts (cartesian count after link folding).
        Returns ``[{}]`` when the input is empty so callers can iterate uniformly.
    """
    if not variations:
        return [{}]

    by_name = {axis.name: axis for axis in variations}
    # Each axis belongs to a "link group" identified by the root of its
    # link_to chain (or its own name when unlinked / when it's a target).
    def root(name: str) -> str:
        seen: set[str] = set()
        cur = name
        while True:
            ax = by_name[cur]
            if ax.link_to is None:
                return cur
            if cur in seen:  # defensive: cycle in link_to chains
                return cur
            seen.add(cur)
            cur = ax.link_to

    groups: dict[str, list[Any]] = {}
    for axis in variations:
        groups.setdefault(root(axis.name), []).append(axis)

    # For each group, build a list of (hydra_path → value) dicts — one per
    # shared index. All axes in a group must have equal-length values (already
    # enforced by _validate_link_to for linked ones; the root has its own).
    group_runs: list[list[dict[str, Any]]] = []
    for axes in groups.values():
        n_values = len(axes[0].values)
        per_index: list[dict[str, Any]] = []
        for i in range(n_values):
            binding: dict[str, Any] = {}
            for axis in axes:
                binding[axis.hydra_path] = axis.values[i]
            per_index.append(binding)
        group_runs.append(per_index)

    compiled: list[dict[str, Any]] = []
    for combo in itertools.product(*group_runs):
        merged: dict[str, Any] = {}
        for binding in combo:
            merged.update(binding)
        compiled.append(merged)
    return compiled


def _compile_clearml_tags(
    variations: list[Any], overrides: dict[str, Any]
) -> list[str]:
    """Build per-variation ClearML tags of the form ``variation:<axis>=<value>``.

    Each axis whose ``hydra_path`` appears in ``overrides`` contributes one tag.
    Tag collection is pure: it does not read ``PET_FORCE_CLEARML_OFFLINE`` (that
    flag gates the actual ClearML upload inside the per-stage logger, not the
    tag-derivation step here).
    """
    tags: list[str] = []
    for axis in variations:
        if axis.hydra_path in overrides:
            tags.append(f"variation:{axis.name}={overrides[axis.hydra_path]}")
    return tags


def launch_multirun(
    recipe_path: str | Path,
    sweep_params: dict[str, list[Any]] | None = None,
    results_root: Path | None = None,
    max_workers: int | None = None,
    *,
    overrides: list[str] | None = None,
    output_dir: Path | None = None,
) -> list[SweepResult] | dict[str, Any]:
    """Dispatch a multi-axis sweep, either via legacy ``sweep_params`` or
    via ``ExperimentRecipe.variations`` (P1-D).

    Two call shapes are supported:

    Legacy (P3B):
        ``launch_multirun(recipe_path, sweep_params={"trainer": ["a", "b"]},
        results_root=...)`` → returns ``list[SweepResult]``. Cartesian product
        is computed over ``sweep_params``; the recipe's own ``variations``
        block is ignored.

    P1-D (recipe-baked sweeps):
        ``launch_multirun(recipe_path, output_dir=..., overrides=[...])`` →
        returns ``dict`` with ``recipe_id`` and ``variations: list[SweepResult]``.
        Cartesian product is computed over ``recipe.variations`` honoring
        ``link_to`` co-iteration. Fail-fast guards (spec §1.3) run before any
        execution; cartesian preflight (spec R6) caps the sweep size unless
        ``PET_ALLOW_LARGE_SWEEP=1`` is set.

    Args:
        recipe_path: Path to the recipe YAML file.
        sweep_params: (Legacy) Dict mapping axis name → list of values. Mutually
            exclusive with ``overrides``/``output_dir``-driven recipe.variations.
        results_root: (Legacy) Root directory for sweep output.
        max_workers: Maximum parallel workers for ProcessPoolExecutor.
        overrides: (P1-D) Hydra-style override strings forwarded to each combo.
            Presence of ``-m`` or ``+ablation.*`` together with a non-empty
            ``recipe.variations`` raises ``ValueError`` (spec §1.3).
        output_dir: (P1-D) Alias for ``results_root``; preferred name in the
            new signature.

    Returns:
        ``list[SweepResult]`` for legacy callers, or ``dict`` with
        ``{"recipe_id": str, "variations": list[SweepResult]}`` for the P1-D
        path.

    Raises:
        ValueError: On any spec §1.3 fail-fast condition (link_to mismatch /
            unknown target, variations + CLI ``-m``, variations +
            ``hydra.sweeper.params``, unknown axis stage).
        CartesianTooLargeError: When the compiled sweep size exceeds the
            preflight fail threshold without the override env var.

    Note:
        Set ``PET_MULTIRUN_SYNC=1`` to force in-process synchronous execution.
    """
    from pet_infra.compose import compose_recipe  # noqa: PLC0415

    recipe_path = Path(recipe_path)
    # output_dir is the P1-D parameter name; results_root is the legacy alias.
    root = output_dir if output_dir is not None else results_root

    # Legacy path: caller passed sweep_params explicitly. Preserve old return
    # shape (list[SweepResult]) and ignore recipe.variations.
    if sweep_params is not None:
        recipe, _, _ = compose_recipe(recipe_path)
        return _dispatch_legacy(
            recipe_path=recipe_path,
            recipe_id=recipe.recipe_id,
            sweep_params=sweep_params,
            results_root=root,
            max_workers=max_workers,
        )

    # P1-D path: drive the sweep from recipe.variations.
    # 1. Load the recipe (Pydantic validators fire here — catches axis.stage
    #    not in recipe.stages via ExperimentRecipe._cross_validate; pydantic v2
    #    ValidationError IS a ValueError subclass so test_variation_stage_unknown_fails
    #    sees a ValueError matching "stage 'X' not found").
    recipe, resolved_dict, _sha = compose_recipe(recipe_path)

    # 2. Fail-fast guards (run BEFORE any execution; spec §1.3).
    overrides = list(overrides or [])
    if recipe.variations:
        if "-m" in overrides or any(
            o.startswith("+ablation.") for o in overrides
        ):
            raise ValueError(
                "recipe.variations conflicts with CLI -m / +ablation overrides; "
                "choose one (recipe-baked sweep OR CLI multirun, not both)"
            )
        raw_yaml = _load_raw_yaml(recipe_path)
        if _has_hydra_sweeper_params(raw_yaml):
            raise ValueError(
                "recipe.variations conflicts with YAML hydra.sweeper.params; "
                "choose one (recipe-baked sweep OR Hydra sweeper, not both)"
            )
        _validate_link_to(recipe.variations)

    # 3. Compile the cartesian product of variations (link-folded).
    variation_overrides = _compile_variation_overrides(recipe.variations)

    # 4. Cartesian preflight (spec §1.3, R6).
    check_cartesian_size(len(variation_overrides))

    # 5. Dispatch.
    root = root or Path("results")
    sweep_dir = root / recipe.recipe_id
    sweep_dir.mkdir(parents=True, exist_ok=True)

    results: list[SweepResult] = []
    sync = os.environ.get("PET_MULTIRUN_SYNC") == "1"

    if sync:
        for ov in variation_overrides:
            results.append(
                _execute_one(recipe_path, ov, sweep_dir, recipe.variations)
            )
    else:
        n_workers = max_workers or min(
            len(variation_overrides) or 1, os.cpu_count() or 1
        )
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            futures = {
                pool.submit(_run_single, recipe_path, ov, sweep_dir / _sweep_hash(ov)): ov
                for ov in variation_overrides
            }
            for future in as_completed(futures):
                ov = futures[future]
                tags = _compile_clearml_tags(recipe.variations, ov)
                vid = _variation_id(ov)
                try:
                    outcome = future.result()
                    results.append(
                        SweepResult(
                            overrides=ov,
                            card_path=outcome["card_path"],
                            status="ok",
                            error=None,
                            resolved_config_uri=outcome.get("resolved_config_uri"),
                            clearml_tags=tags,
                            variation_id=vid,
                        )
                    )
                except Exception as exc:
                    log.warning("variation %s failed: %s", ov, exc)
                    results.append(
                        SweepResult(
                            overrides=ov,
                            card_path=sweep_dir / _sweep_hash(ov) / "card.json",
                            status="failed",
                            error=str(exc),
                            resolved_config_uri=None,
                            clearml_tags=tags,
                            variation_id=vid,
                        )
                    )

    summary_path = sweep_dir / "sweep_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "recipe_id": recipe.recipe_id,
                "variations": [
                    {
                        "overrides": r["overrides"],
                        "status": r["status"],
                        "card_path": str(r["card_path"]),
                        "error": r["error"],
                        "resolved_config_uri": r["resolved_config_uri"],
                        "clearml_tags": r["clearml_tags"],
                        "variation_id": r["variation_id"],
                    }
                    for r in results
                ],
            },
            indent=2,
        )
    )
    log.info(
        "variations sweep complete: %d runs, summary at %s",
        len(results),
        summary_path,
    )
    return {"recipe_id": recipe.recipe_id, "variations": results}


def _execute_one(
    recipe_path: Path,
    overrides: dict[str, Any],
    sweep_dir: Path,
    variations: list[Any],
) -> SweepResult:
    """Synchronous single-variation dispatch with ClearML tag collection."""
    out_dir = sweep_dir / _sweep_hash(overrides)
    tags = _compile_clearml_tags(variations, overrides)
    vid = _variation_id(overrides)
    try:
        outcome = _run_single(recipe_path, overrides, out_dir)
        return SweepResult(
            overrides=overrides,
            card_path=outcome["card_path"],
            status="ok",
            error=None,
            resolved_config_uri=outcome.get("resolved_config_uri"),
            clearml_tags=tags,
            variation_id=vid,
        )
    except Exception as exc:
        log.warning("variation %s failed: %s", overrides, exc)
        return SweepResult(
            overrides=overrides,
            card_path=out_dir / "card.json",
            status="failed",
            error=str(exc),
            resolved_config_uri=None,
            clearml_tags=tags,
            variation_id=vid,
        )


def _dispatch_legacy(
    recipe_path: Path,
    recipe_id: str,
    sweep_params: dict[str, list[Any]],
    results_root: Path | None,
    max_workers: int | None,
) -> list[SweepResult]:
    """Legacy P3B dispatch: cartesian over sweep_params, returns list shape.

    Preserves the pre-P1-D behavior so existing callers (and the orchestrator
    tests in tests/test_launcher_multirun.py / tests/launcher/test_resolved_config.py)
    keep working.
    """
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
                        clearml_tags=[],
                        variation_id=_variation_id(ov),
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
                        clearml_tags=[],
                        variation_id=_variation_id(ov),
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
                            clearml_tags=[],
                            variation_id=_variation_id(ov),
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
                            clearml_tags=[],
                            variation_id=_variation_id(ov),
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
