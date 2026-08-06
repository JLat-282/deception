from __future__ import annotations

from pathlib import Path
from time import perf_counter, sleep

from backend.app.deception import DeceptionEngine, VisibleGuess, _Candidate
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
    assert decision.feedback[decision.tile_index] != truth[decision.tile_index]
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
    assert decision.reason == "deadline_expired"


def test_deadline_uses_a_plausible_candidate_already_found(monkeypatch) -> None:
    truth_engine = TruthEngine(
        valid_guesses=("outre", "store", "crane", "stare"),
        answers=("outre", "store", "crane"),
    )
    deception = DeceptionEngine(truth_engine)
    partial = _Candidate(
        feedback="BYBGG",
        tile_indexes=(0, 1),
        tactic="hide",
        credible_worlds=1,
        credible_weight=0.5,
        exact_decoys=0,
        score=2.0,
    )
    monkeypatch.setattr(
        deception,
        "_belief_candidates",
        lambda **_kwargs: ([partial], True),
    )
    truth = truth_engine.evaluate("stare", "store")

    decision = deception.choose_feedback(
        guess="stare",
        real_answer="store",
        truth_feedback=truth,
        prior_history=(),
        seed="partial-candidate",
        max_false_tiles=2,
        time_budget_ms=100,
    )

    assert truth == "GGBGG"
    assert decision.feedback == "BYBGG"
    assert decision.tile_indexes == (0, 1)
    assert decision.reason == "activated"
    assert decision.deadline_hit is True


def test_stare_store_first_row_regression_uses_scheduled_lie() -> None:
    truth_engine = full_engine()
    deception = DeceptionEngine(truth_engine)
    truth = truth_engine.evaluate("stare", "store")

    decision = deception.choose_feedback(
        guess="stare",
        real_answer="store",
        truth_feedback=truth,
        prior_history=(),
        seed=(
            "67013aa86480b43c14c67a2bddb4e970"
            "14af1daeb59fc219c3834272ce0a879e"
        ),
        allow_constraint_fallback=True,
        max_false_tiles=2,
        time_budget_ms=100,
    )

    assert truth == "GGBGG"
    assert decision.feedback != truth
    assert len(decision.tile_indexes) == 2
    assert decision.reason == "activated"


def test_slow_planner_uses_candidate_found_before_budget(monkeypatch) -> None:
    truth_engine = full_engine()
    original_evaluate = truth_engine.evaluate

    def slow_evaluate(guess: str, answer: str) -> str:
        sleep(0.01)
        return original_evaluate(guess, answer)

    monkeypatch.setattr(truth_engine, "evaluate", slow_evaluate)
    deception = DeceptionEngine(truth_engine)
    truth = original_evaluate("slate", "crane")

    started_at = perf_counter()
    decision = deception.choose_feedback(
        guess="slate",
        real_answer="crane",
        truth_feedback=truth,
        prior_history=(),
        seed="slow-budget",
        time_budget_ms=5,
    )
    elapsed = perf_counter() - started_at

    assert decision.feedback != truth
    assert decision.activated
    assert decision.reason == "activated"
    assert elapsed < 0.1


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
    assert decision.reason == "strategy_restricted"


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
    assert decision.feedback[decision.tile_index] in {"G", "Y"}
    assert "picky"[decision.tile_index] not in {
        letter for row in history for letter in row.guess
    }


def test_strong_first_guess_can_lie_without_an_exact_decoy() -> None:
    truth_engine = TruthEngine(
        valid_guesses=("staez", "stare", "plane"),
        answers=("stare", "plane"),
    )
    deception = DeceptionEngine(truth_engine)
    truth = truth_engine.evaluate("staez", "stare")

    decision = deception.choose_feedback(
        guess="staez",
        real_answer="stare",
        truth_feedback=truth,
        prior_history=(),
        seed="wide-first-row",
        max_false_tiles=1,
        time_budget_ms=None,
    )

    assert truth == "GGGYB"
    assert decision.activated
    assert decision.strategy == "belief_world"
    assert decision.exact_decoys == 0
    assert decision.credible_worlds >= 1
    assert len(changed_indexes(truth, decision.feedback)) == 1


def test_late_unsupported_rare_letter_probe_can_stay_truthful() -> None:
    truth_engine = TruthEngine(
        valid_guesses=("crane", "slate", "stare", "zippy"),
        answers=("crane", "slate", "stare"),
    )
    deception = DeceptionEngine(truth_engine)
    truth = truth_engine.evaluate("zippy", "crane")
    prior = tuple(
        VisibleGuess("slate", truth_engine.evaluate("slate", "crane"))
        for _ in range(3)
    )

    decision = deception.choose_feedback(
        guess="zippy",
        real_answer="crane",
        truth_feedback=truth,
        prior_history=prior,
        seed="late-rare-probe",
        max_false_tiles=1,
        time_budget_ms=None,
    )

    assert truth == "BBBBB"
    assert decision.feedback == truth
    assert decision.reason == "no_candidate"


def test_repeat_thread_can_reuse_a_previously_lied_about_letter() -> None:
    truth_engine = TruthEngine(
        valid_guesses=("crane", "slate", "stare"),
        answers=("crane",),
    )
    deception = DeceptionEngine(truth_engine)
    prior_truth = truth_engine.evaluate("slate", "crane")
    prior_lie = prior_truth[:3] + "Y" + prior_truth[4:]
    truth = truth_engine.evaluate("stare", "crane")

    decision = deception.choose_feedback(
        guess="stare",
        real_answer="crane",
        truth_feedback=truth,
        prior_history=(VisibleGuess("slate", prior_lie),),
        seed="repeat-thread",
        excluded_tile_indexes={0, 2, 3, 4},
        repeat_thread_probability=1.0,
        time_budget_ms=None,
    )

    assert decision.activated
    assert decision.tile_index == 1
    assert decision.thread_letter == "t"


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
    assert decision.reason == "no_candidate"


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
