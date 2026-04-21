"""pet-infra CLI entry point."""
from __future__ import annotations

import json as jsonlib
from pathlib import Path

import click


@click.group()
def main() -> None:
    """pet-infra CLI."""


@main.command("run")
@click.argument("recipe_path", type=click.Path(exists=True))
@click.option("--no-resume", is_flag=True, help="Disable resume-from-cache; re-run all stages.")
@click.option("-m", "--multirun", is_flag=True, hidden=True)  # delegate to Hydra in future
def run_cmd(recipe_path: str, no_resume: bool, multirun: bool) -> None:
    """Execute a recipe DAG with optional resume from cache."""
    from pet_infra.orchestrator.runner import pet_run, GateFailedError

    try:
        card = pet_run(Path(recipe_path), resume=not no_resume)
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
