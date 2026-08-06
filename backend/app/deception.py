from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
import hashlib
import hmac
from itertools import combinations
import math
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
DecisionStrategy = Literal[
    "belief_world",
    "constraint_backed",
    "exact_decoy",
    "truth",
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
    strategy: DecisionStrategy = "truth"
    score: float = 0.0
    credible_worlds: int = 0
    exact_decoys: int = 0
    thread_letter: str | None = None
    decision_ms: float = 0.0
    deadline_hit: bool = False

    @property
    def activated(self) -> bool:
        return bool(self.tile_indexes)

    @property
    def tile_index(self) -> int | None:
        return self.tile_indexes[0] if self.tile_indexes else None

    def diagnostics(self) -> dict[str, int | float | str | bool | None]:
        """Return private, persistence-safe decision diagnostics."""

        return {
            "strategy": self.strategy,
            "score": round(self.score, 4),
            "credibleWorlds": self.credible_worlds,
            "exactDecoys": self.exact_decoys,
            "threadLetter": self.thread_letter,
            "decisionMs": round(self.decision_ms, 3),
            "deadlineHit": self.deadline_hit,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class _Candidate:
    feedback: str
    tile_indexes: tuple[int, ...]
    tactic: Tactic
    credible_worlds: int
    credible_weight: float
    exact_decoys: int
    score: float
    thread_letter: str | None = None


_MARKER_RANK: dict[str, int] = {"B": 0, "Y": 1, "G": 2}
DEFAULT_DECISION_BUDGET_MS = 40
_PATTERN_CACHE_LIMIT = 64


class DeceptionEngine:
    """Choose believable feedback lies without changing truth rules.

    A credible world is an answer that can explain the displayed board when a
    small number of earlier tiles are allowed to have lied. This matches what a
    player actually knows. It avoids the old failure mode where a strong first
    guess forced truth merely because only one exact dictionary decoy remained.
    """

    def __init__(self, truth_engine: TruthEngine) -> None:
        self.truth_engine = truth_engine
        yellow_support: list[dict[str, int]] = [
            defaultdict(int) for _ in range(WORD_LENGTH)
        ]
        answer_letter_support: dict[str, int] = defaultdict(int)
        answer_position_support: list[dict[str, int]] = [
            defaultdict(int) for _ in range(WORD_LENGTH)
        ]
        for word in truth_engine.valid_guesses:
            for tile_index in range(WORD_LENGTH):
                for letter in set(word[:tile_index] + word[tile_index + 1 :]):
                    yellow_support[tile_index][letter] += 1
        for answer in truth_engine.answers:
            for letter in set(answer):
                answer_letter_support[letter] += 1
            for tile_index, letter in enumerate(answer):
                answer_position_support[tile_index][letter] += 1
        self._yellow_support = tuple(yellow_support)
        self._answer_letter_support = answer_letter_support
        self._answer_position_support = tuple(answer_position_support)
        self._pattern_cache: dict[str, tuple[str, ...]] = {}

    @classmethod
    def scheduled_attempts(cls, seed: str) -> tuple[int, ...]:
        """Legacy one-or-two-row schedule retained for old stored games."""

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

    def _patterns_for_guess(
        self, guess: str, deadline: float | None = None
    ) -> tuple[tuple[str, ...], bool]:
        cached = self._pattern_cache.get(guess)
        if cached is not None:
            return cached, True
        patterns: list[str] = []
        for answer in self.truth_engine.answers:
            if self._budget_expired(deadline):
                break
            patterns.append(self.truth_engine.evaluate(guess, answer))
        complete = len(patterns) == len(self.truth_engine.answers)
        result = tuple(patterns)
        if complete:
            if len(self._pattern_cache) >= _PATTERN_CACHE_LIMIT:
                self._pattern_cache.pop(next(iter(self._pattern_cache)))
            self._pattern_cache[guess] = result
        return result, complete

    def _pattern_counts_for(
        self,
        guess: str,
        history: Iterable[VisibleGuess],
        real_answer: str,
        deadline: float | None = None,
    ) -> tuple[dict[str, int], bool]:
        """Legacy exact-decoy search used only by stored pre-v3 games."""

        visible_history = tuple(history)
        pattern_counts: dict[str, int] = defaultdict(int)
        current_patterns, current_complete = self._patterns_for_guess(
            guess, deadline
        )
        history_patterns: list[tuple[VisibleGuess, tuple[str, ...]]] = []
        complete = current_complete
        for row in visible_history:
            patterns, row_complete = self._patterns_for_guess(
                row.guess, deadline
            )
            history_patterns.append((row, patterns))
            complete = complete and row_complete
        available = min(
            [len(current_patterns), *(len(patterns) for _, patterns in history_patterns)]
        )
        for answer_index, answer in enumerate(
            self.truth_engine.answers[:available]
        ):
            if self._budget_expired(deadline):
                return pattern_counts, True
            if answer != real_answer and all(
                patterns[answer_index] == row.feedback
                for row, patterns in history_patterns
            ):
                pattern_counts[current_patterns[answer_index]] += 1
        return pattern_counts, not complete or self._budget_expired(deadline)

    @staticmethod
    def _budget_expired(deadline: float | None) -> bool:
        return deadline is not None and perf_counter() >= deadline

    @staticmethod
    def _distance(first: str, second: str) -> int:
        return sum(left != right for left, right in zip(first, second))

    def _historical_lies(
        self,
        prior_history: tuple[VisibleGuess, ...],
        real_answer: str,
    ) -> tuple[tuple[str, str], ...]:
        lies: list[tuple[str, str]] = []
        for row in prior_history:
            truth = self.truth_engine.evaluate(row.guess, real_answer)
            lies.extend(
                (row.guess[index], displayed)
                for index, (truthful, displayed) in enumerate(
                    zip(truth, row.feedback)
                )
                if truthful != displayed
            )
        return tuple(lies)

    def _score_candidate(
        self,
        *,
        guess: str,
        truth_feedback: str,
        mutation: str,
        tile_indexes: tuple[int, ...],
        credible_worlds: int,
        credible_weight: float,
        exact_decoys: int,
        prior_history: tuple[VisibleGuess, ...],
        real_answer: str,
        seed: str,
        repeat_thread_probability: float,
        historical_lies: tuple[tuple[str, str], ...] | None = None,
    ) -> tuple[float, str | None]:
        score = 1.8 * math.log1p(credible_weight)
        score += 0.7 * math.log1p(exact_decoys)
        if historical_lies is None:
            historical_lies = self._historical_lies(
                prior_history, real_answer
            )
        thread_roll = (
            self._seeded_number(seed, "repeat-thread:v3") / 2**64
        )
        thread_letter: str | None = None

        for index in tile_indexes:
            truthful = truth_feedback[index]
            displayed = mutation[index]
            letter = guess[index]
            if truthful == "G":
                score += 1.35
            elif truthful == "Y":
                score += 0.95
            else:
                score += 0.75 if displayed == "Y" else 1.0

            repeated_claims = [
                marker
                for prior_letter, marker in historical_lies
                if prior_letter == letter
            ]
            if repeated_claims:
                thread_letter = letter
                same_claim = displayed in repeated_claims
                base_bonus = 0.35 if same_claim else 0.15
                if thread_roll < repeat_thread_probability:
                    base_bonus += 2.0 if same_claim else 0.8
                score += base_bonus * min(3, len(repeated_claims))

            if _MARKER_RANK[displayed] > _MARKER_RANK[truthful]:
                answer_count = max(1, len(self.truth_engine.answers))
                support = (
                    self._answer_position_support[index].get(letter, 0)
                    if displayed == "G"
                    else self._answer_letter_support.get(letter, 0)
                )
                frequency = support / answer_count
                rarity_floor = 0.012 if len(prior_history) < 2 else 0.025
                if frequency < rarity_floor:
                    score -= (rarity_floor - frequency) * 55

            if guess.count(letter) > 1:
                changed_copies = sum(
                    guess[other] == letter for other in tile_indexes
                )
                if changed_copies < guess.count(letter):
                    score -= 0.25

        if len(tile_indexes) == 2:
            score += 0.35
        score += min(1.0, credible_worlds / 30)
        return score, thread_letter

    @staticmethod
    def _minimum_score(attempt: int) -> float:
        # Early rows have a wide player-belief space. Late rows need a more
        # coherent alternative story so a conspicuous Z-style probe can stay true.
        return (0.55, 0.75, 1.05, 1.45, 1.80)[min(attempt, 5) - 1]

    def _belief_candidates(
        self,
        *,
        guess: str,
        real_answer: str,
        truth_feedback: str,
        prior_history: tuple[VisibleGuess, ...],
        seed: str,
        excluded_tile_indexes: Collection[int],
        max_false_tiles: int,
        credible_lie_row_cap: int,
        repeat_thread_probability: float,
        deadline: float | None,
    ) -> tuple[list[_Candidate], bool]:
        # Scan the answer worlds once and aggregate the mutations they support.
        # The earlier implementation scanned the full answer list separately
        # for every possible marker mutation (up to 50 scans for a two-tile
        # lie). Deriving each supported mutation from an answer's pattern cuts
        # the maximum-pressure path to at most eleven small checks per answer.
        aggregates: dict[
            tuple[str, tuple[int, ...]], list[int | float]
        ] = {}
        attempt = len(prior_history) + 1
        maximum = min(2, max_false_tiles)
        excluded = frozenset(excluded_tile_indexes)
        current_patterns, current_complete = self._patterns_for_guess(
            guess, deadline
        )
        history_patterns: list[tuple[VisibleGuess, tuple[str, ...]]] = []
        complete = current_complete
        for row in prior_history:
            patterns, row_complete = self._patterns_for_guess(
                row.guess, deadline
            )
            history_patterns.append((row, patterns))
            complete = complete and row_complete
        available = min(
            [
                len(current_patterns),
                *(len(patterns) for _, patterns in history_patterns),
            ]
        )
        deadline_expired = not complete

        for answer_index, answer in enumerate(
            self.truth_engine.answers[:available]
        ):
            if self._budget_expired(deadline):
                deadline_expired = True
                break
            if answer == real_answer:
                continue

            required_history_rows = 0
            required_history_tiles = 0
            exact_history = True
            credible_history = True
            for row, patterns in history_patterns:
                distance = self._distance(
                    row.feedback, patterns[answer_index]
                )
                if distance > max_false_tiles:
                    credible_history = False
                    break
                if distance:
                    required_history_rows += 1
                    required_history_tiles += distance
                    exact_history = False
                    if required_history_rows > credible_lie_row_cap:
                        credible_history = False
                        break
            if not credible_history:
                continue

            current_truth = current_patterns[answer_index]
            differing_indexes = tuple(
                index
                for index, (truthful, alternative) in enumerate(
                    zip(truth_feedback, current_truth)
                )
                if truthful != alternative and index not in excluded
            )
            differing_count = self._distance(truth_feedback, current_truth)
            for target_size in range(maximum, 0, -1):
                current_distance = differing_count - target_size
                if (
                    len(differing_indexes) < target_size
                    or current_distance < 0
                    or current_distance > max_false_tiles
                ):
                    continue
                for tile_indexes in combinations(
                    differing_indexes, target_size
                ):
                    # Selected tiles are false for the real answer and true in
                    # this alternative world; unchanged mismatches consume its
                    # remaining hypothetical lie allowance.
                    mutation_list = list(truth_feedback)
                    for index in tile_indexes:
                        mutation_list[index] = current_truth[index]
                    mutation = "".join(mutation_list)
                    if mutation == "GGGGG":
                        continue

                    required_rows = required_history_rows + int(
                        current_distance > 0
                    )
                    if required_rows > credible_lie_row_cap:
                        continue
                    required_tiles = (
                        required_history_tiles + current_distance
                    )
                    key = (mutation, tile_indexes)
                    values = aggregates.setdefault(key, [0, 0.0, 0])
                    values[0] += 1
                    values[1] += 1.0 / (
                        1.0
                        + 0.55 * required_tiles
                        + 0.75 * required_rows
                    )
                    if exact_history and current_distance == 0:
                        values[2] += 1

        candidates: list[_Candidate] = []
        historical_lies = self._historical_lies(
            prior_history, real_answer
        )
        for (mutation, tile_indexes), values in aggregates.items():
            credible_worlds = int(values[0])
            credible_weight = float(values[1])
            exact_decoys = int(values[2])
            rank_delta = sum(
                _MARKER_RANK[mutation[index]]
                - _MARKER_RANK[truth_feedback[index]]
                for index in tile_indexes
            )
            score, thread_letter = self._score_candidate(
                guess=guess,
                truth_feedback=truth_feedback,
                mutation=mutation,
                tile_indexes=tile_indexes,
                credible_worlds=credible_worlds,
                credible_weight=credible_weight,
                exact_decoys=exact_decoys,
                prior_history=prior_history,
                real_answer=real_answer,
                seed=seed,
                repeat_thread_probability=repeat_thread_probability,
                historical_lies=historical_lies,
            )
            if score < self._minimum_score(attempt):
                continue
            candidates.append(
                _Candidate(
                    feedback=mutation,
                    tile_indexes=tile_indexes,
                    tactic="fabricate" if rank_delta >= 0 else "hide",
                    credible_worlds=credible_worlds,
                    credible_weight=credible_weight,
                    exact_decoys=exact_decoys,
                    score=score,
                    thread_letter=thread_letter,
                )
            )
        return candidates, deadline_expired or self._budget_expired(deadline)

    def _select_candidate(
        self, candidates: list[_Candidate], seed: str
    ) -> _Candidate:
        best_score = max(candidate.score for candidate in candidates)
        near_best_margin = max(0.35, abs(best_score) * 0.08)
        finalists = [
            candidate
            for candidate in candidates
            if candidate.score >= best_score - near_best_margin
        ]
        return min(
            finalists,
            key=lambda candidate: self._seeded_number(
                seed,
                (
                    f"candidate:v3:{candidate.feedback}:"
                    f"{','.join(str(index) for index in candidate.tile_indexes)}"
                ),
            ),
        )

    def _decision(
        self,
        *,
        started_at: float,
        feedback: str,
        reason: DecisionReason,
        strategy: DecisionStrategy = "truth",
        selected: _Candidate | None = None,
        deadline_hit: bool = False,
    ) -> DeceptionDecision:
        return DeceptionDecision(
            feedback=selected.feedback if selected is not None else feedback,
            tile_indexes=(selected.tile_indexes if selected is not None else ()),
            reason=reason,
            strategy=strategy,
            score=selected.score if selected is not None else 0.0,
            credible_worlds=(
                selected.credible_worlds if selected is not None else 0
            ),
            exact_decoys=(selected.exact_decoys if selected is not None else 0),
            thread_letter=(selected.thread_letter if selected is not None else None),
            decision_ms=(perf_counter() - started_at) * 1_000,
            deadline_hit=deadline_hit,
        )

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
        credible_lie_row_cap: int = 2,
        repeat_thread_probability: float = 0.15,
        belief_aware: bool = True,
        time_budget_ms: int | None = DEFAULT_DECISION_BUDGET_MS,
    ) -> DeceptionDecision:
        started_at = perf_counter()
        # Reserve a small portion of the caller's wall-clock budget for ranking
        # and response construction after the answer scan stops.
        search_budget_ms = (
            None
            if time_budget_ms is None
            else max(0.0, time_budget_ms - min(8.0, time_budget_ms * 0.20))
        )
        deadline = (
            None
            if search_budget_ms is None
            else started_at + search_budget_ms / 1_000
        )
        if self._budget_expired(deadline):
            return self._decision(
                started_at=started_at,
                feedback=truth_feedback,
                reason="deadline_expired",
                deadline_hit=True,
            )

        visible_history = tuple(prior_history)
        if belief_aware:
            fallback_decision = (
                self._constraint_backed_feedback(
                    guess=guess,
                    real_answer=real_answer,
                    truth_feedback=truth_feedback,
                    prior_history=visible_history,
                    seed=seed,
                    excluded_tile_indexes=excluded_tile_indexes,
                    repeat_thread_probability=repeat_thread_probability,
                    deadline=deadline,
                    started_at=started_at,
                )
                if allow_constraint_fallback
                else None
            )
            candidates, deadline_expired = self._belief_candidates(
                guess=guess,
                real_answer=real_answer,
                truth_feedback=truth_feedback,
                prior_history=visible_history,
                seed=seed,
                excluded_tile_indexes=excluded_tile_indexes,
                max_false_tiles=max_false_tiles,
                credible_lie_row_cap=max(1, credible_lie_row_cap),
                repeat_thread_probability=repeat_thread_probability,
                deadline=deadline,
            )
            if candidates:
                selected = self._select_candidate(candidates, seed)
                return self._decision(
                    started_at=started_at,
                    feedback=truth_feedback,
                    reason="activated",
                    strategy="belief_world",
                    selected=selected,
                    deadline_hit=deadline_expired,
                )
            if deadline_expired:
                if fallback_decision is not None and fallback_decision.activated:
                    return replace(
                        fallback_decision,
                        decision_ms=(perf_counter() - started_at) * 1_000,
                        deadline_hit=True,
                    )
                return self._decision(
                    started_at=started_at,
                    feedback=truth_feedback,
                    reason="deadline_expired",
                    deadline_hit=True,
                )
            if fallback_decision is not None:
                return replace(
                    fallback_decision,
                    decision_ms=(perf_counter() - started_at) * 1_000,
                )
            return self._decision(
                started_at=started_at,
                feedback=truth_feedback,
                reason="strategy_restricted",
            )

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
                        credible_worlds=decoy_count,
                        credible_weight=float(decoy_count),
                        exact_decoys=decoy_count,
                        score=-float(decoy_count),
                    )
                )
            if candidates:
                break

        if not candidates:
            if deadline_expired:
                return self._decision(
                    started_at=started_at,
                    feedback=truth_feedback,
                    reason="deadline_expired",
                    deadline_hit=True,
                )
            if not allow_constraint_fallback:
                return self._decision(
                    started_at=started_at,
                    feedback=truth_feedback,
                    reason="strategy_restricted",
                )
            return self._constraint_backed_feedback(
                guess=guess,
                real_answer=real_answer,
                truth_feedback=truth_feedback,
                prior_history=visible_history,
                seed=seed,
                excluded_tile_indexes=excluded_tile_indexes,
                repeat_thread_probability=0.0,
                deadline=deadline,
                started_at=started_at,
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
        ] or candidates
        smallest_decoy_count = min(
            candidate.exact_decoys for candidate in tactic_candidates
        )
        finalists = [
            candidate
            for candidate in tactic_candidates
            if candidate.exact_decoys == smallest_decoy_count
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
        return self._decision(
            started_at=started_at,
            feedback=truth_feedback,
            reason="activated",
            strategy="exact_decoy",
            selected=selected,
            deadline_hit=deadline_expired,
        )

    def _constraint_backed_feedback(
        self,
        *,
        guess: str,
        real_answer: str,
        truth_feedback: str,
        prior_history: tuple[VisibleGuess, ...],
        seed: str,
        excluded_tile_indexes: Collection[int],
        repeat_thread_probability: float,
        deadline: float | None,
        started_at: float,
    ) -> DeceptionDecision:
        """Fabricate a supported yellow when no answer-world candidate exists."""

        previously_guessed: set[str] = set()
        previously_lied = self._historical_lies(prior_history, real_answer)
        previously_lied_letters = {letter for letter, _ in previously_lied}
        thread_roll = self._seeded_number(seed, "fallback-thread:v3") / 2**64
        for row in prior_history:
            if self._budget_expired(deadline):
                return self._decision(
                    started_at=started_at,
                    feedback=truth_feedback,
                    reason="deadline_expired",
                    deadline_hit=True,
                )
            previously_guessed.update(row.guess)
        visible_greens: list[set[str]] = [set() for _ in range(WORD_LENGTH)]
        for row in prior_history:
            for tile_index, marker in enumerate(row.feedback):
                if marker == "G":
                    visible_greens[tile_index].add(row.guess[tile_index])
        for tile_index, marker in enumerate(truth_feedback):
            if marker == "G":
                visible_greens[tile_index].add(guess[tile_index])

        if any(len(letters) > 1 for letters in visible_greens):
            return self._decision(
                started_at=started_at,
                feedback=truth_feedback,
                reason="strategy_restricted",
            )

        candidates: list[_Candidate] = []
        answer_count = max(1, len(self.truth_engine.answers))
        for tile_index, truth_marker in enumerate(truth_feedback):
            if self._budget_expired(deadline):
                if candidates:
                    break
                return self._decision(
                    started_at=started_at,
                    feedback=truth_feedback,
                    reason="deadline_expired",
                    deadline_hit=True,
                )
            letter = guess[tile_index]
            repeats_thread = letter in previously_lied_letters
            may_reuse = (
                repeats_thread and thread_roll < repeat_thread_probability
            )
            if (
                truth_marker != "B"
                or tile_index in excluded_tile_indexes
                or (letter in previously_guessed and not may_reuse)
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
            answer_frequency = (
                self._answer_letter_support.get(letter, 0) / answer_count
            )
            if (
                len(self.truth_engine.answers) > 2
                and len(prior_history) >= 2
                and answer_frequency < 0.02
                and not repeats_thread
            ):
                continue
            mutation = (
                truth_feedback[:tile_index]
                + "Y"
                + truth_feedback[tile_index + 1 :]
            )
            support = self._yellow_support[tile_index].get(letter, 0)
            score = math.log1p(support) + (2.0 if may_reuse else 0.0)
            candidates.append(
                _Candidate(
                    feedback=mutation,
                    tile_indexes=(tile_index,),
                    tactic="fabricate",
                    credible_worlds=0,
                    credible_weight=0.0,
                    exact_decoys=0,
                    score=score,
                    thread_letter=letter if may_reuse else None,
                )
            )

        if not candidates:
            return self._decision(
                started_at=started_at,
                feedback=truth_feedback,
                reason="no_candidate",
            )

        selected = self._select_candidate(candidates, seed + ":constraint")
        return self._decision(
            started_at=started_at,
            feedback=truth_feedback,
            reason="activated",
            strategy="constraint_backed",
            selected=selected,
            deadline_hit=self._budget_expired(deadline),
        )
