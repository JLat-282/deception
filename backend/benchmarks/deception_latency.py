from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from time import perf_counter

from backend.app.deception import DeceptionEngine, VisibleGuess
from backend.app.engine import TruthEngine, load_word_list


DATA_DIR = Path(__file__).resolve().parents[1] / "app" / "data"


@dataclass(frozen=True)
class Scenario:
    name: str
    guess: str
    prior_guesses: tuple[str, ...]
    maximum_p99_ms: float
    answer: str = "crane"
    must_activate: bool = False
    max_false_tiles: int = 1


SCENARIOS = (
    Scenario("first selected row", "slate", (), 25),
    Scenario("selected row after one guess", "fight", ("slate",), 25),
    Scenario(
        "selected row after four guesses",
        "shack",
        ("slate", "fight", "mould", "berry"),
        35,
    ),
    Scenario(
        name="constraint-backed fallback",
        guess="picky",
        prior_guesses=("stare", "cloud"),
        maximum_p99_ms=25,
        answer="gnash",
        must_activate=True,
    ),
    Scenario(
        name="Doubt III coordinated two-tile search",
        guess="slate",
        prior_guesses=(),
        maximum_p99_ms=35,
        must_activate=True,
        max_false_tiles=2,
    ),
    Scenario(
        name="Deception False Victory search",
        guess="crane",
        prior_guesses=("fight",),
        maximum_p99_ms=35,
        must_activate=True,
        max_false_tiles=2,
    ),
)


def percentile(values: list[float], proportion: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int((len(ordered) - 1) * proportion))
    return ordered[index]


def benchmark_scenario(
    truth_engine: TruthEngine,
    deception_engine: DeceptionEngine,
    scenario: Scenario,
    samples: int,
) -> dict[str, float]:
    answer = scenario.answer
    history = tuple(
        VisibleGuess(
            guess=guess,
            feedback=truth_engine.evaluate(guess, answer),
        )
        for guess in scenario.prior_guesses
    )
    truth_feedback = truth_engine.evaluate(scenario.guess, answer)
    timings: list[float] = []

    for sample in range(samples):
        started_at = perf_counter()
        decision = deception_engine.choose_feedback(
            guess=scenario.guess,
            real_answer=answer,
            truth_feedback=truth_feedback,
            prior_history=history,
            seed=f"benchmark-{scenario.name}-{sample}",
            max_false_tiles=scenario.max_false_tiles,
        )
        timings.append((perf_counter() - started_at) * 1_000)
        if scenario.must_activate and not decision.activated:
            raise RuntimeError(
                f"{scenario.name} did not activate its expected lie"
            )
        if (
            scenario.max_false_tiles == 2
            and len(decision.tile_indexes) != 2
        ):
            raise RuntimeError(
                f"{scenario.name} did not produce its expected two-tile lie"
            )

    return {
        "p50": median(timings),
        "p95": percentile(timings, 0.95),
        "p99": percentile(timings, 0.99),
        "p99.9": percentile(timings, 0.999),
        "max": max(timings),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure the deception planner's cold calculation path."
    )
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument(
        "--enforce-target",
        action="store_true",
        help=(
            "Fail unless p99 and hard-ceiling latency gates are met."
        ),
    )
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("--samples must be at least 1")

    truth_engine = TruthEngine(
        load_word_list(DATA_DIR / "words"),
        load_word_list(DATA_DIR / "answers"),
    )
    deception_engine = DeceptionEngine(truth_engine)
    target_met = True

    print(f"Deception planner latency ({args.samples} samples per scenario)")
    for scenario in SCENARIOS:
        results = benchmark_scenario(
            truth_engine,
            deception_engine,
            scenario,
            args.samples,
        )
        metrics = "  ".join(
            f"{name}={value:.2f}ms" for name, value in results.items()
        )
        scenario_met = (
            results["p99"] <= scenario.maximum_p99_ms
            and results["p99.9"] <= 50
        )
        summary = (
            f"p99 budget={scenario.maximum_p99_ms:.0f}ms "
            "p99.9 ceiling=50ms"
        )
        target_met = target_met and scenario_met
        print(f"- {scenario.name}: {metrics}  {summary}".rstrip())

    if args.enforce_target and not target_met:
        print("Target missed: a performance requirement was not met.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
