from datetime import datetime

from pet_schema.model_card import ModelCard

from pet_infra.experiment_logger import ExperimentLogger, NullLogger


def _card():
    return ModelCard(
        id="pet_test_train_abc12345",
        version="0.1.0",
        modality="vision",
        task="sft",
        arch="qwen2vl_2b_lora_r16_a32",
        training_recipe="recipes/smoke_tiny.yaml",
        hydra_config_sha="x" * 40,
        git_shas={},
        dataset_versions={},
        checkpoint_uri="file:///tmp/adapter",
        metrics={},
        gate_status="pending",
        trained_at=datetime.utcnow(),
        trained_by="test",
    )


def test_null_logger_is_experiment_logger():
    assert issubclass(NullLogger, ExperimentLogger)


def test_null_logger_start_returns_none():
    logger = NullLogger()
    task_id = logger.start(recipe=None, stage="train")
    assert task_id is None


def test_null_logger_all_methods_noop():
    logger = NullLogger()
    logger.start(recipe=None, stage="train")
    logger.log_metrics({"loss": 0.1}, step=1)
    logger.log_artifact("adapter", "file:///tmp/a")
    logger.log_model_card(_card())
    logger.finish("success")  # no raise
