# tests/test_smoke_recipe.py
import pytest
from click.testing import CliRunner

from pet_infra.base import BaseTrainer
from pet_infra.cli import main
from pet_infra.registry import TRAINERS


@pytest.fixture
def fake_trainer_registered():
    @TRAINERS.register_module(name="pet_infra.fake_trainer", force=True)
    class _FakeTrainer(BaseTrainer):
        def fit(self, recipe, resolved_config, output_dir):
            return None  # type: ignore[return-value]

        def validate_config(self, resolved_config):
            return None

        def estimate_resources(self, resolved_config):
            return None  # type: ignore[return-value]

    yield
    TRAINERS._module_dict.pop("pet_infra.fake_trainer", None)


def test_smoke_recipe_preflight_passes(fake_trainer_registered):
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["validate", "--recipe", "recipes/smoke_foundation.yaml"],
    )
    assert result.exit_code == 0, result.output
    assert "preflight: OK" in result.output
