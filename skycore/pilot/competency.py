"""Pilot competency self-check before flight.

A short configurable checklist that asks the pilot to attest that they've
done the things they should have done. Not a substitute for proper
certification. Default questions cover NOTAMs, weather, battery, observers,
emergency procedures, and local rules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class CompetencyQuestion:
    key: str
    text: str
    required: bool = True
    detail: str = ""


@dataclass
class CompetencyResult:
    answers: dict[str, bool] = field(default_factory=dict)

    def passed(self, questions: list[CompetencyQuestion]) -> bool:
        for q in questions:
            if q.required and not self.answers.get(q.key, False):
                return False
        return True

    def missing(self, questions: list[CompetencyQuestion]) -> list[str]:
        return [q.key for q in questions if q.required and not self.answers.get(q.key, False)]


DEFAULT_QUESTIONS: list[CompetencyQuestion] = [
    CompetencyQuestion(
        key="notams",
        text="Have you checked NOTAMs for the operating area?",
        detail="https://www.faa.gov/air_traffic/flight_info/aeronav/notams/",
    ),
    CompetencyQuestion(
        key="weather",
        text="Have you checked current and forecast weather?",
        detail="Wind, gust, visibility, precipitation",
    ),
    CompetencyQuestion(
        key="battery",
        text="Is the battery fresh, balanced, and within service limits?",
        detail="Cells within 0.05 V; not bloated; recent storage charge cycled",
    ),
    CompetencyQuestion(
        key="firmware",
        text="Is the drone firmware on a known-good version?",
    ),
    CompetencyQuestion(
        key="airspace",
        text="Have you confirmed you're in legal airspace for this flight?",
        detail="NFZ, controlled airspace, distance to airports",
    ),
    CompetencyQuestion(
        key="vlos",
        text="Will you maintain visual line of sight throughout?",
    ),
    CompetencyQuestion(
        key="observers",
        text="If required, are observers / spotters briefed and in position?",
    ),
    CompetencyQuestion(
        key="emergency_plan",
        text="Do you have an emergency landing area identified?",
    ),
    CompetencyQuestion(
        key="props",
        text="Have you inspected propellers for damage and seated them firmly?",
    ),
    CompetencyQuestion(
        key="compass",
        text="Has the compass calibration been verified for this location?",
    ),
]


class CompetencyCheck:
    """Interactive or programmatic pilot self-check."""

    def __init__(self, questions: Optional[list[CompetencyQuestion]] = None):
        self.questions = questions or list(DEFAULT_QUESTIONS)

    def add(self, q: CompetencyQuestion) -> None:
        self.questions.append(q)

    def run_interactive(self, ask: Optional[Callable[[CompetencyQuestion], bool]] = None) -> CompetencyResult:
        """Run synchronously via console (default) or via a custom asker."""
        if ask is None:
            def ask(q: CompetencyQuestion) -> bool:  # type: ignore
                ans = input(f"  [?] {q.text}\n      ({q.detail})\n      yes/no: ").strip().lower()
                return ans in {"y", "yes", "true", "1"}

        result = CompetencyResult()
        for q in self.questions:
            result.answers[q.key] = ask(q)
        return result

    def from_dict(self, answers: dict) -> CompetencyResult:
        """Build a result from a {key: bool} dict (e.g. submitted from web UI)."""
        return CompetencyResult(answers={q.key: bool(answers.get(q.key, False)) for q in self.questions})
