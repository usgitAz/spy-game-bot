# SpyFall Telegram Bot

A group-based word game bot for Telegram (Persian UI). One player is the **spy** and does not know the secret word; everyone else does. Players ask questions, vote, and try to find the spy — or the spy tries to guess the word.

Built with **Python 3.12**, **aiogram 3**, and **Redis**.

> Live version of this bot : [@spyfallgamerobot](https://t.me/spyfallgamerobot)

> Persian version of this document : [README.fa.md](README.fa.md)
---

## Features

### Gameplay

- **New game in groups** — `/newgame` opens a settings panel (round length, optional two-spy mode for 7+ players).
- **Lobby** — join, leave, delete game, read rules, start when enough players have joined.
- **Roles** — one spy by default (or two when enabled and the group is large enough); citizens see the word, spies do not.
- **In-round actions**
  - “See my role” button (private alert to the player only).
  - Spy can win **mid-round** by sending the **exact** word as a standalone message (no extra text).
- **Voting** — when the round timer ends, a voting panel is posted (not edited in place) so it stays visible at the bottom of the chat.
  - Only players still in the game can vote.
  - One vote per player; you cannot vote for yourself.
  - Vote announcements in the group.
  - Early resolve when everyone has voted; otherwise a voting timeout applies.
- **Tie handling** — if the top score is tied, a **second runoff** runs only among the tied players. If still tied, the game is a **draw**.
- **Spy voted out** — the spy gets a short window to guess the word exactly; correct guess → spy wins, otherwise citizens win.
- **Citizen voted out** — spies win immediately.

### Group & safety behavior

- **Bot must be a group admin** — commands and buttons are blocked until the bot is promoted (needed for leave detection and panel cleanup).
- **Player leaves the group**
  - Lobby: removed from the list; if the creator leaves, the lobby is deleted.
  - During the game: marked as left; last spy leaving → citizens win; fewer than the minimum active players → draw.
  - During final guess: if the eliminated spy leaves → citizens win.
- **Bot demoted or removed** — live game/lobby is cleared so the group is not stuck.
- **Admin force-reset** — group admins can run `/deletecurrentgame` to wipe the current game state for that chat.
- **Anti-spam** — short rate limits on inline buttons and heavy commands (`/newgame`, `/deletecurrentgame`, `/start`).
- **Timers & recovery** — lobby timeout, round timer, voting timeout, final-guess timeout; a background sweeper re-arms deadlines after process restarts (state lives in Redis).

### Operations

- **Redis-only live state** — no database required to run games today.
- **Structured JSON logging** to stdout, `logs/app.log`, and `logs/error.log` (rotating files).
- **Docker** support for local development and production-style deploys.
- **Word list** — editable text file (`data/words.txt`); one word per line or comma-separated entries.

---

## Requirements

- Docker & Docker Compose **or** Python 3.12+
- Redis 7+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

---

## Quick start (Docker)

1. Clone the repository and enter the project directory.

2. Create environment file:

   ```bash
   cp .env.example .env
   ```

   Set at least:

   ```env
   BOT_TOKEN=your_bot_token_here
   ```

3. Start services:

   **Development** (hot-reload, published Redis port, logs mounted):

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.local.yml up --build
   ```

   **Production-style**:

   ```bash
   docker compose up --build -d
   ```

4. Add the bot to a **Telegram group**, promote it to **administrator**, then run `/newgame`.

---

## Configuration

Values are read from environment variables (see `.env.example`).

| Variable | Default | Description |
|----------|---------|-------------|
| `BOT_TOKEN` | *(required)* | Telegram bot token |
| `TELEGRAM_PROXY` | — | Optional proxy URL for the Telegram API (see below) |
| `REDIS_HOST` | `redis` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_DB` | `0` | Redis database index |
| `MIN_PLAYERS` | `3` | Minimum players to start |
| `MAX_PLAYERS` | `10` | Maximum lobby size |
| `SPY_THRESHOLD_PLAYERS` | `7` | Player count at which two spies may apply |
| `LOBBY_TIMEOUT_SECONDS` | `300` | Auto-delete lobby if never started |
| `VOTING_TIMEOUT_SECONDS` | `60` | Voting phase duration |
| `FINAL_GUESS_SECONDS` | `30` | Spy’s final guess window after being voted out |
| `REDIS_GAME_TTL_SECONDS` | `3600` | Safety TTL for Redis game keys |
| `THROTTLE_CALLBACK_SECONDS` | `0.7` | Min interval between button taps per user |
| `THROTTLE_COMMAND_SECONDS` | `3.0` | Min interval for heavy commands per user |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `LOG_DIR` | `logs` | Directory for log files |
| `LOG_MAX_MB` | `20` | Max size of each rotated log file (megabytes) |
| `LOG_BACKUP_COUNT` | `3` | Number of rotated backups per log file |

### Telegram proxy (`TELEGRAM_PROXY`)

Use this **only** if Telegram is blocked or unreachable from your network (for example in some countries). Uncomment and set it in `.env`:

```env
TELEGRAM_PROXY=socks5://host.docker.internal:1080
```

(or another HTTP/SOCKS URL that works on your machine).

- **Local Docker:** `docker-compose.local.yml` maps `host.docker.internal` so the container can reach a proxy running on the host.
- **Production:** using a proxy is **not recommended**. It adds latency, can reduce reliability, and is harder to operate. Prefer hosting the bot where Telegram is reachable directly.
- If Telegram works without a proxy, leave `TELEGRAM_PROXY` unset.

PostgreSQL-related variables may exist for a **future** feature; they are **not required** to run the bot today (see [Planned: game history and stats](#planned-game-history-and-stats)).

---

## Commands

| Command | Where | Who | Description |
|---------|--------|-----|-------------|
| `/start` | Private or group | Anyone | Simple health check / intro |
| `/newgame` | Group only | Anyone (bot must be admin) | Open settings and create a lobby |
| `/deletecurrentgame` | Group only | Group admin / creator | Force-delete the active game or lobby for this chat |

All other actions use **inline buttons** (join, leave, start, vote, see role, settings).

---

## How a round works

1. Someone runs `/newgame` and confirms settings.
2. Players join the lobby; the creator starts when ready (and the minimum player count is met).
3. Roles and the secret word are assigned. Citizens use “See my role” to view the word; the spy only learns they are the spy.
4. Discussion runs until the round timer ends, unless the spy sends the exact word earlier and wins.
5. Voting opens. After votes (or timeout), the player with the most votes is eliminated.
6. Outcome depends on who was eliminated and any final guess — or a draw after a second tied runoff.

---

## Word list

Edit `data/words.txt`:

- One word per line, **or** several words separated by commas on one line
- Empty lines and lines starting with `#` are ignored
- Words may repeat across games (no per-group “already used” store)

Reload requires a process restart (or your own reload hook if you add one later).

---

## Logging

- **stdout** — JSON lines (Docker-friendly)
- **`logs/app.log`** — `LOG_LEVEL` and above, rotating
- **`logs/error.log`** — errors only, rotating

Mount `./logs` into the container (already set in Compose files) so files persist on the host.

---

## Project layout

```text
.
├── app/
│   ├── bot/              Bot & dispatcher bootstrap
│   ├── config/           Settings from environment
│   ├── domain/           Live game state models (Redis-backed)
│   ├── handlers/         Commands and callback handlers
│   ├── keyboards/        Inline keyboards and callback data
│   ├── middlewares/      Admin check, rate limiting
│   ├── models/           ORM models reserved for future archival (unused at runtime)
│   ├── repositories/     Redis game-state access
│   ├── services/         Game rules, timers, voting, leave handling
│   ├── states/           Legacy/alternate state definitions
│   ├── utils/            Logging, Redis client, Telegram helpers
│   ├── constants.py
│   └── main.py           Application entrypoint
├── data/
│   └── words.txt         Word bank
├── logs/                 Runtime logs (gitignored; created at run time)
├── migrations/           Alembic migrations (for future Postgres archival)
├── docker-compose.yml
├── docker-compose.local.yml
├── Dockerfile
├── Dockerfile.dev
├── alembic.ini
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── TODO.md
└── README.md
```

---

## Planned: game history and stats

Live games already run fully on **Redis**. Persisting finished games is **not enabled yet**.

A later update is planned to add:

- **PostgreSQL** storage for completed games (winner, end reason, word, players, roles)
- **User and group stats** (games played, wins, times as spy, and similar aggregates)
- Optional commands or panels to **show statistics** in a group or privately
- Turning on the existing ORM models under `app/models/` and Alembic migrations under `migrations/`

Until then:

- You do **not** need to start a Postgres service
- Game results are announced in the chat but **not** kept in a long-term database
- See `TODO.md` for a short implementation checklist when this work is picked up

---

## Development notes

- Live game state is stored in **Redis**, not only in process memory, so restarts can recover in-progress timers via stored deadlines.
- The bot should remain a **group administrator** while games are running; otherwise leave tracking and message cleanup will not work reliably.

---

## License

See [LICENSE](LICENSE) in the repository root.
