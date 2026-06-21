from __future__ import annotations

from collections import Counter

from sampark.core.models import SamparkRun


class LearningStore:
    def __init__(self) -> None:
        self._runs: list[SamparkRun] = []

    def record(self, run: SamparkRun) -> dict[str, object]:
        self._runs.append(run)
        completed = sum(1 for step in run.steps if step.status != "blocked")
        blocked = sum(1 for step in run.steps if step.status == "blocked")
        language_counts = Counter(item.customer.language for item in self._runs)
        return {
            "runs_recorded": len(self._runs),
            "completed_or_ready_steps": completed,
            "blocked_steps": blocked,
            "language_mix": dict(language_counts),
            "learning_signal": "Update next-best-action timing, language, and channel from outcome feedback.",
        }

