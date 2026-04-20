# src/pet_infra/_register.py
from __future__ import annotations


def register_all() -> None:
    """Triggered via the `pet_infra.plugins` entry point.

    Imports every first-party plugin module so @register_module side-effects
    populate the registries before pet-infra hands control to the caller.
    """
    from pet_infra.hydra_plugins.structured import register as _register_hydra
    from pet_infra.storage import local  # noqa: F401

    _register_hydra()
