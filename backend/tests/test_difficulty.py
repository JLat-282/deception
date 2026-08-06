from __future__ import annotations

from collections import Counter
from dataclasses import FrozenInstanceError
import json

import pytest

from backend.app.difficulty import (
    BlueprintOverrides,
    CURRENT_LIE_TILE_CAP,
    GameBlueprint,
    build_blueprint,
    public_presets,
)


def test_preset_registry_exposes_all_four_versioned_levels() -> None:
    presets = public_presets()

    assert [preset.key for preset in presets] == [
        "doubt-1@3",
        "doubt-2@3",
        "doubt-3@3",
        "deception@3",
    ]
    assert [preset.available for preset in presets] == [True, True, True, True]
    assert [preset.lie_count_weights for preset in presets] == [
        ((1, 0.85), (2, 0.15)),
        ((1, 0.20), (2, 0.75), (3, 0.05)),
        ((2, 0.25), (3, 0.70), (4, 0.05)),
        ((3, 0.20), (4, 0.75), (5, 0.05)),
    ]
    assert presets[2].timer_count_weights == (
        (0, 0.05), (1, 0.50), (2, 0.45)
    )
    assert presets[2].two_tile_probability == 0.35
    assert presets[2].max_reverse_events == 2
    assert presets[2].combination_policy == "limited"
    assert [preset.blackout_probability for preset in presets] == [
        0.0,
        0.30,
        0.75,
        0.95,
    ]
    assert [preset.intrusion_probability for preset in presets] == [
        0.0,
        0.12,
        0.30,
        0.50,
    ]
    assert presets[3].timer_count_weights == ((1, 0.15), (2, 0.45), (3, 0.40))
    assert [preset.reverse_probability for preset in presets] == [
        0.15, 0.30, 0.55, 0.75
    ]
    assert [preset.blind_entry_probability for preset in presets] == [
        0.08, 0.22, 0.40, 0.55
    ]
    assert [preset.corrupted_history_probability for preset in presets] == [
        0.12, 0.25, 0.30, 0.30
    ]
    assert [preset.no_revision_probability for preset in presets] == [
        0.0, 0.15, 0.35, 0.50
    ]
    assert [preset.forced_commitment_probability for preset in presets] == [
        0.0, 0.10, 0.35, 0.55
    ]
    assert [preset.memory_tax_probability for preset in presets] == [
        0.0, 0.0, 0.50, 0.80
    ]
    assert [preset.pressure_scene_probability for preset in presets] == [
        0.0, 0.15, 0.80, 0.95
    ]
    assert [preset.pressure_budget for preset in presets] == [2, 6, 12, 20]
    assert [preset.max_punishment_events for preset in presets] == [1, 3, 7, 11]
    assert presets[3].two_tile_probability == 0.45
    assert presets[3].false_victory_probability == 0.05
    assert presets[3].max_reverse_events == 3
    assert presets[3].combination_policy == "broad"
    assert all(
        preset.lie_policy.repeat_thread_probability > 0
        for preset in presets
    )


def test_blueprint_is_deterministic_canonical_and_immutable() -> None:
    first = build_blueprint("doubt-2@1", "stable-seed")
    second = build_blueprint("doubt-2@1", "stable-seed")

    assert first == second
    assert first.to_json() == second.to_json()
    encoded = json.loads(first.to_json())
    assert encoded["preset_key"] == "doubt-2@1"
    assert encoded["schema_version"] == 4
    assert encoded["false_victory_enabled"] is False
    with pytest.raises(FrozenInstanceError):
        first.preset_key = "doubt-1@1"  # type: ignore[misc]


def test_blueprint_decoder_rejects_unknown_schema_version() -> None:
    value = json.loads(build_blueprint("doubt-2@1", "stable-seed").to_json())
    value["schema_version"] = 7

    with pytest.raises(ValueError, match="Unsupported game blueprint schema"):
        GameBlueprint.from_json(json.dumps(value))


def test_blueprint_decoder_migrates_schema_two_without_false_victory() -> None:
    value = json.loads(build_blueprint("doubt-3@1", "legacy-seed").to_json())
    value["schema_version"] = 2
    value.pop("false_victory_enabled")

    restored = GameBlueprint.from_json(json.dumps(value))

    assert restored.schema_version == 4
    assert restored.false_victory_enabled is False
    assert restored.intrusion_probability == 0.0


def test_blueprint_decoder_migrates_schema_three_without_intrusion() -> None:
    value = json.loads(build_blueprint("doubt-3@1", "legacy-seed").to_json())
    value["schema_version"] = 3
    value.pop("intrusion_probability")

    restored = GameBlueprint.from_json(json.dumps(value))

    assert restored.schema_version == 4
    assert restored.intrusion_probability == 0.0


