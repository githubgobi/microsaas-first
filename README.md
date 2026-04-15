# AI Error Debugger

A SaaS application that analyses API errors using AI. Paste an error, get an instant root cause analysis and fix suggestions.

**Stack:** FastAPI · PostgreSQL · SQLAlchemy 2 async · Alembic · Stripe · Vite + React · Docker

---

## Prerequisites

| Tool | Version |
|------|---------|
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | 4.x+ |
| [Docker Compose](https://docs.docker.com/compose/) | v2 (included with Docker Desktop) |
| [Node.js](https://nodejs.org/) | 18+ (frontend dev only) |

---

## Local Setup

### 1. Clone the repository

```bash
git clone <repo-url>
cd saas-first
```

### 2. Create the environment file

```bash
cp .env.example .env
```

Open `.env` and set the required values:

```env
# Required — generate a random secret key
SECRET_KEY=        # python -c "import secrets; print(secrets.token_hex(32))"

# Database — leave as-is for local Docker
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/saas_db

# Required for AI analysis
ANTHROPIC_API_KEY= # get from https://console.anthropic.com
```

Everything else is optional for local development:

| Variable | Default | Notes |
|----------|---------|-------|
| `SMTP_HOST` | *(empty)* | Leave empty — verification links print to app logs instead |
| `BILLING_ENABLED` | `false` | Set to `true` only if you add Stripe keys |
| `STRIPE_SECRET_KEY` | *(empty)* | Required only when `BILLING_ENABLED=true` |
| `STRIPE_WEBHOOK_SECRET` | *(empty)* | Required only when `BILLING_ENABLED=true` |
| `STRIPE_PRO_PRICE_ID` | *(empty)* | Required only when `BILLING_ENABLED=true` |
| `RATE_LIMIT_ENABLED` | `true` | Set to `false` to skip rate limiting in dev |
| `DEBUG` | `false` | Set to `true` to enable `/docs` and `/redoc` |

### 3. Start the application

```bash
docker compose up --build
```

This starts four services in order:

| Service | Description |
|---------|-------------|
| `db` | PostgreSQL 16 database |
| `migrate` | Runs `alembic upgrade head` — applies all migrations |
| `app` | FastAPI backend on port 8000 |
| `frontend` | Vite dev server on port 3000 |

Wait for output like:
```
migrate-1   | INFO  [alembic] Running upgrade  -> 15f7b1cc3061
migrate-1   | INFO  [alembic] Running upgrade 15f7b1cc3061 -> 3c7a9e2f1b84
migrate-1   | INFO  [alembic] Running upgrade 3c7a9e2f1b84 -> 5f8c2a7d4e1b
app-1       | {"event": "startup_complete", ...}
```

### 4. Open the app

| URL | Description |
|-----|-------------|
| http://localhost:3000 | Frontend (React) |
| http://localhost:8000/health | Backend health check |
| http://localhost:8000/docs | API docs (requires `DEBUG=true`) |

---

## Running the Frontend Separately

If you prefer to run the frontend outside Docker (faster hot reload):

```bash
cd frontend
npm install
npm run dev
```

The frontend reads `frontend/.env` for the API URL:

```bash
cp frontend/.env.example frontend/.env
# VITE_API_URL=http://localhost:8000
```

Make sure the backend is running (`docker compose up app db migrate`).

---

## Running Tests

```bash
docker compose run --rm test
```

This creates a separate test database, runs all migrations on it, then executes the full pytest suite.

To run a specific test file:

```bash
docker compose run --rm test pytest tests/auth/test_router.py -v
```

---

## Email Verification (Dev Mode)

With `SMTP_HOST` left empty, the app does not send real emails. Instead it prints the verification link directly to the app container logs:

```bash
docker compose logs app | grep verification
```

Copy the link and open it in your browser, or pass the token directly to the API.

---

## Adding a New Migration

After changing a model in `app/*/models.py`:

```bash
# Generate the migration file
docker compose run --rm migrate alembic revision --autogenerate -m "describe your change"

# Apply it
docker compose run --rm migrate alembic upgrade head
```

Commit the generated file in `alembic/versions/`.

---

## Stopping and Resetting

```bash
# Stop containers, keep the database volume
docker compose down

# Stop containers AND wipe the database (fresh start)
docker compose down -v
```

After `down -v`, run `docker compose up --build` again to rebuild and re-run all migrations from scratch.

---

## Project Structure

```
saas-first/
├── app/
│   ├── auth/          # Register, login, JWT, email verification, password reset
│   ├── errors/        # Error log CRUD
│   ├── analysis/      # AI analysis (Anthropic Claude)
│   ├── history/       # Analysis history
│   ├── billing/       # Stripe subscriptions (optional)
│   └── core/          # Exceptions, middleware, rate limiting, email
├── alembic/           # Database migrations
├── frontend/          # Vite + React frontend
│   └── src/
│       ├── api/       # Axios API clients
│       ├── pages/     # Route pages
│       ├── components/# Shared UI components
│       └── store/     # Zustand auth store
├── tests/             # pytest test suite
├── docker-compose.yml
├── Dockerfile
└── .env.example
```
