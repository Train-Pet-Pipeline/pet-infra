"""Topological execution plan builder for ExperimentRecipe DAGs."""
from __future__ import annotations

import networkx as nx
from pet_schema import ExperimentRecipe


def build_execution_plan(recipe: ExperimentRecipe) -> list[str]:
    """Return stage names in a valid topological execution order.

    Cycles are caught upstream by ``ExperimentRecipe``'s model validator,
    so by the time a recipe instance exists, its DAG is acyclic.

    Args:
        recipe: A validated ``ExperimentRecipe`` instance.

    Returns:
        A list of stage name strings ordered so that every stage appears
        after all of its dependencies.
    """
    g: nx.DiGraph = recipe.to_dag()
    return list(nx.topological_sort(g))
