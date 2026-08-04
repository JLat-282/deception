from __future__ import annotations

from pathlib import Path
from time import sleep

from backend.app.deception import DeceptionEngine, VisibleGuess
from backend.app.engine import TruthEngine, load_word_list


def full_engine() -> TruthEngine:
    data_dir = Path(__file__).resolve().parents[1] / "app" / "data"
    return TruthEngine(
        load_word_list(data_dir / "words"),
        load_word_list(data_dir / "answers"),
    )


def changed_indexes(truth: str, displayed: str) -> list[int]:
    return [
        index
        for index, markers in enumerate(zip(truth, displayed))
        if markers[0] != markers[1]
    ]


def test_schedule_is_deterministic_distinct_and_weighted_around_eighty_twenty(
) -> None:
    rows = {
        row
        for index in range(1_000)
        for row in DeceptionEngine.scheduled_attempts(f"seed-{index}")
    }
    plans = [
        DeceptionEngine.scheduled_attempts(f"seed-{index}")
        for index in range(1_000)
    ]
    two_row_count = sum(len(plan) == 2 for plan in plans)

    assert rows == {1, 2, 3, 4, 5, 6}
    assert DeceptionEngine.scheduled_attempts("stable") == (
        DeceptionEngine.scheduled_attempts("stable")
    )
    assert all(len(plan) in {1, 2} for plan in plans)
    assert all(len(plan) == len(set(plan)) for plan in plans)
    assert 760 <= two_row_count <= 840


def test_fabricated_feedback_changes_exactly_one_tile() -> None:
    truth_engine = full_engine()
    deception = DeceptionEngine(truth_engine)
    truth = truth_engine.evaluate("slate", "crane")

    decision = deception.choose_feedback(
        guess="slate",
        real_answer="crane",
        truth_feedback=truth,
        prior_history=(),
        seed="seed-0",
    )

    assert changed_indexes(truth, decision.feedback) == [
        decision.tile_index
    ]
    assert decision.feedback[decision.tile_index] in {"G", "Y"}
    assert truth[decision.tile_index] == "B"
    assert decision.feedback != "GGGGG"


def test_two_tile_lie_prefers_a_jointly_supported_decoy_pattern() -> None:
    truth_engine = full_engine()
    deception = DeceptionEngine(truth_engine)
    truth = truth_engine.evaluate("slate", "crane")

    decision = deception.choose_feedback(
        guess="slate",
        real_answer="crane",
        truth_feedback=truth,
        prior_history=(),
        seed="two-tile",
        max_false_tiles=2,
        time_budget_ms=None,
    )

    assert len(decision.tile_indexes) == 2
    assert changed_indexes(truth, decision.feedback) == list(
        decision.tile_indexes
    )


def test_decision_budget_falls_back_to_truthful_feedback() -> None:
    truth_engine = full_engine()
    deception = DeceptionEngine(truth_engine)
    truth = truth_engine.evaluate("slate", "crane")

    decision = deception.choose_feedback(
        guess="slate",
        real_answer="crane",
        truth_feedback=truth,
        prior_history=(),
        seed="budget-expired",
        time_budget_ms=0,
    )

    assert decision.feedback == truth
    assert not decision.activated


def test_slow_planner_falls_back_before_exceeding_budget(monkeypatch) -> None:
    truth_engine = full_engine()
    original_evaluate = truth_engine.evaluate

    def slow_evaluate(guess: str, answer: str) -> str:
        sleep(0.01)
        return original_evaluate(guess, answer)

    monkeypatch.setattr(truth_engine, "evaluate", slow_evaluate)
    deception = DeceptionEngine(truth_engine)
    truth = original_evaluate("slate", "crane")

    decision = deception.choose_feedback(
        guess="slate",
        real_answer="crane",
        truth_feedback=truth,
        prior_history=(),
        seed="slow-budget",
        time_budget_ms=5,
    )

    assert decision.feedback == truth
    assert not decision.activated


def test_truth_can_be_concealed() -> None:
    truth_engine = full_engine()
    deception = DeceptionEngine(truth_engine)
    truth = truth_engine.evaluate("eerie", "crane")

    decision = deception.choose_feedback(
        guess="eerie",
        real_answer="crane",
        truth_feedback=truth,
        prior_history=(),
        seed="seed-2",
    )

    assert changed_indexes(truth, decision.feedback) == [2]
    assert truth[2] == "Y"
    assert decision.feedback[2] == "B"


