# SmartCampus

Monorepo: **FastAPI** backend (`backend/`) and **React** frontend (`frontend/`). Production Postgres is supported via `DATABASE_URL` or `DB_*_PSQL` (see `backend/.env.example`).

## Hosting on Render

You can deploy with the dashboard only, or use the included Blueprint file `render.yaml`.

### Option A — Blueprint (recommended)

1. Push this repo to GitHub (or GitLab / Bitbucket) and connect it in [Render](https://dashboard.render.com).
2. **New → Blueprint** → select the repo. Render reads `render.yaml` and creates:
   - **PostgreSQL** `smartcampus-db`
   - **Web service** `smartcampus-api` (FastAPI, `rootDir: backend`)
   - **Static site** `smartcampus-web` (CRA build from `frontend/`)
3. In the Render dashboard, open **smartcampus-web → Environment** and set:
   - `REACT_APP_API_URL` = your API URL, e.g. `https://smartcampus-api.onrender.com` (no trailing slash). Redeploy the static site after saving.
4. On **smartcampus-api**, set any optional secrets you use locally (ThingsBoard, SMTP). The blueprint already wires `DATABASE_URL`, generates `SECRET_KEY` and `IOT_INGEST_API_KEY`, and prompts for ThingsBoard env vars (`sync: false`).
5. First deploy: tables are created on API startup (`create_all` + `ensure_schema` in `main.py`). Create an admin user via Render **Shell** on the API service, e.g. run your existing seed script or insert into `users` if you have one.

**Health check:** the API exposes `GET /health` (configured in `render.yaml`).

**Python version:** `backend/runtime.txt` pins the native Python runtime for Render.

### Option B — Manual (two services + database)

1. **New → PostgreSQL** — note the internal **Database URL**.
2. **New → Web Service** — same repo, **Root Directory** `backend`.
   - **Build:** `pip install -r requirements.txt`
   - **Start:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Environment:** paste `DATABASE_URL` from the database (or use Render’s “Link database”). Set `SECRET_KEY`, `IOT_INGEST_API_KEY`, and optional `THINGSBOARD_*` / SMTP vars from `backend/.env.example`.
3. **New → Static Site** — **Root Directory** `frontend` (or build from repo root with `cd frontend && npm install && npm run build`).
   - **Build command:** `npm install && npm run build`
   - **Publish directory:** `build` (if root is `frontend`) **or** from repo root use `frontend/build` and a build command that builds into that tree.
   - Set **`REACT_APP_API_URL`** to the Web Service URL before building (change env → **Clear build cache & deploy** if the URL was wrong on first build).

### Notes

- **ThingsBoard:** the API calls ThingsBoard over HTTPS (`THINGSBOARD_BASE_URL`). Use [ThingsBoard Cloud](https://thingsboard.cloud) or any **publicly reachable** ThingsBoard instance; a ThingsBoard instance only on your laptop cannot be reached by Render unless you expose it (tunnel / VPS).
- **Free tier:** Web services can spin down when idle; first request may be slow (cold start).
- **Uploads:** user uploads live on the service filesystem and are **not** persisted across redeploys unless you add external storage (e.g. S3) later.

## Local development

- Backend: from `backend/`, install `requirements.txt`, copy `.env.example` to `.env`, run `uvicorn main:app --reload`.
- Frontend: from `frontend/`, set `REACT_APP_API_URL=http://localhost:8000` in `.env` (optional; defaults to localhost), then `npm start`.

## Database schema

SQLAlchemy models live in `backend/app/models.py`. Migrations and one-off SQL helpers are under `backend/migrations/`.

| Table | Purpose |
| --- | --- |
| `users` | Accounts: name, email, phone, role, is_active, profile_photo, hashed_password, year_of_study, department, membership_tier, timestamps |
| `campuses` | Campus name, location |
| `buildings` | name, `campus_id` |
| `floors` | `building_id`, `floor_no` |
| `facility_types` | Enum: mens_hostel, ladies_hostel, dining, sports, academic_spaces |
| `other_areas` | Non-hostel facilities: name, building/floor, capacity, facility_type, active, staff_only, eligibility_rules (JSON) |
| `hostel_rooms` | roomno, room_type, facility_type, building/floor, inmate_profiles (JSON), room_capacity, staff_only, eligibility_rules |
| `bookings` | user, time range, status, priority, hostel_room or other_area, meal fields, dining_menu_item_ids, inventory_selections (JSON) |
| `dining_menu_items` | Per dining `other_area`: meal_slot, name, description, diet, active |
| `facility_inventory_items` | Stock per `facility_scope` + `facility_id` |
| `room_allocations` | Hostel: `room_id`, `student_id`, `allocation_date` |
| `sensor_readings` | IoT: facility_id, facility_scope, facility_name, sensor_type, value, timestamp, optional ThingsBoard ids/ts |
| `sensor_alerts` | Threshold alerts: facility, sensor, alert_type, reading_value, names, triggered_at, status |
| `notifications` | Per user: title, body, category, read, created_at |
| `maintenance_schedules` | Planned work: title, notes, optional room/area, window, status, created_by |
| `maintenance_tickets` | Reports: reporter, title, description, optional room/area, status, photo_paths (JSON), timestamps |

For exact column types and constraints, see `backend/app/models.py`. New DB migrations should be added under `backend/migrations/` and referenced here when they change the schema.
