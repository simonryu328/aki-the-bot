# Setup Guide

## Prerequisites

- Python 3.11+
- Docker
- [uv](https://github.com/astral-sh/uv) package manager

## 1. Install Dependencies

```bash
pip install uv
uv sync
```

## 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:
- `TELEGRAM_BOT_TOKEN` - From [@BotFather](https://t.me/botfather)
- `OPENAI_API_KEY` - From OpenAI
- `ANTHROPIC_API_KEY` - From Anthropic
- `PINECONE_API_KEY` - From Pinecone
- `DATABASE_URL` - PostgreSQL connection string (default works with Docker setup below)

## 3. Start PostgreSQL with Docker

```bash
docker run -d \
  --name ai-companion-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=ai_companion \
  -p 5432:5432 \
  -v ai_companion_data:/var/lib/postgresql/data \
  postgres:16
```

Verify it's running:
```bash
docker ps
```

### Docker Commands Reference

```bash
# Stop
docker stop ai-companion-postgres

# Start
docker start ai-companion-postgres

# View logs
docker logs ai-companion-postgres

# Remove container (data persists in volume)
docker rm ai-companion-postgres

# Remove data volume (destructive)
docker volume rm ai_companion_data
```

## 4. Initialize Database

Create the required tables:

```bash
uv run python scripts/init_db_async.py
```

## 5. Run the Bot

Development mode (with hot reload):
```bash
uv run python dev.py
```

Production mode:
```bash
uv run python main.py
```

## Troubleshooting

### "password authentication failed"
The password in `.env` doesn't match the Docker container. Either:
- Update `DATABASE_URL` in `.env` to match the container password
- Recreate the container with the correct password (see step 3)

### "relation does not exist"
Run the database initialization script:
```bash
uv run python scripts/init_db_async.py
```

### "connection refused"
PostgreSQL container isn't running:
```bash
docker start ai-companion-postgres
```
