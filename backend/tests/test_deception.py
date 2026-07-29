from __future__ import annotations

from pathlib import Path

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


def test_schedule_is_deterministic_and_covers_all_six_rows() -> None:
    rows = {
        DeceptionEngine.scheduled_attempt(f"seed-{index}")
        for index in range(100)
    }

    assert rows == {1, 2, 3, 4, 5, 6}
    assert DeceptionEngine.scheduled_attempt("stable") == (
        DeceptionEngine.scheduled_attempt("stable")
    )


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


def test_no_believable_decoy_keeps_feedback_truthful() -> None:
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

    assert decision.feedback == truth
    assert decision.tile_index is None
