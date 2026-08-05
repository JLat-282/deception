begin;

create table public.devices (
    id text primary key,
    created_at timestamptz not null
);

create table public.daily_puzzles (
    puzzle_key text primary key,
    answer text not null check (char_length(answer) = 5),
    blueprint_json text,
    answer_list_version text not null,
    created_at timestamptz not null
);

create table public.games (
    id text primary key,
    device_id text not null references public.devices(id),
    mode text not null check (mode in ('daily', 'practice')),
    puzzle_key text,
    answer text not null check (char_length(answer) = 5),
    status text not null default 'playing'
        check (status in ('playing', 'won', 'lost')),
    guess_count integer not null default 0
        check (guess_count between 0 and 6),
    created_at timestamptz not null,
    updated_at timestamptz not null,
    rules_version integer not null default 1 check (rules_version >= 1),
    preset_key text not null default 'doubt-2@1',
    blueprint_json text
);

create index games_device_mode_created_idx
on public.games (device_id, mode, created_at desc);

create table public.daily_attempts (
    device_id text not null references public.devices(id),
    puzzle_key text not null,
    game_id text not null unique references public.games(id),
    consumed_at timestamptz,
    created_at timestamptz not null,
    primary key (device_id, puzzle_key)
);

create table public.guesses (
    id bigint generated always as identity primary key,
    game_id text not null references public.games(id),
    attempt integer not null check (attempt between 1 and 6),
    guess text not null check (char_length(guess) = 5),
    truth_feedback text not null,
    display_feedback text not null,
    deception_reason text not null default 'legacy_unknown',
    created_at timestamptz not null,
    unique (game_id, attempt)
);

alter table public.devices enable row level security;
alter table public.daily_puzzles enable row level security;
alter table public.games enable row level security;
alter table public.daily_attempts enable row level security;
alter table public.guesses enable row level security;

revoke all privileges on table
    public.devices,
    public.daily_puzzles,
    public.games,
    public.daily_attempts,
    public.guesses
from anon, authenticated;

revoke all privileges on sequence public.guesses_id_seq
from anon, authenticated;

commit;