def test_selected_pattern_has_a_decoy_consistent_with_visible_history() -> None:
    truth_engine = full_engine()
    deception = DeceptionEngine(truth_engine)
    prior = VisibleGuess(
        guess="slate",
        feedback=truth_engine.evaluate("slate", "crane"),
    )
    truth = truth_engine.evaluate("fight", "crane")

    decision = deception.choose_feedback(
        guess="fight",
        real_answer="crane",
        truth_feedback=truth,
        prior_history=(prior,),
        seed="history-seed",
    )

    if decision.activated:
        decoys = [
            answer
            for answer in truth_engine.answers
            if answer != "crane"
            and truth_engine.evaluate(prior.guess, answer) == prior.feedback
            and truth_engine.evaluate("fight", answer) == decision.feedback
        ]
        assert decoys
        assert len(changed_indexes(truth, decision.feedback)) == 1
    else:
        assert decision.feedback == truth


def test_constraint_backed_lie_fabricates_an_untouched_yellow() -> None:
    truth_engine = TruthEngine(
        valid_guesses=("crane", "slate"),
        answers=("crane",),
    )
    deception = DeceptionEngine(truth_engine)
    truth = truth_engine.evaluate("slate", "crane")

    decision = deception.choose_feedback(
        guess="slate",
        real_answer="crane",
        truth_feedback=truth,
        prior_history=(),
        seed="no-decoy",
    )

    assert decision.tile_index is not None
    assert truth[decision.tile_index] == "B"
    assert decision.feedback[decision.tile_index] == "Y"
    assert changed_indexes(truth, decision.feedback) == [
        decision.tile_index
    ]


def test_legacy_strategy_can_keep_the_strict_truthful_fallback() -> None:
    truth_engine = TruthEngine(
        valid_guesses=("crane", "slate"),
        answers=("crane",),
    )
    deception = DeceptionEngine(truth_engine)
    truth = truth_engine.evaluate("slate", "crane")

    decision = deception.choose_feedback(
        guess="slate",
        real_answer="crane",
        truth_feedback=truth,
        prior_history=(),
        seed="legacy-strategy",
        allow_constraint_fallback=False,
    )

    assert decision.feedback == truth
    assert decision.tile_index is None


def test_picky_can_lie_after_stare_and_cloud_against_gnash() -> None:
    truth_engine = full_engine()
    deception = DeceptionEngine(truth_engine)
    answer = "gnash"
    history = tuple(
        VisibleGuess(
            guess=guess,
            feedback=truth_engine.evaluate(guess, answer),
        )
        for guess in ("stare", "cloud")
    )
    truth = truth_engine.evaluate("picky", answer)

    decision = deception.choose_feedback(
        guess="picky",
        real_answer=answer,
        truth_feedback=truth,
        prior_history=history,
        seed="picky-regression",
    )

    assert truth == "BBBBB"
    assert decision.tile_index is not None
    assert decision.feedback[decision.tile_index] == "Y"
    assert "picky"[decision.tile_index] not in {
        letter for row in history for letter in row.guess
    }


def test_constraint_backed_lie_does_not_reuse_a_previously_guessed_letter(
) -> None:
    truth_engine = TruthEngine(
        valid_guesses=("crane", "picky"),
        answers=("crane",),
    )
    deception = DeceptionEngine(truth_engine)
    truth = truth_engine.evaluate("picky", "crane")

    decision = deception.choose_feedback(
        guess="picky",
        real_answer="crane",
        truth_feedback=truth,
        prior_history=(VisibleGuess("picky", truth),),
        seed="already-guessed",
    )

    assert decision.feedback == truth
    assert decision.tile_index is None


def test_constraint_backed_yellow_requires_an_available_other_position(
) -> None:
    truth_engine = TruthEngine(
        valid_guesses=("crane", "brane"),
        answers=("crane",),
    )
    deception = DeceptionEngine(truth_engine)
    truth = truth_engine.evaluate("brane", "crane")

    decision = deception.choose_feedback(
        guess="brane",
        real_answer="crane",
        truth_feedback=truth,
        prior_history=(),
        seed="no-destination",
    )

    assert truth == "BGGGG"
    assert decision.feedback == truth
    assert decision.tile_index is None


def test_excluded_tile_position_cannot_be_used_by_a_later_lie() -> None:
    truth_engine = full_engine()
    deception = DeceptionEngine(truth_engine)
    truth = truth_engine.evaluate("slate", "crane")

    first = deception.choose_feedback(
        guess="slate",
        real_answer="crane",
        truth_feedback=truth,
        prior_history=(),
        seed="seed-0",
    )
    second = deception.choose_feedback(
        guess="slate",
        real_answer="crane",
        truth_feedback=truth,
        prior_history=(),
        seed="seed-0",
        excluded_tile_indexes={first.tile_index},
    )

    assert first.tile_index is not None
    assert second.tile_index != first.tile_index
