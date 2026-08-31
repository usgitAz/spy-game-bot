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
    PATH="/venv/bin:$PATH"

# Create a non-root user to run the bot process
RUN groupadd -r spybot && useradd -r -g spybot spybot

WORKDIR /app

COPY --from=builder /venv /venv
COPY app ./app
COPY data ./data
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini

USER spybot

CMD ["python", "-m", "app.main"]
