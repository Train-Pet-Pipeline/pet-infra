"""pet-infra CLI entry point."""
from __future__ import annotations

import json as jsonlib
from pathlib import Path

import click


@click.group()
def main() -> None:
    """pet-infra CLI."""


_PARALLEL_LAUNCHERS = frozenset({"joblib", "ray", "submitit"})


def _check_cartesian_size_from_overrides(overrides: tuple[str, ...]) -> None:
    """Run cartesian preflight on CLI-driven multirun overrides (P1-D, spec R6).

    Inspects each override of the form ``+ablation.<axis>=[v1,v2,v3]`` (and the
    Hydra ``key=val1,val2,val3`` short form) to compute the cartesian-product
    size and delegate to ``check_cartesian_size``. Overrides that don't look
    like sweep axes (single value, no comma-separated list) contribute factor 1
    and have no effect on the size.

    Args:
        overrides: Tuple of raw Hydra-style override strings from the CLI.

    Raises:
        CartesianTooLargeError: When the product exceeds the fail threshold
            without ``PET_ALLOW_LARGE_SWEEP=1``.
    """
    from pet_infra.sweep_preflight import check_cartesian_size  # noqa: PLC0415

    total = 1
    for override in overrides:
        _key, eq, value = override.partition("=")
        if not eq:
            continue
        value = value.strip()
        # Detect Hydra sweep list syntax: bracketed [a,b,c] or bare a,b,c.
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1]
            count = len([p for p in inner.split(",") if p.strip()])
        elif "," in value:
            count = len([p for p in value.split(",") if p.strip()])
        else:
            count = 1
        if count > 1:
            total *= count
    check_cartesian_size(total)


def _check_multirun_launcher(overrides: tuple[str, ...]) -> None:
    """Raise UsageError if any override selects a parallel Hydra launcher.

    Phase 3A spec §4.5 defers parallel execution; only the ``basic`` (in-process
    sequential) launcher is permitted during multirun sweeps.

    Phase 4 P1-D additionally runs the cartesian preflight (warn >16, fail >64;
    ``PET_ALLOW_LARGE_SWEEP=1`` overrides) for CLI-driven sweeps so the same
    safety net protects both recipe.variations and ``-m`` paths.

    Args:
        overrides: Tuple of raw Hydra-style override strings from the CLI.

    Raises:
        click.UsageError: When a non-basic launcher is detected.
        CartesianTooLargeError: When the cartesian preflight fails.
    """
    for override in overrides:
        # Match patterns like "hydra/launcher=joblib" or "+hydra/launcher=ray"
        key, _, value = override.lstrip("+~").partition("=")
        if key.strip() == "hydra/launcher" and value.strip() in _PARALLEL_LAUNCHERS:
            raise click.UsageError(
                f"parallel Hydra launchers ({', '.join(sorted(_PARALLEL_LAUNCHERS))}) are "
                "deferred — Phase 3A only supports serial execution; re-run without overriding "
                "hydra/launcher or use the default basic launcher. "
                "File a ticket to request parallel sweep support."
            )
    _check_cartesian_size_from_overrides(overrides)


@main.command("run")
@click.argument("recipe_path", type=click.Path())
@click.argument("overrides", nargs=-1)
@click.option("--no-resume", is_flag=True, help="Disable resume-from-cache; re-run all stages.")
@click.option(
    "-m",
    "--multirun",
    is_flag=True,
    help="Run a sweep (serial trials only; parallel launchers are not supported in Phase 3A).",
)
def run_cmd(recipe_path: str, overrides: tuple[str, ...], no_resume: bool, multirun: bool) -> None:
    """Execute a recipe DAG with optional resume from cache."""
    from pet_infra.orchestrator.runner import GateFailedError, pet_run

    # Guard runs before path validation so that a bad launcher flag surfaces
    # a clear actionable error even when the recipe file does not yet exist.
    if multirun:
        _check_multirun_launcher(overrides)

    p = Path(recipe_path)
    if not p.exists():
        raise click.BadParameter(
            f"Path '{recipe_path}' does not exist.", param_hint="'RECIPE_PATH'"
        )

    try:
        card = pet_run(p, resume=not no_resume)
        click.secho(f"run complete: card_id={card.id}", fg="green")
    except GateFailedError as e:
        click.secho(f"GateFailedError: {e}", fg="red", err=True)
        raise SystemExit(3)


