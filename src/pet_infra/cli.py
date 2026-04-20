"""pet-infra CLI entry point."""
from __future__ import annotations

import json as jsonlib

import click


@click.group()
def main() -> None:
    """pet-infra CLI."""


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
