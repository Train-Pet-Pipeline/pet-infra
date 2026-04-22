# src/pet_infra/_register.py
from __future__ import annotations


def register_all() -> None:
    """Triggered via the `pet_infra.plugins` entry point.

    Imports every first-party plugin module so @register_module side-effects
    populate the registries before pet-infra hands control to the caller.

    Guard against duplicate registration: if a module's key is already present
    in the target registry (e.g. because another test imported the module
    directly), skip re-importing to avoid KeyError from mmengine's Registry.
    """
    from pet_infra.hydra_plugins.structured import register as _register_hydra
    from pet_infra.registry import EVALUATORS, STORAGE

    if "local" not in STORAGE.module_dict:
        from pet_infra.storage import local  # noqa: F401

    if "s3" not in STORAGE.module_dict:
        from pet_infra.storage import s3  # noqa: F401

    if "pet_infra.noop_evaluator" not in EVALUATORS.module_dict:
        from pet_infra.evaluators import noop  # noqa: F401

    _register_hydra()
