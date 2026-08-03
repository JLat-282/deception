from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import hmac
from time import perf_counter
from typing import Collection, Iterable, Literal

from .engine import MAX_GUESSES, WORD_LENGTH, TruthEngine


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
DEFAULT_DECISION_BUDGET_MS = 100


class DeceptionEngine:
    """Choose a believable one-tile feedback lie without changing truth rules."""

    def __init__(self, truth_engine: TruthEngine) -> None:
        self.truth_engine = truth_engine
        yellow_support: list[dict[str, int]] = [
            defaultdict(int) for _ in range(WORD_LENGTH)
        ]
        for word in truth_engine.valid_guesses:
            for tile_index in range(WORD_LENGTH):
                for letter in set(
                    word[:tile_index] + word[tile_index + 1 :]
                ):
                    yellow_support[tile_index][letter] += 1
        self._yellow_support = tuple(yellow_support)

    @classmethod
    def scheduled_attempts(cls, seed: str) -> tuple[int, ...]:
        """Return one hidden row 20% of the time and two distinct rows 80%."""
        count = (
            2
            if cls._seeded_number(seed, "schedule-count:v2") % 5 != 0
            else 1
        )
        ranked_attempts = sorted(
            range(1, MAX_GUESSES + 1),
            key=lambda attempt: cls._seeded_number(
                seed, f"schedule-row:v2:{attempt}"
            ),
        )
        return tuple(sorted(ranked_attempts[:count]))

    @staticmethod
    def _seeded_number(seed: str, identity: str) -> int:
        digest = hmac.new(
            seed.encode("utf-8"),
            identity.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return int.from_bytes(digest[:8], "big")

    def _answers_consistent_with(
        self,
        history: Iterable[VisibleGuess],
        real_answer: str,
        deadline: float | None = None,
    ) -> list[str] | None:
        visible_history = tuple(history)
        consistent: list[str] = []
        for answer in self.truth_engine.answers:
            if self._budget_expired(deadline):
                return None
            if answer != real_answer and all(
                self.truth_engine.evaluate(row.guess, answer) == row.feedback
                for row in visible_history
            ):
                consistent.append(answer)
        return consistent

    @staticmethod
    def _budget_expired(deadline: float | None) -> bool:
        return deadline is not None and perf_counter() >= deadline

    def choose_feedback(
        self,
        *,
        guess: str,
        real_answer: str,
        truth_feedback: str,
        prior_history: Iterable[VisibleGuess],
        seed: str,
        excluded_tile_indexes: Collection[int] = (),
        allow_constraint_fallback: bool = True,
        time_budget_ms: int | None = DEFAULT_DECISION_BUDGET_MS,
    ) -> DeceptionDecision:
        deadline = (
            None
            if time_budget_ms is None
            else perf_counter() + max(0, time_budget_ms) / 1_000
        )
        if self._budget_expired(deadline):
            return DeceptionDecision(feedback=truth_feedback)

        visible_history = tuple(prior_history)
        pattern_counts: dict[str, int] = defaultdict(int)
        consistent_answers = self._answers_consistent_with(
            visible_history, real_answer, deadline
        )
        if consistent_answers is None:
            return DeceptionDecision(feedback=truth_feedback)
        for answer in consistent_answers:
            if self._budget_expired(deadline):
                return DeceptionDecision(feedback=truth_feedback)
            pattern_counts[self.truth_engine.evaluate(guess, answer)] += 1

        candidates: list[_Candidate] = []
        for tile_index, truth_marker in enumerate(truth_feedback):
            if self._budget_expired(deadline):
                return DeceptionDecision(feedback=truth_feedback)
            if tile_index in excluded_tile_indexes:
                continue
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
            if not allow_constraint_fallback:
                return DeceptionDecision(feedback=truth_feedback)
            return self._constraint_backed_feedback(
                guess=guess,
                truth_feedback=truth_feedback,
                prior_history=visible_history,
                seed=seed,
                excluded_tile_indexes=excluded_tile_indexes,
                deadline=deadline,
            )

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

    def _constraint_backed_feedback(
        self,
        *,
        guess: str,
        truth_feedback: str,
        prior_history: tuple[VisibleGuess, ...],
        seed: str,
        excluded_tile_indexes: Collection[int],
        deadline: float | None,
    ) -> DeceptionDecision:
        """Fabricate a safe yellow when no curated answer supports a lie."""

        previously_guessed: set[str] = set()
        for row in prior_history:
            if self._budget_expired(deadline):
                return DeceptionDecision(feedback=truth_feedback)
            previously_guessed.update(row.guess)
        visible_greens: list[set[str]] = [
            set() for _ in range(WORD_LENGTH)
        ]
        for row in prior_history:
            if self._budget_expired(deadline):
                return DeceptionDecision(feedback=truth_feedback)
            for tile_index, marker in enumerate(row.feedback):
                if marker == "G":
                    visible_greens[tile_index].add(row.guess[tile_index])
        for tile_index, marker in enumerate(truth_feedback):
            if self._budget_expired(deadline):
                return DeceptionDecision(feedback=truth_feedback)
            if marker == "G":
                visible_greens[tile_index].add(guess[tile_index])

        if any(len(letters) > 1 for letters in visible_greens):
            return DeceptionDecision(feedback=truth_feedback)

        candidates: list[_Candidate] = []
        for tile_index, truth_marker in enumerate(truth_feedback):
            if self._budget_expired(deadline):
                return DeceptionDecision(feedback=truth_feedback)
            letter = guess[tile_index]
            if (
                truth_marker != "B"
                or tile_index in excluded_tile_indexes
                or letter in previously_guessed
                or guess.count(letter) != 1
            ):
                continue
            has_possible_destination = any(
                other_index != tile_index
                and (
                    not visible_greens[other_index]
                    or letter in visible_greens[other_index]
                )
                for other_index in range(WORD_LENGTH)
            )
            if not has_possible_destination:
                continue
            mutation = (
                truth_feedback[:tile_index]
                + "Y"
                + truth_feedback[tile_index + 1 :]
            )
            candidates.append(
                _Candidate(
                    feedback=mutation,
                    tile_index=tile_index,
                    tactic="fabricate",
                    decoy_count=self._yellow_support[tile_index].get(
                        letter, 0
                    ),
                )
            )

        if not candidates:
            return DeceptionDecision(feedback=truth_feedback)

        strongest_support = max(
            candidate.decoy_count for candidate in candidates
        )
        finalists = [
            candidate
            for candidate in candidates
            if candidate.decoy_count == strongest_support
        ]
        selected = min(
            finalists,
            key=lambda candidate: self._seeded_number(
                seed,
                (
                    f"constraint-candidate:v1:{candidate.feedback}:"
                    f"{candidate.tile_index}"
                ),
            ),
        )
        return DeceptionDecision(
            feedback=selected.feedback,
            tile_index=selected.tile_index,
        )
