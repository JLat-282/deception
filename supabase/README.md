# Supabase database setup

Apply the SQL files in `migrations/` in filename order:

1. `20260805144122_core_game_schema.sql`
2. `20260805144132_deception_mechanics.sql`
3. `20260805144143_daily_descent.sql`

For a new hosted Supabase project, open **SQL Editor**, paste the complete
contents of the first file, and run it. Repeat for the second and third files.
Stop if any file reports an error; do not continue to the next migration.

The migrations enable Row Level Security and grant no browser-facing policies.
The application accesses the tables only through FastAPI's trusted Postgres
connection. Do not put a Supabase secret key or database password in frontend
environment variables.

For Vercel runtime traffic, connect the Supabase Marketplace integration to the
Vercel project. It automatically supplies a pooled `POSTGRES_URL`, which this
application accepts directly. If you configure the connection manually instead,
store a pooled Postgres connection string with SSL enabled as `DATABASE_URL`.
`DATABASE_URL` takes precedence if both variables exist. Direct database
connections are intended for migrations and administration, not serverless
runtime traffic.