def test_doubt_one_timer_owns_the_single_punishment_slot() -> None:
    blueprint = build_blueprint(
        "doubt-1@1",
        "timer-seed",
        BlueprintOverrides(
            timer_roll=0.0,
            timer_attempt=3,
            reverse_enabled=True,
            blackout_roll=0.0,
        ),
    )

    assert len(blueprint.lie_attempts) == 1
    assert blueprint.timer_attempt == 3
    assert blueprint.timer_duration_seconds == 30
    assert blueprint.reverse_enabled is False
    assert blueprint.blackout_attempt is None


def test_doubt_two_preserves_blackout_buffer_when_scheduling_timer() -> None:
    blueprint = build_blueprint(
        "doubt-2@1",
        "collision-seed",
        BlueprintOverrides(
            timer_roll=0.0,
            timer_attempt=4,
            timer_duration=10,
            blackout_roll=0.0,
            blackout_attempt=4,
        ),
    )

    assert blueprint.blackout_blocked_attempts == (4, 5)
    assert blueprint.timer_attempt not in {4, 5}
    assert blueprint.timer_duration_seconds == 10


def test_deception_limits_timers_to_two_consecutive_attempts() -> None:
    blueprint = build_blueprint(
        "deception@1",
        "extreme-seed",
        BlueprintOverrides(
            timer_attempts=(2, 3, 4),
            timer_durations=(10, 10, 10),
            blackout_enabled=False,
        ),
    )

    attempts = {event.attempt for event in blueprint.timer_events}
    assert len(attempts) == 3
    assert not any(
        {start, start + 1, start + 2} <= attempts for start in range(2, 5)
    )


def test_deception_allows_ten_second_timer_after_blackout() -> None:
    blueprint = build_blueprint(
        "deception@1",
        "broad-overlap-seed",
        BlueprintOverrides(
            timer_attempts=(4,),
            timer_durations=(10,),
            blackout_roll=0.0,
            blackout_attempt=3,
        ),
    )

    assert blueprint.blackout_attempt == 3
    assert blueprint.timer_events[0].attempt == 4
    assert blueprint.timer_events[0].duration_seconds == 10


def test_deception_false_victory_is_enabled_in_about_five_percent_of_games() -> None:
    blueprints = [
        build_blueprint("deception@1", f"false-victory-{index}")
        for index in range(1_000)
    ]
    enabled = sum(blueprint.false_victory_enabled for blueprint in blueprints)

    assert 30 <= enabled <= 70
    assert all(
        len(blueprint.lie_attempts) in {3, 4, 5}
        and len(blueprint.timer_events) in {1, 2, 3}
        for blueprint in blueprints
    )


def test_doubt_three_builds_repeated_events_and_two_tile_targets() -> None:
    blueprint = build_blueprint(
        "doubt-3@1",
        "doubt-three-seed",
        BlueprintOverrides(
            lie_attempts=(1, 3, 5),
            timer_attempts=(4, 5),
            timer_durations=(10, 30),
            blackout_roll=0.0,
            blackout_attempt=3,
        ),
    )

    assert len(blueprint.lie_attempts) == 3
    assert len(blueprint.lie_tile_counts) == 3
    assert blueprint.reverse_max_events == 2
    assert len(blueprint.timer_events) == 2
    assert len({event.attempt for event in blueprint.timer_events}) == 2
    assert all(
        event.attempt != 4
        for event in blueprint.timer_events
        if event.duration_seconds == 10
    )


def test_v2_blueprints_use_normalized_bounded_punishment_plans() -> None:
    limits = {
        "doubt-1@2": (2, 1),
        "doubt-2@2": (4, 2),
        "doubt-3@2": (8, 4),
        "deception@2": (13, 7),
    }
    input_kinds = {
        "reverseEntry", "blindEntry", "noRevision", "forcedCommitment"
    }
    for preset_key, (budget, cap) in limits.items():
        for index in range(500):
            blueprint = build_blueprint(preset_key, f"bounded-{index}")
            plans = blueprint.punishment_plans
            assert blueprint.schema_version == 5
            assert len(plans) <= cap
            assert sum(plan.pressure_cost for plan in plans) <= budget
            for attempt in range(1, 7):
                effective = blueprint.punishments_for_effective(attempt)
                active_input = [
                    plan for plan in effective if plan.kind in input_kinds
                ]
                assert len(active_input) <= 1
                ten_second = [
                    plan for plan in effective
                    if plan.kind == "timer"
                    and plan.config.get("durationSeconds") == 10
                ]
                assert not (ten_second and active_input)


