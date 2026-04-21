from __future__ import annotations

import logging
from typing import Literal

from clearml import Task
from pet_schema.model_card import ModelCard
from pet_schema.recipe import ExperimentRecipe
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import ExperimentLogger
from .null_logger import NullLogger

logger = logging.getLogger(__name__)

Mode = Literal["offline", "saas", "self_hosted"]
OnUnavailable = Literal["strict", "fallback_null", "retry"]

_RETRY_WAIT = wait_exponential(multiplier=1, min=1, max=16)


class ClearMLLogger(ExperimentLogger):
    """ClearML-backed experiment logger with offline/saas/self_hosted modes."""

    def __init__(
        self,
        mode: Mode = "offline",
        api_host: str = "",
        on_unavailable: OnUnavailable = "strict",
        project: str = "pet-pipeline",
    ):
        """Initialize ClearMLLogger.

        Args:
            mode: Connection mode — ``offline``, ``saas``, or ``self_hosted``.
            api_host: Informational server URL for non-offline modes.
            on_unavailable: Policy when ClearML is unreachable —
                ``strict`` (re-raise), ``fallback_null`` (switch to NullLogger),
                or ``retry`` (retry up to 3 times via tenacity).
            project: ClearML project name.
        """
        self.mode = mode
        self.api_host = api_host
        self.on_unavailable = on_unavailable
        self.project = project
        self._task = None

    def _init_task(self, task_name: str):
        """Initialize a ClearML Task, applying retry policy when configured."""
        if self.on_unavailable == "retry":
            @retry(
                stop=stop_after_attempt(3),
                wait=_RETRY_WAIT,
                reraise=True,
            )
            def _inner():
                return Task.init(project_name=self.project, task_name=task_name)

            return _inner()
        return Task.init(project_name=self.project, task_name=task_name)

    def start(self, recipe: ExperimentRecipe | None, stage: str) -> str | None:
        """Start a ClearML task. Returns task_id or None on fallback."""
        if self.mode == "offline":
            Task.set_offline(True)
        task_name = f"{getattr(recipe, 'id', 'unnamed')}_{stage}"
        try:
            self._task = self._init_task(task_name)
            return str(self._task.id)
        except Exception as e:
            return self._handle_unavailable(e)

    def _handle_unavailable(self, e: Exception) -> str | None:
        """Handle ClearML unavailability according to the configured policy."""
        if self.on_unavailable == "strict":
            raise
        if self.on_unavailable == "fallback_null":
            logger.warning("ClearML unavailable, falling back to NullLogger: %s", e)
            self._task = None
            return None
        if self.on_unavailable == "retry":
            # retry is applied at call site in _init_task; if we land here,
            # all retries exhausted — treat as strict for correctness.
            raise
        return None

    def log_metrics(self, metrics: dict[str, float], step: int | None = None) -> None:
        """Log scalar metrics to ClearML."""
        if not self._task:
            return
        for k, v in metrics.items():
            self._task.get_logger().report_scalar(title=k, series=k, value=v, iteration=step or 0)

    def log_artifact(self, name: str, uri: str) -> None:
        """Upload an artifact to ClearML by URI."""
        if not self._task:
            return
        self._task.upload_artifact(name=name, artifact_object=uri)

    def log_model_card(self, card: ModelCard) -> None:
        """Attach a ModelCard to the ClearML task as configuration."""
        if not self._task:
            return
        self._task.connect_configuration(card.model_dump(mode="json"), name="model_card")

    def finish(self, status: Literal["success", "failed"]) -> None:
        """Close the ClearML task."""
        if not self._task:
            return
        self._task.close()
        self._task = None


def _with_fallback(clearml_logger: ClearMLLogger) -> ExperimentLogger:
    """Probe ClearML; if start() fails and policy is fallback_null, swap to NullLogger."""
    try:
        clearml_logger.start(recipe=None, stage="_probe")
    except Exception:
        if clearml_logger.on_unavailable == "fallback_null":
            return NullLogger()
        return clearml_logger
    return clearml_logger
