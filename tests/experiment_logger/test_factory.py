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


def test_factory_wraps_plugin_load_failure(monkeypatch):
    """A broken entry-point should surface with plugin name + entry-point value."""
    from pet_infra.experiment_logger import factory as factory_mod

    class _BrokenEP:
        name = "broken"
        value = "pkg.missing:Cls"

        def load(self):
            raise ImportError("simulated broken plugin")

    def _fake_eps(*, group):
        assert group == "pet_infra.experiment_loggers"
        return [_BrokenEP()]

    monkeypatch.setattr(factory_mod, "entry_points", _fake_eps)
    with pytest.raises(RuntimeError, match="failed to load experiment logger plugin 'broken'"):
        factory_mod.build_experiment_logger({"name": "broken"})
