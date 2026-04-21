import pytest

from pet_infra.experiment_logger import NullLogger, build_experiment_logger


def test_factory_null():
    """Factory returns a NullLogger when name is 'null'."""
    logger = build_experiment_logger({"name": "null"})
    assert isinstance(logger, NullLogger)


def test_factory_unknown_raises():
    """Factory raises KeyError for an unregistered logger name."""
    with pytest.raises(KeyError, match="unknown experiment logger"):
        build_experiment_logger({"name": "mlflow_not_installed"})
