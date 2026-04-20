from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pet_schema import EdgeFormat, ModelCard


class BaseConverter(ABC):
    """Base class for all model converters (RKLLM, RKNN, ONNX, GGUF, etc.)."""

    @abstractmethod
    def convert(
        self,
        source_card: ModelCard,
        convert_config: dict,
        calibration_data_uri: str | None,
        output_dir: Path,
    ) -> ModelCard:
        """Convert a model to the target edge format.

        Args:
            source_card: ModelCard describing the source model.
            convert_config: Conversion configuration dict.
            calibration_data_uri: URI of calibration data for quantization, or None.
            output_dir: Directory where converted artifacts are written.

        Returns:
            ModelCard describing the converted model.
        """
        ...

    @abstractmethod
    def target_format(self) -> EdgeFormat:
        """Return the EdgeFormat this converter targets.

        Returns:
            The EdgeFormat enum value this converter produces.
        """
        ...
