"""Plugin discovery for pet-infra entry-point group ``pet_infra.plugins``."""
from __future__ import annotations

from collections.abc import Iterable
from importlib.metadata import entry_points

from pet_infra.registry import CONVERTERS, DATASETS, EVALUATORS, METRICS, OTA, STORAGE, TRAINERS

_PLUGIN_GROUP = "pet_infra.plugins"

_REGISTRY_MAP = {
    "trainers": TRAINERS,
    "evaluators": EVALUATORS,
    "converters": CONVERTERS,
    "metrics": METRICS,
    "datasets": DATASETS,
    "storage": STORAGE,
    "ota": OTA,
}


def discover_plugins(
    required: Iterable[str] | None = None,
) -> dict[str, list[str]]:
    """Load all entry points under ``pet_infra.plugins`` and return a registry summary.

    Each entry point is expected to be a callable with no arguments that
    registers one or more modules into the global pet-infra registries as a
    side effect (e.g. ``register_all``).

    Args:
        required: Optional iterable of entry-point *names* that must be present.
            If any name is absent a :exc:`RuntimeError` is raised before any
            loading takes place.

    Returns:
        A dict with seven keys — ``trainers``, ``evaluators``, ``converters``,
        ``metrics``, ``datasets``, ``storage``, ``ota`` — each mapping to a sorted list
        of the names currently registered in that registry.

    Raises:
        RuntimeError: If one or more *required* entry-point names are not found
            in the ``pet_infra.plugins`` group.
    """
    eps = entry_points(group=_PLUGIN_GROUP)
    ep_by_name = {ep.name: ep for ep in eps}

    if required is not None:
        required_set = set(required)
        missing = sorted(required_set - ep_by_name.keys())
        if missing:
            raise RuntimeError(
                f"Required plugin(s) not found in group {_PLUGIN_GROUP!r}: {missing}"
            )
        to_load = [ep for name, ep in ep_by_name.items() if name in required_set]
    else:
        to_load = list(ep_by_name.values())

    for ep in to_load:
        loader = ep.load()
        loader()

    return {key: sorted(reg._module_dict.keys()) for key, reg in _REGISTRY_MAP.items()}