@main.command("list-plugins")
@click.option("--json", "as_json", is_flag=True, help="emit JSON")
def list_plugins(as_json: bool) -> None:
    """List all registered plugins per registry."""
    from pet_infra.plugins.discover import discover_plugins

    tree = discover_plugins()
    if as_json:
        click.echo(jsonlib.dumps(tree, indent=2))
        return
    for reg, keys in tree.items():
        click.echo(f"[{reg}]")
        for k in keys:
            click.echo(f"  - {k}")


@main.command("validate")
@click.option("--recipe", "recipe_path", default=None, type=click.Path(exists=True),
              help="Compose and preflight a recipe (exclusive with --card/--hardware).")
@click.option("--override", "overrides", multiple=True, help="Hydra-style key=value override")
@click.option("--dump-resolved", is_flag=True, help="print resolved config before preflight")
# Phase 3B: hardware validation options (exclusive with --recipe)
@click.option("--card", "card_path", default=None, type=click.Path(path_type=Path),
              help="Path to ModelCard JSON (requires --hardware + --device).")
@click.option("--hardware", default=None, type=click.Choice(["rk3576"]),
              help="Target hardware platform for validation.")
@click.option("--device", "device_id", default=None,
              help="Device identifier, e.g. rk3576-dev-01.")
@click.option("--firmware", "firmware_version", default="unknown",
              help="Firmware version string (default: unknown).")
@click.option("--dry-run", is_flag=True,
              help="Write a stub HardwareValidation without running on device.")
@click.option("--validated-by", "validated_by", default=None,
              help="Override validated_by field (must match schema regex).")
def validate_cmd(
    recipe_path: str | None,
    overrides: tuple[str, ...],
    dump_resolved: bool,
    card_path: Path | None,
    hardware: str | None,
    device_id: str | None,
    firmware_version: str,
    dry_run: bool,
    validated_by: str | None,
) -> None:
    """Validate a recipe (--recipe) or a ModelCard against hardware (--card + --hardware).

    Modes are mutually exclusive:
      --recipe <path>                 compose + preflight the recipe
      --card <path> --hardware rk3576 --device <id>  write HardwareValidation stub
    """
    # Mutual-exclusion check
    hw_mode = card_path is not None or hardware is not None
    if recipe_path and hw_mode:
        raise click.ClickException("--recipe is exclusive with --card/--hardware/--device")
    if not recipe_path and not hw_mode:
        raise click.ClickException(
            "Either --recipe or (--card + --hardware + --device) is required"
        )

    if recipe_path:
        # Existing Phase 3A recipe preflight path
        from pet_infra.plugins.discover import discover_plugins
        from pet_infra.recipe.compose import compose_recipe
        from pet_infra.recipe.preflight import PreflightError, preflight

        discover_plugins()
        try:
            recipe, resolved, sha = compose_recipe(recipe_path, list(overrides))
            if dump_resolved:
                click.echo(jsonlib.dumps(resolved, indent=2, default=str))
            preflight(recipe)
        except PreflightError as e:
            click.secho(f"PreflightError: {e}", fg="red", err=True)
            raise SystemExit(2)
        click.secho(f"preflight: OK  (sha={sha[:8]})", fg="green")
        return

    # Phase 3B hardware validation path
    if not (card_path and hardware and device_id):
        raise click.ClickException(
            "--card, --hardware, and --device are all required for hardware validation"
        )
    from pet_infra.cli_commands.validate_hardware import run_hardware_validate

    run_hardware_validate(card_path, hardware, device_id, firmware_version, dry_run, validated_by)


if __name__ == "__main__":
    main()
