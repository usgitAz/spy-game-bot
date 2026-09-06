# TODO

## Postgres archival & stats (deferred)

**Status:** cancelled for now — do **not** start a Postgres service.

The bot runs on **Redis only** for live games (lobby, roles, votes, timers).

When re-enabling later:

1. Bring back `postgres` in `docker-compose` (if used).
2. Restore startup check in `app/main.py` (`get_engine()` + ping).
3. Restore `app/utils/db.py` SQLAlchemy engine/session helpers.
4. On `end_game`, write:
   - `games` row (winner, end_reason, word, timings)
   - `game_players` rows (role, eliminated, left_mid_game, …)
   - upsert `users` / `groups` and increment stats
5. Run Alembic migrations against a real database.
6. Optional: `/stats` commands.

ORM models under `app/models/` are kept as the planned schema; they are
unused at runtime until this stage is implemented.
