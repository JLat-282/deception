from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import hmac
from typing import Iterable, Literal

from .engine import MAX_GUESSES, TruthEngine


FeedbackMarker = Literal["G", "Y", "B"]
Tactic = Literal["fabricate", "hide"]


@dataclass(frozen=True)
class VisibleGuess:
    guess: str
    feedback: str


@dataclass(frozen=True)
class DeceptionDecision:
    feedback: str
    tile_index: int | None = None

    @property
    def activated(self) -> bool:
        return self.tile_index is not None


@dataclass(frozen=True)
class _Candidate:
    feedback: str
    tile_index: int
    tactic: Tactic
    decoy_count: int


_MARKER_RANK: dict[str, int] = {"B": 0, "Y": 1, "G": 2}


class DeceptionEngine:
    """Choose a believable one-tile feedback lie without changing truth rules."""

    def __init__(self, truth_engine: TruthEngine) -> None:
        self.truth_engine = truth_engine

    @staticmethod
    def scheduled_attempt(seed: str) -> int:
        digest = hmac.new(
            seed.encode("utf-8"),
            b"scheduled-attempt:v1",
            hashlib.sha256,
        ).digest()
        return int.from_bytes(digest[:8], "big") % MAX_GUESSES + 1

    @staticmethod
    def _seeded_number(seed: str, identity: str) -> int:
        digest = hmac.new(
            seed.encode("utf-8"),
            identity.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return int.from_bytes(digest[:8], "big")

    def _answers_consistent_with(
        self, history: Iterable[VisibleGuess], real_answer: str
    ) -> list[str]:
        visible_history = tuple(history)
        return [
            answer
            for answer in self.truth_engine.answers
            if answer != real_answer
            and all(
                self.truth_engine.evaluate(row.guess, answer) == row.feedback
                for row in visible_history
            )
        ]

    def choose_feedback(
        self,
        *,
        guess: str,
        real_answer: str,
        truth_feedback: str,
        prior_history: Iterable[VisibleGuess],
        seed: str,
    ) -> DeceptionDecision:
        pattern_counts: dict[str, int] = defaultdict(int)
        for answer in self._answers_consistent_with(
            prior_history, real_answer
        ):
            pattern_counts[self.truth_engine.evaluate(guess, answer)] += 1

        candidates: list[_Candidate] = []
        for tile_index, truth_marker in enumerate(truth_feedback):
            for display_marker in ("G", "Y", "B"):
                if display_marker == truth_marker:
                    continue
                mutation = (
                    truth_feedback[:tile_index]
                    + display_marker
                    + truth_feedback[tile_index + 1 :]
                )
                if mutation == "GGGGG":
                    continue
                decoy_count = pattern_counts.get(mutation, 0)
                if decoy_count == 0:
                    continue
                tactic: Tactic = (
                    "fabricate"
                    if _MARKER_RANK[display_marker]
                    > _MARKER_RANK[truth_marker]
                    else "hide"
                )
                candidates.append(
                    _Candidate(
                        feedback=mutation,
                        tile_index=tile_index,
                        tactic=tactic,
                        decoy_count=decoy_count,
                    )
                )

        if not candidates:
            return DeceptionDecision(feedback=truth_feedback)

        preferred_tactic: Tactic = (
            "fabricate"
            if self._seeded_number(seed, "tactic:v1") % 2 == 0
            else "hide"
        )
        tactic_candidates = [
            candidate
            for candidate in candidates
            if candidate.tactic == preferred_tactic
        ]
        if not tactic_candidates:
            tactic_candidates = candidates

        smallest_decoy_count = min(
            candidate.decoy_count for candidate in tactic_candidates
        )
        finalists = [
            candidate
            for candidate in tactic_candidates
            if candidate.decoy_count == smallest_decoy_count
        ]
        selected = min(
            finalists,
            key=lambda candidate: self._seeded_number(
                seed,
                (
                    f"candidate:v1:{candidate.feedback}:"
                    f"{candidate.tile_index}"
                ),
            ),
        )
        return DeceptionDecision(
            feedback=selected.feedback,
            tile_index=selected.tile_index,
        )
