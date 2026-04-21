from mmengine.registry import Registry

TRAINERS = Registry("trainer", scope="pet_infra")
EVALUATORS = Registry("evaluator", scope="pet_infra")
CONVERTERS = Registry("converter", scope="pet_infra")
METRICS = Registry("metric", scope="pet_infra")
DATASETS = Registry("dataset", scope="pet_infra")
STORAGE = Registry("storage", scope="pet_infra")
OTA = Registry("ota", scope="pet_infra")

__all__ = ["TRAINERS", "EVALUATORS", "CONVERTERS", "METRICS", "DATASETS", "STORAGE", "OTA"]
