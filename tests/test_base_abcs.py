from __future__ import annotations

from collections.abc import Iterator

import pytest
from pet_schema import (
    EdgeFormat,
)

from pet_infra.base import (
    BaseConverter,
    BaseDataset,
    BaseEvaluator,
    BaseMetric,
    BaseStorage,
    BaseTrainer,
)


def test_base_trainer_has_three_abstracts():
    assert BaseTrainer.__abstractmethods__ == {"fit", "validate_config", "estimate_resources"}


def test_base_trainer_bare_instantiation_raises():
    with pytest.raises(TypeError):
        BaseTrainer()  # type: ignore[abstract]


def test_base_trainer_concrete_subclass_instantiates():
    class Fake(BaseTrainer):
        def fit(self, recipe, resolved_config, output_dir):  # type: ignore[override]
            return None  # type: ignore[return-value]
        def validate_config(self, resolved_config):  # type: ignore[override]
            return None
        def estimate_resources(self, resolved_config):  # type: ignore[override]
            return None  # type: ignore[return-value]

    assert isinstance(Fake(), BaseTrainer)


def test_base_evaluator_has_two_abstracts():
    assert BaseEvaluator.__abstractmethods__ == {"evaluate", "supports"}


def test_base_evaluator_bare_instantiation_raises():
    with pytest.raises(TypeError):
        BaseEvaluator()  # type: ignore[abstract]


def test_base_evaluator_concrete_subclass_instantiates():
    class Fake(BaseEvaluator):
        def evaluate(self, model_card, eval_config, output_dir):  # type: ignore[override]
            return None  # type: ignore[return-value]
        def supports(self, model_card):  # type: ignore[override]
            return True

    assert isinstance(Fake(), BaseEvaluator)


def test_base_converter_has_two_abstracts():
    assert BaseConverter.__abstractmethods__ == {"convert", "target_format"}


def test_base_converter_bare_instantiation_raises():
    with pytest.raises(TypeError):
        BaseConverter()  # type: ignore[abstract]


def test_base_converter_target_format_returns_edgeformat():
    class Fake(BaseConverter):
        def convert(self, source_card, convert_config, calibration_data_uri, output_dir):  # type: ignore[override]
            return None  # type: ignore[return-value]
        def target_format(self) -> EdgeFormat:
            return EdgeFormat.RKLLM

    assert Fake().target_format() is EdgeFormat.RKLLM


def test_base_metric_has_one_abstract_and_two_classvars():
    assert BaseMetric.__abstractmethods__ == {"compute"}
    # ClassVars declared (not instance fields)
    assert "name" in BaseMetric.__annotations__
    assert "higher_is_better" in BaseMetric.__annotations__


def test_base_metric_bare_instantiation_raises():
    with pytest.raises(TypeError):
        BaseMetric()  # type: ignore[abstract]


def test_base_metric_concrete_subclass_instantiates():
    class Fake(BaseMetric):
        name = "fake"
        higher_is_better = True

        def compute(self, predictions, references, **kwargs):  # type: ignore[override]
            return None  # type: ignore[return-value]

    assert isinstance(Fake(), BaseMetric)
    assert Fake.name == "fake"
    assert Fake.higher_is_better is True


def test_base_dataset_has_three_abstracts():
    assert BaseDataset.__abstractmethods__ == {"build", "to_hf_dataset", "modality"}


def test_base_dataset_bare_instantiation_raises():
    with pytest.raises(TypeError):
        BaseDataset()  # type: ignore[abstract]


def test_base_dataset_modality_literal():
    class Fake(BaseDataset):
        def build(self, dataset_config):  # type: ignore[override]
            return iter([])
        def to_hf_dataset(self, dataset_config):  # type: ignore[override]
            return None  # type: ignore[return-value]
        def modality(self):  # type: ignore[override]
            return "vision"

    assert Fake().modality() == "vision"


def test_base_storage_has_four_abstracts():
    assert BaseStorage.__abstractmethods__ == {"read", "write", "exists", "iter_prefix"}


def test_base_storage_bare_instantiation_raises():
    with pytest.raises(TypeError):
        BaseStorage()  # type: ignore[abstract]


def test_base_storage_concrete_subclass_instantiates():
    class Fake(BaseStorage):
        def read(self, uri: str) -> bytes:
            return b""
        def write(self, uri: str, data: bytes) -> str:
            return uri
        def exists(self, uri: str) -> bool:
            return False
        def iter_prefix(self, prefix: str) -> Iterator[str]:
            return iter([])

    assert isinstance(Fake(), BaseStorage)
