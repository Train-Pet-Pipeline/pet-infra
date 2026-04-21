"""pet-infra CLI entry point."""
from __future__ import annotations

import json as jsonlib
from pathlib import Path

import click


@click.group()
def main() -> None:
    """pet-infra CLI."""


_PARALLEL_LAUNCHERS = frozenset({"joblib", "ray", "submitit"})


def _check_multirun_launcher(overrides: tuple[str, ...]) -> None:
    """Raise UsageError if any override selects a parallel Hydra launcher.

    Phase 3A spec §4.5 defers parallel execution; only the ``basic`` (in-process
    sequential) launcher is permitted during multirun sweeps.

    Args:
        overrides: Tuple of raw Hydra-style override strings from the CLI.

    Raises:
        click.UsageError: When a non-basic launcher is detected.
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
@click.option("--recipe", "recipe_path", required=True, type=click.Path(exists=True))
@click.option("--override", "overrides", multiple=True, help="Hydra-style key=value override")
@click.option("--dump-resolved", is_flag=True, help="print resolved config before preflight")
def validate_cmd(recipe_path: str, overrides: tuple[str, ...], dump_resolved: bool) -> None:
    """Compose and preflight a recipe."""
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


if __name__ == "__main__":
    main()
