from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class RunState:
    completed_steps: dict[str, dict[str, Any]] = field(default_factory=dict)

    def is_completed(self, step: str) -> bool:
        return step in self.completed_steps

    def mark_completed(self, step: str, details: dict[str, Any] | None = None) -> None:
        payload = details.copy() if details else {}
        payload["completedAt"] = datetime.now(timezone.utc).isoformat()
        self.completed_steps[step] = payload

    def clear(self) -> None:
        self.completed_steps.clear()

    def to_dict(self) -> dict[str, Any]:
        return {"completedSteps": self.completed_steps}


def load_state(path: Path) -> RunState:
    if not path.exists():
        return RunState()
    raw = json.loads(path.read_text(encoding="utf-8"))
    completed = raw.get("completedSteps", {})
    if not isinstance(completed, dict):
        completed = {}
    return RunState(completed_steps=completed)


def save_state(path: Path, state: RunState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")
