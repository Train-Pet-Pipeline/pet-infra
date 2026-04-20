from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import TYPE_CHECKING, Literal

from pet_schema import BaseSample

if TYPE_CHECKING:
    import datasets  # HuggingFace datasets — only for type hints


class BaseDataset(ABC):
    """Base class for all dataset builders."""

    @abstractmethod
    def build(self, dataset_config: dict) -> Iterable[BaseSample]:
        """Build an iterable of BaseSample from the given config.

        Args:
            dataset_config: Dataset configuration dict.

        Returns:
            Iterable of BaseSample instances.
        """
        ...

    @abstractmethod
    def to_hf_dataset(self, dataset_config: dict) -> datasets.Dataset:
        """Build a HuggingFace Dataset from the given config.

        Args:
            dataset_config: Dataset configuration dict.

        Returns:
            HuggingFace datasets.Dataset instance.
        """
        ...

    @abstractmethod
    def modality(self) -> Literal["vision", "audio", "sensor", "multimodal"]:
        """Return the data modality handled by this dataset.

        Returns:
            One of "vision", "audio", "sensor", or "multimodal".
        """
        ...
