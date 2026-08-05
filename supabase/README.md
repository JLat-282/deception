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

For Vercel runtime traffic, copy the **Transaction pooler** connection string
from Supabase's **Connect** dialog. It normally uses port `6543`. Replace the
password placeholder, ensure SSL is enabled, and store the result as
`DATABASE_URL` in Vercel. The direct connection is intended for migrations and
administration, not the serverless runtime.
