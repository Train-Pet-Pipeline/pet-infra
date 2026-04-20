from pet_infra.registry import (
    CONVERTERS,
    DATASETS,
    EVALUATORS,
    METRICS,
    STORAGE,
    TRAINERS,
)


def test_six_registries_with_unique_names():
    regs = [TRAINERS, EVALUATORS, CONVERTERS, METRICS, DATASETS, STORAGE]
    names = {r.name for r in regs}
    assert names == {"trainer", "evaluator", "converter", "metric", "dataset", "storage"}


def test_registry_decorator_works():
    @TRAINERS.register_module(name="__fake_trainer__")
    class FakeTrainer:
        pass

    try:
        assert TRAINERS.get("__fake_trainer__") is FakeTrainer
    finally:
        TRAINERS._module_dict.pop("__fake_trainer__", None)
