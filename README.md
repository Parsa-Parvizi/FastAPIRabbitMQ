# FastAPIRabbitMQ

A small learning project: **FastAPI + RabbitMQ (aio-pika) + SQLite (async SQLAlchemy) + Vue 3**, all served through a single port.

```
browser -> nginx :8080 --/--> Vue (static)
                       \-/api-> FastAPI -> RabbitMQ -> consumer -> SQLite
```

`POST /tasks` stores the task as `pending` in SQLite and publishes its id to the `tasks` queue. The consumer processes it and sets the status to `done` (or `failed`). The dashboard polls every 2 seconds.

## Quick start

```bash
docker compose up -d --build --wait
```

Open http://localhost:8080. Only port **8080** is published; RabbitMQ, the API and the consumer stay inside the Docker network.

## API (all under `/api`)

| Method | Path          | Description                          |
|--------|---------------|--------------------------------------|
| GET    | `/health`     | RabbitMQ connection status           |
| GET    | `/tasks`      | Last 20 tasks                        |
| POST   | `/tasks`      | `{"name": "...", "payload": {}}` -> 202 |
| GET    | `/tasks/{id}` | One task (404 if unknown)            |

OpenAPI spec: `curl.exe http://localhost:8080/api/openapi.json -o openapi.json`

## Project layout

```
app/        FastAPI app (main.py), consumer.py, db.py, mq.py
app/lab/    RabbitMQ experiments (topic exchange, retry + DLQ, DB snapshot)
frontend/   Vue 3 + Vite dashboard (built into an nginx image)
e2e/        Playwright tests against http://localhost:8080
tests/      pytest tests (unit + integration)
```

## Configuration

| Variable       | Default (in compose)                         | Used by        |
|----------------|----------------------------------------------|----------------|
| `RABBITMQ_URL` | `amqp://guest:guest@rabbitmq:5672/`          | api, consumer  |
| `QUEUE_NAME`   | `tasks`                                      | api, consumer  |
| `DATABASE_URL` | `sqlite+aiosqlite:////data/app.db`           | api, consumer  |
| `WORK_DELAY`   | `3` (seconds, simulates slow work)           | consumer       |

## Tests

```bash
pytest                      # unit tests (no Docker needed)
pytest -m integration       # real RabbitMQ, needs the debug ports (see below)
cd frontend && npm test     # Vitest
cd e2e && npm test          # Playwright, the stack must be running
```

Playwright uses the installed Microsoft Edge (`channel: 'msedge'`), so no browser download is needed.

## Development

```bash
# Frontend with hot reload (stack must be up; /api is proxied to :8080)
cd frontend && npm install && npm run dev      # http://localhost:5173

# Debug mode: also publishes 5672, 15672 (Management UI, guest/guest) and 8000
docker compose -f docker-compose.yaml -f docker-compose.dev.yaml up -d

# RabbitMQ lab
docker compose run --rm api python -m app.lab.topic_demo
docker compose run --rm api python -m app.lab.retry_demo

# Inspect the SQLite DB in PyCharm (a snapshot copy, not live)
docker compose exec api python -m app.lab.snapshot_db
docker compose cp api:/data/snapshot.db ./snapshot.db
```

## Cleanup

```bash
docker compose down        # stop, keep the database
docker compose down -v     # stop and delete the database
```