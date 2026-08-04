from __future__ import annotations

from dataclasses import FrozenInstanceError
import json

import pytest

from backend.app.difficulty import (
    BlueprintOverrides,
    GameBlueprint,
    build_blueprint,
    public_presets,
)


def test_preset_registry_exposes_all_four_versioned_levels() -> None:
    presets = public_presets()

    assert [preset.key for preset in presets] == [
        "doubt-1@1",
        "doubt-2@1",
        "doubt-3@1",
        "deception@1",
    ]
    assert [preset.available for preset in presets] == [True, True, True, True]
    assert presets[2].timer_count_weights == ((0, 0.15), (1, 0.55), (2, 0.30))
    assert presets[2].two_tile_probability == 0.25
    assert presets[2].max_reverse_events == 2
    assert presets[2].combination_policy == "limited"
    assert [preset.blackout_probability for preset in presets] == [
        0.0,
        0.20,
        0.45,
        0.80,
    ]
    assert presets[3].timer_count_weights == ((1, 0.25), (2, 0.45), (3, 0.30))
    assert presets[3].two_tile_probability == 0.50
    assert presets[3].false_victory_probability == 0.05
    assert presets[3].max_reverse_events == 3
    assert presets[3].combination_policy == "broad"


def test_blueprint_is_deterministic_canonical_and_immutable() -> None:
    first = build_blueprint("doubt-2@1", "stable-seed")
    second = build_blueprint("doubt-2@1", "stable-seed")

    assert first == second
    assert first.to_json() == second.to_json()
    encoded = json.loads(first.to_json())
    assert encoded["preset_key"] == "doubt-2@1"
    assert encoded["schema_version"] == 3
    assert encoded["false_victory_enabled"] is False
    with pytest.raises(FrozenInstanceError):
        first.preset_key = "doubt-1@1"  # type: ignore[misc]


def test_blueprint_decoder_rejects_unknown_schema_version() -> None:
    value = json.loads(build_blueprint("doubt-2@1", "stable-seed").to_json())
    value["schema_version"] = 4

    with pytest.raises(ValueError, match="Unsupported game blueprint schema"):
        GameBlueprint.from_json(json.dumps(value))


def test_blueprint_decoder_migrates_schema_two_without_false_victory() -> None:
    value = json.loads(build_blueprint("doubt-3@1", "legacy-seed").to_json())
    value["schema_version"] = 2
    value.pop("false_victory_enabled")

    restored = GameBlueprint.from_json(json.dumps(value))

    assert restored.schema_version == 3
    assert restored.false_victory_enabled is False


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