def test_doubt_one_v2_uses_one_categorical_punishment_slot() -> None:
    counts = {
        "reverseEntry": 0,
        "timer": 0,
        "blindEntry": 0,
        "corruptedHistory": 0,
    }
    for index in range(10_000):
        plans = build_blueprint(
            "doubt-1@2", f"distribution-{index}"
        ).punishment_plans
        assert len(plans) <= 1
        if plans:
            counts[plans[0].kind] += 1
    targets = {
        "reverseEntry": 0.10,
        "timer": 0.15,
        "blindEntry": 0.05,
        "corruptedHistory": 0.10,
    }
    for kind, target in targets.items():
        assert abs(counts[kind] / 10_000 - target) <= 0.02


def test_v3_lie_count_distributions_match_approved_weights() -> None:
    targets = {
        "doubt-1@3": {1: 0.85, 2: 0.15},
        "doubt-2@3": {1: 0.20, 2: 0.75, 3: 0.05},
        "doubt-3@3": {2: 0.25, 3: 0.70, 4: 0.05},
        "deception@3": {3: 0.20, 4: 0.75, 5: 0.05},
    }
    for preset_key, expected in targets.items():
        counts = Counter(
            len(build_blueprint(preset_key, f"lie-matrix-{index}").lie_attempts)
            for index in range(10_000)
        )
        for lie_count, target in expected.items():
            assert abs(counts[lie_count] / 10_000 - target) <= 0.02


def test_current_blueprints_cap_total_false_tiles_at_six() -> None:
    for preset_key in (
        "doubt-1@3", "doubt-2@3", "doubt-3@3", "deception@3"
    ):
        for index in range(2_000):
            blueprint = build_blueprint(preset_key, f"tile-cap-{index}")
            assert sum(blueprint.lie_tile_counts) <= CURRENT_LIE_TILE_CAP

    with pytest.raises(ValueError, match="at most 6 false tiles"):
        build_blueprint(
            "deception@3",
            "invalid-tile-cap",
            BlueprintOverrides(
                lie_attempts=(1, 2, 3, 4),
                lie_tile_counts=(2, 2, 2, 2),
            ),
        )


def test_v3_blueprints_obey_pressure_and_combination_rules() -> None:
    limits = {
        "doubt-1@3": (2, 1),
        "doubt-2@3": (6, 3),
        "doubt-3@3": (12, 7),
        "deception@3": (20, 11),
    }
    input_kinds = {
        "reverseEntry", "blindEntry", "noRevision", "forcedCommitment"
    }
    allowed_pair = {"reverseEntry", "forcedCommitment"}
    saw_reverse_commitment = {"doubt-3@3": False, "deception@3": False}

    for preset_key, (budget, cap) in limits.items():
        for index in range(2_000):
            blueprint = build_blueprint(preset_key, f"v3-bounded-{index}")
            plans = blueprint.punishment_plans
            assert blueprint.schema_version == 6
            assert len(plans) <= cap
            assert sum(plan.pressure_cost for plan in plans) <= budget
            reverse_attempts = sorted(
                plan.effective_attempt
                for plan in plans if plan.kind == "reverseEntry"
            )
            assert all(
                right > left
                for left, right in zip(reverse_attempts, reverse_attempts[1:])
            )
            assert all(
                plan.effective_attempt in {3, 4, 5}
                for plan in plans if plan.kind == "blackout"
            )
            for attempt in range(1, 7):
                active = blueprint.punishments_for_effective(attempt)
                active_inputs = [
                    plan for plan in active if plan.kind in input_kinds
                ]
                input_set = {plan.kind for plan in active_inputs}
                assert len(active_inputs) <= 2
                if len(active_inputs) == 2:
                    assert input_set == allowed_pair
                    if preset_key in saw_reverse_commitment:
                        saw_reverse_commitment[preset_key] = True
                ten_second = any(
                    plan.kind == "timer"
                    and plan.config.get("durationSeconds") == 10
                    for plan in active
                )
                assert not (ten_second and len(active_inputs) == 2)

    assert all(saw_reverse_commitment.values())


def test_v3_reverse_blueprints_can_schedule_adjacent_distinct_events() -> None:
    saw_adjacent = False
    for index in range(2_000):
        blueprint = build_blueprint("deception@3", f"adjacent-reverse-{index}")
        attempts = sorted(
            plan.effective_attempt
            for plan in blueprint.punishment_plans
            if plan.kind == "reverseEntry"
        )
        if any(
            right - left == 1
            for left, right in zip(attempts, attempts[1:])
        ):
            saw_adjacent = True
            break

    assert saw_adjacent
