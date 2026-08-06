from __future__ import annotations

import argparse
from collections import Counter
from statistics import median
from time import perf_counter

from backend.app.difficulty import build_blueprint, get_preset, public_presets


LIE_TARGETS = {
    "doubt-1@3": {1: 0.85, 2: 0.15},
    "doubt-2@3": {1: 0.20, 2: 0.75, 3: 0.05},
    "doubt-3@3": {2: 0.25, 3: 0.70, 4: 0.05},
    "deception@3": {3: 0.05, 4: 0.40, 5: 0.55},
}
REVERSE_TARGETS = {
    "doubt-1@3": 0.15,
    "doubt-2@3": 0.30,
    "doubt-3@3": 0.55,
    "deception@3": 0.75,
}
TIMER_TARGETS = {
    "doubt-1@3": 0.22,
    "doubt-2@3": 0.55,
    "doubt-3@3": 0.95,
    "deception@3": 1.00,
}
STACK_BANDS = {
    "doubt-1@3": (0.00, 0.00),
    "doubt-2@3": (0.12, 0.28),
    "doubt-3@3": (0.95, 1.00),
    "deception@3": (0.99, 1.00),
}
EVENT_COUNT_BANDS = {
    "doubt-1@3": (0.50, 0.65),
    "doubt-2@3": (1.90, 2.30),
    "doubt-3@3": (4.70, 5.30),
    "deception@3": (7.70, 8.40),
}
PRESSURE_COST_BANDS = {
    "doubt-1@3": (0.65, 0.95),
    "doubt-2@3": (3.20, 4.00),
    "doubt-3@3": (9.20, 10.80),
    "deception@3": (16.50, 18.50),
}
BLACKOUT_BANDS = {
    "doubt-1@3": (0.00, 0.00),
    "doubt-2@3": (0.15, 0.28),
    "doubt-3@3": (0.58, 0.70),
    "deception@3": (0.75, 0.88),
}
REVERSE_TIMER_BANDS = {
    "doubt-1@3": (0.00, 0.00),
    "doubt-2@3": (0.00, 0.00),
    "doubt-3@3": (0.12, 0.28),
    "deception@3": (0.32, 0.50),
}
SCENE_BANDS = {
    "doubt-1@3": (0.00, 0.00),
    "doubt-2@3": (0.03, 0.10),
    "doubt-3@3": (0.65, 0.85),
    "deception@3": (0.90, 1.00),
}
INPUT_KINDS = {
    "reverseEntry", "blindEntry", "noRevision", "forcedCommitment"
}
ALLOWED_INPUT_PAIR = {"reverseEntry", "forcedCommitment"}


def percentile(values: list[float], proportion: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int((len(ordered) - 1) * proportion))
    return ordered[index]


