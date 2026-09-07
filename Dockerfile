# --- Builder stage: install dependencies into a virtualenv ---
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Final stage: copy only the venv and source code ---
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/venv/bin:$PATH" \
    LOG_DIR=/app/logs

# Non-root user for the bot process (entrypoint drops to this user).
RUN groupadd -r spybot && useradd -r -g spybot spybot

WORKDIR /app

COPY --from=builder /venv /venv
COPY app ./app
COPY data ./data
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
COPY docker-entrypoint.sh /docker-entrypoint.sh

RUN chmod +x /docker-entrypoint.sh \
    && mkdir -p /app/logs \
    && chown -R spybot:spybot /app/logs

# Start as root so the entrypoint can chown the mounted logs volume,
# then it switches to user ``spybot`` before running the bot.
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["python", "-m", "app.main"]
