from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from backend.app.deception import DeceptionEngine, VisibleGuess
from backend.app.difficulty import build_blueprint, get_preset, public_presets
from backend.app.engine import TruthEngine, load_word_list


DATA_DIR = Path(__file__).resolve().parents[1] / "app" / "data"
PROBE_GUESSES = ("stare", "cloud", "picky", "berry", "mould", "fight")


def percentile(values: list[float], proportion: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int((len(ordered) - 1) * proportion))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Exercise scheduled lie rows through representative high-information "
            "guess histories."
        )
    )
    parser.add_argument("--games-per-preset", type=int, default=400)
    parser.add_argument("--enforce-targets", action="store_true")
    args = parser.parse_args()
    if args.games_per_preset < 50:
        parser.error("--games-per-preset must be at least 50")

    truth_engine = TruthEngine(
        load_word_list(DATA_DIR / "words"),
        load_word_list(DATA_DIR / "answers"),
    )
    deception = DeceptionEngine(truth_engine)
    passed = True
    print(
        "Scheduled-lie activation "
        f"({args.games_per_preset} games per preset)"
    )

    for preset in public_presets():
        scheduled: Counter[int] = Counter()
        activated: Counter[int] = Counter()
        timings: list[float] = []
        altered_tiles = 0
        suppressed_positive_tiles = 0
        positive_lie_events = 0
        suppression_events = 0
        cap_obeyed = True
        for game_index in range(args.games_per_preset):
            answer = truth_engine.answers[
                (game_index * 7_919) % len(truth_engine.answers)
            ]
            blueprint = build_blueprint(
                preset.key, f"activation:{preset.key}:{game_index}"
            )
            history: list[VisibleGuess] = []
            used_tile_indexes: set[int] = set()
            game_altered_tiles = 0
            game_suppressed_positive_tiles = 0
            for attempt, guess in enumerate(PROBE_GUESSES, start=1):
                truth = truth_engine.evaluate(guess, answer)
                displayed = truth
                if (
                    attempt in blueprint.lie_attempts
                    and attempt < 6
                    and guess != answer
                ):
                    scheduled[attempt] += 1
                    decision = deception.choose_feedback(
                        guess=guess,
                        real_answer=answer,
                        truth_feedback=truth,
                        prior_history=history,
                        seed=f"{blueprint.seed}:activation:{attempt}",
                        excluded_tile_indexes=(
                            ()
                            if preset.max_false_tiles > 1
                            else used_tile_indexes
                        ),
                        max_false_tiles=blueprint.false_tiles_for_attempt(
                            attempt
                        ),
                        credible_lie_row_cap=(
                            preset.lie_policy.credible_lie_row_cap
                        ),
                        repeat_thread_probability=(
                            preset.lie_policy.repeat_thread_probability
                        ),
                        time_budget_ms=40,
                    )
                    timings.append(decision.decision_ms)
                    displayed = decision.feedback
                    if decision.activated:
                        activated[attempt] += 1
                        used_tile_indexes.update(decision.tile_indexes)
                        positive_lie_events += any(
                            marker in {"G", "Y"} for marker in truth
                        )
                        row_suppressed_positive_tiles = sum(
                            truthful in {"G", "Y"} and displayed == "B"
                            for truthful, displayed in zip(
                                truth, decision.feedback
                            )
                        )
                        game_altered_tiles += len(decision.tile_indexes)
                        game_suppressed_positive_tiles += (
                            row_suppressed_positive_tiles
                        )
                        suppression_events += row_suppressed_positive_tiles > 0
                        cap_obeyed = cap_obeyed and (
                            row_suppressed_positive_tiles <= 1
                        )
                history.append(VisibleGuess(guess, displayed))
            altered_tiles += game_altered_tiles
            suppressed_positive_tiles += game_suppressed_positive_tiles
            cap_obeyed = cap_obeyed and (
                game_altered_tiles <= 6
                and game_suppressed_positive_tiles <= 2
            )

        rates = {
            attempt: activated[attempt] / scheduled[attempt]
            for attempt in range(1, 6)
            if scheduled[attempt]
        }
        p99 = percentile(timings, 0.99)
        maximum = max(timings)
        p999 = percentile(timings, 0.999)
        suppression_rate = (
            suppressed_positive_tiles / max(1, altered_tiles)
        )
        suppression_event_rate = (
            suppression_events / max(1, positive_lie_events)
        )
        print(
            f"- {preset.key}: "
            + " ".join(
                f"g{attempt}={rate:.1%}" for attempt, rate in rates.items()
            )
            + (
                f" positive-to-gray-tiles={suppression_rate:.1%}"
                f" positive-lie-events={suppression_event_rate:.1%}"
                f" p99={p99:.2f}ms p99.9={p999:.2f}ms max={maximum:.2f}ms"
            )
        )

        for attempt in range(1, 4):
            passed = passed and rates.get(attempt, 0.0) >= 0.95
        passed = passed and rates.get(4, 0.0) >= 0.90
        late_floor = {
            "doubt-1@3": 0.85,
            "doubt-2@3": 0.82,
            "doubt-3@3": 0.85,
            "deception@3": 0.75,
        }[preset.key]
        passed = passed and rates.get(5, 0.0) >= late_floor
        passed = passed and cap_obeyed and suppression_rate <= 0.30
        if preset.key == "deception@3":
            passed = passed and 0.18 <= suppression_event_rate <= 0.32
        passed = passed and p99 <= 35 and p999 <= 50

    if args.enforce_targets and not passed:
        print("Target missed: activation quality or latency fell below its gate.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
