begin;

create table public.daily_descent_puzzles (
    puzzle_key text not null,
    stage_index integer not null check (stage_index between 1 and 4),
    preset_key text not null,
    answer text not null check (char_length(answer) = 5),
    answer_list_version text not null,
    blueprint_json text,
    created_at timestamptz not null,
    primary key (puzzle_key, stage_index),
    unique (puzzle_key, answer)
);

create table public.daily_descent_runs (
    device_id text not null references public.devices(id),
    puzzle_key text not null,
    status text not null check (
        status in (
            'unstarted', 'active', 'checkpoint', 'failed',
            'forfeited', 'completed', 'expired'
        )
    ),
    current_stage integer not null check (current_stage between 1 and 4),
    continuation_hash text,
    created_at timestamptz not null,
    updated_at timestamptz not null,
    primary key (device_id, puzzle_key)
);

create table public.daily_descent_stages (
    device_id text not null,
    puzzle_key text not null,
    stage_index integer not null check (stage_index between 1 and 4),
    game_id text not null unique references public.games(id),
    status text not null
        check (status in ('ready', 'active', 'won', 'lost', 'forfeited')),
    consumed_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz not null,
    updated_at timestamptz not null,
    primary key (device_id, puzzle_key, stage_index),
    foreign key (device_id, puzzle_key)
        references public.daily_descent_runs(device_id, puzzle_key)
);

alter table public.daily_descent_puzzles enable row level security;
alter table public.daily_descent_runs enable row level security;
alter table public.daily_descent_stages enable row level security;

revoke all privileges on table
    public.daily_descent_puzzles,
    public.daily_descent_runs,
    public.daily_descent_stages
from anon, authenticated;

commit;
