from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pet_schema import EvaluationReport, ModelCard


class BaseEvaluator(ABC):
    """Base class for all model evaluators."""

    @abstractmethod
    def evaluate(
        self,
        model_card: ModelCard,
        eval_config: dict,
        output_dir: Path,
    ) -> EvaluationReport:
        """Run evaluation and return an EvaluationReport.

        Args:
            model_card: The model to evaluate.
            eval_config: Evaluation configuration dict.
            output_dir: Directory where evaluation artifacts are written.

        Returns:
            EvaluationReport with all metric results.
        """
        ...

    @abstractmethod
    def supports(self, model_card: ModelCard) -> bool:
        """Check whether this evaluator supports the given model.

        Args:
            model_card: The model to check.

        Returns:
            True if this evaluator can evaluate the model.
        """
        ...
