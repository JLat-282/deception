begin;

alter table public.guesses
add column deception_diagnostics_json text;

commit;
