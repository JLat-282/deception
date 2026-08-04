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
DecisionReason = Literal[
    "activated",
    "deadline_expired",
    "no_candidate",
    "strategy_restricted",
]


@dataclass(frozen=True)
class VisibleGuess:
    guess: str
    feedback: str


@dataclass(frozen=True)
class DeceptionDecision:
    feedback: str
    tile_indexes: tuple[int, ...] = ()
    reason: DecisionReason = "no_candidate"

    @property
    def activated(self) -> bool:
        return bool(self.tile_indexes)

    @property
    def tile_index(self) -> int | None:
        return self.tile_indexes[0] if self.tile_indexes else None


@dataclass(frozen=True)
class _Candidate:
    feedback: str
    tile_indexes: tuple[int, ...]
    tactic: Tactic
    decoy_count: int


_MARKER_RANK: dict[str, int] = {"B": 0, "Y": 1, "G": 2}
DEFAULT_DECISION_BUDGET_MS = 100


class DeceptionEngine:
    """Choose believable feedback lies without changing truth rules."""

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

    def _pattern_counts_for(
        self,
        guess: str,
        history: Iterable[VisibleGuess],
        real_answer: str,
        deadline: float | None = None,
    ) -> tuple[dict[str, int], bool]:
        visible_history = tuple(history)
        pattern_counts: dict[str, int] = defaultdict(int)
        for answer in self.truth_engine.answers:
            if self._budget_expired(deadline):
                return pattern_counts, True
            if answer != real_answer and all(
                self.truth_engine.evaluate(row.guess, answer) == row.feedback
                for row in visible_history
            ):
                pattern_counts[self.truth_engine.evaluate(guess, answer)] += 1
        return pattern_counts, self._budget_expired(deadline)

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
        max_false_tiles: int = 1,
        time_budget_ms: int | None = DEFAULT_DECISION_BUDGET_MS,
    ) -> DeceptionDecision:
        deadline = (
            None
            if time_budget_ms is None
            else perf_counter() + max(0, time_budget_ms) / 1_000
        )
        if self._budget_expired(deadline):
            return DeceptionDecision(
                feedback=truth_feedback,
                reason="deadline_expired",
            )

        visible_history = tuple(prior_history)
        pattern_counts, deadline_expired = self._pattern_counts_for(
            guess, visible_history, real_answer, deadline
        )

        candidates: list[_Candidate] = []
        target_sizes = tuple(range(min(2, max_false_tiles), 0, -1))
        for target_size in target_sizes:
            for mutation, decoy_count in pattern_counts.items():
                tile_indexes = tuple(
                    index
                    for index, markers in enumerate(zip(truth_feedback, mutation))
                    if markers[0] != markers[1]
                )
                if (
                    len(tile_indexes) != target_size
                    or mutation == "GGGGG"
                    or any(index in excluded_tile_indexes for index in tile_indexes)
                ):
                    continue
                rank_delta = sum(
                    _MARKER_RANK[mutation[index]]
                    - _MARKER_RANK[truth_feedback[index]]
                    for index in tile_indexes
                )
                candidates.append(
                    _Candidate(
                        feedback=mutation,
                        tile_indexes=tile_indexes,
                        tactic="fabricate" if rank_delta >= 0 else "hide",
                        decoy_count=decoy_count,
                    )
                )
            if candidates:
                break

        if not candidates:
            if deadline_expired:
                return DeceptionDecision(
                    feedback=truth_feedback,
                    reason="deadline_expired",
                )
            if not allow_constraint_fallback:
                return DeceptionDecision(
                    feedback=truth_feedback,
                    reason="strategy_restricted",
                )
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
                    f"{','.join(str(index) for index in candidate.tile_indexes)}"
                ),
            ),
        )
        return DeceptionDecision(
            feedback=selected.feedback,
            tile_indexes=selected.tile_indexes,
            reason="activated",
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
                return DeceptionDecision(
                    feedback=truth_feedback,
                    reason="deadline_expired",
                )
            previously_guessed.update(row.guess)
        visible_greens: list[set[str]] = [
            set() for _ in range(WORD_LENGTH)
        ]
        for row in prior_history:
            if self._budget_expired(deadline):
                return DeceptionDecision(
                    feedback=truth_feedback,
                    reason="deadline_expired",
                )
            for tile_index, marker in enumerate(row.feedback):
                if marker == "G":
                    visible_greens[tile_index].add(row.guess[tile_index])
        for tile_index, marker in enumerate(truth_feedback):
            if self._budget_expired(deadline):
                return DeceptionDecision(
                    feedback=truth_feedback,
                    reason="deadline_expired",
                )
            if marker == "G":
                visible_greens[tile_index].add(guess[tile_index])

        if any(len(letters) > 1 for letters in visible_greens):
            return DeceptionDecision(
                feedback=truth_feedback,
                reason="strategy_restricted",
            )

        candidates: list[_Candidate] = []
        for tile_index, truth_marker in enumerate(truth_feedback):
            if self._budget_expired(deadline):
                if candidates:
                    break
                return DeceptionDecision(
                    feedback=truth_feedback,
                    reason="deadline_expired",
                )
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
                    tile_indexes=(tile_index,),
                    tactic="fabricate",
                    decoy_count=self._yellow_support[tile_index].get(
                        letter, 0
                    ),
                )
            )

        if not candidates:
            return DeceptionDecision(
                feedback=truth_feedback,
                reason="no_candidate",
            )

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
                    f"{candidate.tile_indexes[0]}"
                ),
            ),
        )
        return DeceptionDecision(
            feedback=selected.feedback,
            tile_indexes=selected.tile_indexes,
            reason="activated",
        )
