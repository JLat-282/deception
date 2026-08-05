begin;

create table public.deception_schedules (
    id bigint generated always as identity primary key,
    daily_puzzle_key text references public.daily_puzzles(puzzle_key),
    game_id text references public.games(id),
    ordinal integer not null default 1 check (ordinal >= 1),
    scheduled_attempt integer not null
        check (scheduled_attempt between 1 and 6),
    seed text not null,
    strategy_version integer not null default 1
        check (strategy_version >= 1),
    created_at timestamptz not null,
    check (
        (daily_puzzle_key is not null and game_id is null)
        or (daily_puzzle_key is null and game_id is not null)
    ),
    unique (daily_puzzle_key, ordinal),
    unique (game_id, ordinal)
);

create unique index deception_schedules_daily_attempt_idx
on public.deception_schedules (daily_puzzle_key, scheduled_attempt)
where daily_puzzle_key is not null;

create unique index deception_schedules_game_attempt_idx
on public.deception_schedules (game_id, scheduled_attempt)
where game_id is not null;

create table public.reverse_entry_states (
    game_id text primary key references public.games(id),
    seed text not null,
    status text not null default 'armed'
        check (status in ('armed', 'active', 'consumed')),
    trigger_attempt integer check (trigger_attempt between 1 and 5),
    trigger_reason text check (trigger_reason in ('lowInformation', 'chance')),
    consumed_attempt integer check (consumed_attempt between 2 and 6),
    created_at timestamptz not null,
    updated_at timestamptz not null,
    check (
        (status = 'armed' and trigger_attempt is null
            and trigger_reason is null and consumed_attempt is null)
        or (status = 'active' and trigger_attempt is not null
            and trigger_reason is not null and consumed_attempt is null)
        or (status = 'consumed' and trigger_attempt is not null
            and trigger_reason is not null and consumed_attempt is not null)
    )
);

create table public.guess_timer_states (
    game_id text primary key references public.games(id),
    seed text not null,
    status text not null check (
        status in ('skipped', 'scheduled', 'active', 'completed', 'expired')
    ),
    scheduled_attempt integer check (scheduled_attempt between 2 and 6),
    duration_seconds integer check (duration_seconds in (10, 30)),
    starts_at timestamptz,
    deadline_at timestamptz,
    resolved_attempt integer check (resolved_attempt between 2 and 6),
    created_at timestamptz not null,
    updated_at timestamptz not null,
    check (
        (status = 'skipped' and scheduled_attempt is null
            and duration_seconds is null and starts_at is null
            and deadline_at is null and resolved_attempt is null)
        or (status = 'scheduled' and scheduled_attempt is not null
            and duration_seconds is not null and starts_at is null
            and deadline_at is null and resolved_attempt is null)
        or (status = 'active' and scheduled_attempt is not null
            and duration_seconds is not null and starts_at is not null
            and deadline_at is not null and resolved_attempt is null)
        or (status in ('completed', 'expired')
            and scheduled_attempt is not null and duration_seconds is not null
            and starts_at is not null and deadline_at is not null
            and resolved_attempt = scheduled_attempt)
    )
);

create table public.blackout_states (
    game_id text primary key references public.games(id),
    seed text not null,
    status text not null check (status in ('skipped', 'scheduled', 'activated')),
    scheduled_attempt integer check (scheduled_attempt between 3 and 5),
    activated_at timestamptz,
    created_at timestamptz not null,
    updated_at timestamptz not null,
    check (
        (status = 'skipped' and scheduled_attempt is null
            and activated_at is null)
        or (status = 'scheduled' and scheduled_attempt is not null
            and activated_at is null)
        or (status = 'activated' and scheduled_attempt is not null
            and activated_at is not null)
    )
);

create table public.reverse_entry_states_v2 (
    game_id text primary key references public.games(id),
    seed text not null,
    status text not null check (status in ('armed', 'active', 'consumed')),
    trigger_attempt integer check (trigger_attempt between 1 and 5),
    trigger_reason text check (trigger_reason in ('lowInformation', 'chance')),
    consumed_attempt integer check (consumed_attempt between 2 and 6),
    event_count integer not null default 0 check (event_count >= 0),
    max_events integer not null default 1 check (max_events >= 1),
    created_at timestamptz not null,
    updated_at timestamptz not null,
    check (event_count <= max_events)
);

create table public.guess_timer_events (
    game_id text not null references public.games(id),
    ordinal integer not null check (ordinal >= 1),
    seed text not null,
    status text not null check (
        status in ('skipped', 'scheduled', 'active', 'completed', 'expired')
    ),
    scheduled_attempt integer check (scheduled_attempt between 2 and 6),
    duration_seconds integer check (duration_seconds in (10, 30)),
    starts_at timestamptz,
    deadline_at timestamptz,
    resolved_attempt integer check (resolved_attempt between 2 and 6),
    created_at timestamptz not null,
    updated_at timestamptz not null,
    primary key (game_id, ordinal),
    unique (game_id, scheduled_attempt)
);

alter table public.deception_schedules enable row level security;
alter table public.reverse_entry_states enable row level security;
alter table public.guess_timer_states enable row level security;
alter table public.blackout_states enable row level security;
alter table public.reverse_entry_states_v2 enable row level security;
alter table public.guess_timer_events enable row level security;

revoke all privileges on table
    public.deception_schedules,
    public.reverse_entry_states,
    public.guess_timer_states,
    public.blackout_states,
    public.reverse_entry_states_v2,
    public.guess_timer_events
from anon, authenticated;

revoke all privileges on sequence public.deception_schedules_id_seq
from anon, authenticated;

commit;
