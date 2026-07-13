# Taxi Booking API (server-side)

FastAPI backend for bookings, auth, payments, Viator import, and the staff admin UI.

## Prerequisites

- Python **3.11** (see `.python-version`)
- MySQL **8.4** (local install or Docker)
- Docker + Docker Compose (optional, for MySQL)

## Setup

### 1. Create a virtual environment

From the `server-side` folder:

```bash
python -m venv .venv
```

Activate it:

```bash
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Edit `.env` as needed. Minimum for local development:

```env
APP_URL=http://localhost:8000
HOST=0.0.0.0
PORT=8000

DATABASE_HOST=127.0.0.1
DATABASE_PORT=3306
DATABASE_USER=taxi
DATABASE_PASSWORD=taxi
DATABASE_NAME=taxi_booking
```

Optional: set `JWT_SECRET` (required in production). In development a default is used if unset.

### 4. Start MySQL

**Option A — Docker Compose** (recommended):

```bash
# Create the shared network once (if it does not exist yet)
docker network create taxi-booking

docker compose up -d
```

This starts MySQL on host port `DATABASE_PORT` (default `3306`).

**Option B — existing MySQL:** create database/user to match `.env`, then continue.

### 5. Run database migrations

```bash
alembic upgrade head
```

If the schema was already applied by another tool (e.g. Prisma) and you only need Alembic to catch up:

```bash
alembic stamp head
```

### 6. Create a super admin (first time)

```bash
python -m scripts.create_admin
```

Answer `y` when asked for super admin. You need this account to sign in at `/my-portal`.

To promote an existing staff user later:

```bash
python -m scripts.promote_super_admin
```

## Start the application

With the venv activated, from `server-side`:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Or use values from `.env`:

```bash
uvicorn app.main:app --reload --host %HOST% --port %PORT%
```

(On macOS/Linux use `$HOST` / `$PORT`.)

### URLs

| What | URL |
|------|-----|
| API (versioned) | http://localhost:8000/api/v1 |
| OpenAPI docs | http://localhost:8000/docs |
| Staff admin UI | http://localhost:8000/my-portal |

Admin UI and admin APIs (`/my-portal`, `/api/v1/admin/*`, and staff-admin routes such as `/api/v1/logs`) are rate-limited to **300 requests per minute** per client IP.

Password sign-in (`POST /api/v1/auth/signin`) allows **5 failed attempts** per email. After that the account is locked for **15 minutes**; each later lockout adds another **15 minutes** (30, 45, …). A successful sign-in clears the counter.

To unlock without waiting (works while the API is running):

```bash
python -m scripts.clear_login_lockout admin@example.com
python -m scripts.clear_login_lockout --list
python -m scripts.clear_login_lockout --all
```

Admin uses the same API (`/api/v1/auth/signin`, bookings, logs). Sign in with the super-admin account you created above.

## Useful scripts

Run from `server-side` with the venv active:

```bash
python -m scripts.create_admin
python -m scripts.promote_super_admin
python -m scripts.clear_login_lockout
python -m scripts.set_admin_code
python -m scripts.set_driver_verification_code
python -m scripts.set_pricing_passcode
python -m scripts.seed_test_bookings
python -m scripts.maybe_migrate_deploy   # only if ALEMBIC_MIGRATE_ON_START=1
```

## Production notes

- Shared hosting (Passenger): entrypoint is `passenger_wsgi.py`.
- Set `APP_ENV=production` and a strong `JWT_SECRET`.
- Point `APP_URL` at your public API URL.
- Admin UI is served at `{APP_URL}/my-portal`.
- For Hostinger-style MySQL limits, see commented `DATABASE_*` options in `.env.example`.

## Troubleshooting

- **Cannot connect to MySQL:** confirm Docker is up (`docker compose ps`), and `DATABASE_HOST` / `DATABASE_PORT` match how you run the API (host vs container).
- **Admin login rejected:** account must be staff with `is_super_admin=true` (`create_admin` with `y`, or `promote_super_admin`).
- **Admin account locked:** run `python -m scripts.clear_login_lockout your@email.com` (or `--all`), then hard-refresh `/my-portal`.
- **Logs page empty / 503:** enable file logging (`LOG_FILE_ENABLED=true`, default on) and ensure `logs/` is writable.
- **Stale schema errors:** run `alembic upgrade head` again after pulling new migrations.