def validate_blueprint(preset_key: str, blueprint) -> None:
    preset = get_preset(preset_key)
    plans = blueprint.punishment_plans
    if sum(plan.pressure_cost for plan in plans) > preset.pressure_budget:
        raise AssertionError(f"{preset_key}: pressure budget exceeded")
    if len(plans) > preset.max_punishment_events:
        raise AssertionError(f"{preset_key}: event cap exceeded")
    reverse_attempts = sorted(
        plan.effective_attempt for plan in plans if plan.kind == "reverseEntry"
    )
    if any(
        right == left
        for left, right in zip(reverse_attempts, reverse_attempts[1:])
    ):
        raise AssertionError(f"{preset_key}: duplicate Reverse Entry events")
    for attempt in range(1, 7):
        active = blueprint.punishments_for_effective(attempt)
        inputs = [plan for plan in active if plan.kind in INPUT_KINDS]
        input_kinds = {plan.kind for plan in inputs}
        if len(inputs) > 1 and input_kinds != ALLOWED_INPUT_PAIR:
            raise AssertionError(
                f"{preset_key}: illegal input stack on guess {attempt}: "
                f"{sorted(input_kinds)}"
            )
        ten_second = any(
            plan.kind == "timer"
            and plan.config.get("durationSeconds") == 10
            for plan in active
        )
        if ten_second and len(inputs) > 1:
            raise AssertionError(
                f"{preset_key}: 10-second timer has two input modifiers"
            )
    memory = next((plan for plan in plans if plan.kind == "memoryTax"), None)
    blackout = next((plan for plan in plans if plan.kind == "blackout"), None)
    if (
        memory is not None
        and blackout is not None
        and abs(memory.effective_attempt - blackout.effective_attempt) <= 1
    ):
        raise AssertionError(f"{preset_key}: Memory Tax adjacent to Blackout")
    if blackout is not None and blackout.effective_attempt not in {3, 4, 5}:
        raise AssertionError(f"{preset_key}: Blackout outside guesses 3-5")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Simulate v3 balance distributions and compatibility gates."
    )
    parser.add_argument("--samples", type=int, default=100_000)
    parser.add_argument("--enforce-targets", action="store_true")
    args = parser.parse_args()
    if args.samples < 4:
        parser.error("--samples must be at least 4")

    presets = public_presets()
    per_preset = max(1, args.samples // len(presets))
    passed = True
    print(
        f"Difficulty Director v3 simulation "
        f"({per_preset * len(presets)} seeded blueprints)"
    )
    for preset in presets:
        lie_counts: Counter[int] = Counter()
        reverse_games = 0
        timer_games = 0
        stacked_games = 0
        blackout_games = 0
        reverse_timer_games = 0
        scene_games = 0
        quiet_games = 0
        total_events = 0
        total_pressure_cost = 0
        lie_rows: Counter[int] = Counter()
        timings: list[float] = []
        for index in range(per_preset):
            started = perf_counter()
            blueprint = build_blueprint(
                preset.key, f"balance:v3:{preset.key}:{index}"
            )
            timings.append((perf_counter() - started) * 1_000)
            validate_blueprint(preset.key, blueprint)
            lie_counts[len(blueprint.lie_attempts)] += 1
            lie_rows.update(blueprint.lie_attempts)
            total_events += len(blueprint.punishment_plans)
            total_pressure_cost += sum(
                plan.pressure_cost for plan in blueprint.punishment_plans
            )
            kinds = {plan.kind for plan in blueprint.punishment_plans}
            reverse_games += "reverseEntry" in kinds
            timer_games += "timer" in kinds
            blackout_games += "blackout" in kinds
            scene_games += any(
                "sceneId" in plan.config for plan in blueprint.punishment_plans
            )
            stacked_games += any(
                len(blueprint.punishments_for_effective(attempt)) > 1
                for attempt in range(1, 7)
            )
            reverse_timer_games += any(
                {
                    plan.kind
                    for plan in blueprint.punishments_for_effective(attempt)
                } >= {"reverseEntry", "timer"}
                for attempt in range(1, 7)
            )
            quiet_threshold = {
                "doubt-1@3": 0,
                "doubt-2@3": 1,
                "doubt-3@3": 4,
                "deception@3": 6,
            }[preset.key]
            quiet_games += len(blueprint.punishment_plans) < quiet_threshold

        lie_rates = {
            count: occurrences / per_preset
            for count, occurrences in lie_counts.items()
        }
        reverse_rate = reverse_games / per_preset
        timer_rate = timer_games / per_preset
        stack_rate = stacked_games / per_preset
        blackout_rate = blackout_games / per_preset
        reverse_timer_rate = reverse_timer_games / per_preset
        scene_rate = scene_games / per_preset
        quiet_rate = quiet_games / per_preset
        average_events = total_events / per_preset
        average_pressure_cost = total_pressure_cost / per_preset
        p50 = median(timings)
        p99 = percentile(timings, 0.99)
        maximum = max(timings)
        p999 = percentile(timings, 0.999)
        print(
            f"- {preset.key}: lies={lie_rates} reverse={reverse_rate:.1%} "
            f"timer={timer_rate:.1%} stacked={stack_rate:.1%} "
            f"blackout={blackout_rate:.1%} reverse+timer={reverse_timer_rate:.1%} "
            f"scenes={scene_rate:.1%} quiet={quiet_rate:.1%} "
            f"events={average_events:.2f} cost={average_pressure_cost:.2f} "
            f"p50={p50:.3f}ms p99={p99:.3f}ms p99.9={p999:.3f}ms "
            f"max={maximum:.3f}ms"
        )

        for count, target in LIE_TARGETS[preset.key].items():
            passed = passed and abs(lie_rates.get(count, 0.0) - target) <= 0.02
        passed = passed and abs(
            reverse_rate - REVERSE_TARGETS[preset.key]
        ) <= 0.025
        passed = passed and abs(
            timer_rate - TIMER_TARGETS[preset.key]
        ) <= 0.025
        lower_stack, upper_stack = STACK_BANDS[preset.key]
        passed = passed and lower_stack <= stack_rate <= upper_stack
        lower_events, upper_events = EVENT_COUNT_BANDS[preset.key]
        passed = passed and lower_events <= average_events <= upper_events
        lower_cost, upper_cost = PRESSURE_COST_BANDS[preset.key]
        passed = passed and lower_cost <= average_pressure_cost <= upper_cost
        lower_blackout, upper_blackout = BLACKOUT_BANDS[preset.key]
        passed = passed and lower_blackout <= blackout_rate <= upper_blackout
        lower_combo, upper_combo = REVERSE_TIMER_BANDS[preset.key]
        passed = passed and lower_combo <= reverse_timer_rate <= upper_combo
        lower_scene, upper_scene = SCENE_BANDS[preset.key]
        passed = passed and lower_scene <= scene_rate <= upper_scene
        passed = passed and quiet_rate <= {
            "doubt-1@3": 1.00,
            "doubt-2@3": 0.01,
            "doubt-3@3": 0.08,
            "deception@3": 0.03,
        }[preset.key]
        expected_row_rate = sum(
            count * probability
            for count, probability in LIE_TARGETS[preset.key].items()
        ) / 6
        passed = passed and all(
            abs(lie_rows[row] / per_preset - expected_row_rate) <= 0.02
            for row in range(1, 7)
        )
        # This mixed workload validates every blueprint between measurements
        # and is sensitive to host scheduling pauses. Keep a broad regression
        # ceiling here; the isolated punishment benchmark owns the strict
        # per-level 5-10ms p99 and 10-20ms p99.9 gates.
        passed = passed and p99 <= 25.0 and p999 <= 50.0

    if args.enforce_targets and not passed:
        print("Target missed: a balance distribution or performance gate failed.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
