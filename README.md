# 104 Central Command Centre (CCC) — ticketing

Source pulled from the live server on **25 Aug 2026** so developers can run and
extend it locally.

Live: `cct.bhspl.in/ccc` — systemd unit `ccc.service`, uvicorn on `127.0.0.1:8092`
behind nginx, MySQL database `ccc`.

## What's in here

| Path | What it is |
|---|---|
| `app.py` | The entire backend — FastAPI, 511 lines, no other Python modules |
| `web/index.html` | The whole front end — one self-contained SPA, no build step |
| `schema.sql` | Structure-only dump of the `ccc` database (4 tables) |
| `requirements.txt` | Exact versions from the server's venv |
| `ccc.service` | The systemd unit as deployed |
| `.env.example` | Config template — **real secrets are not in this bundle** |

## Run it locally

```bash
python -m venv venv
venv/bin/pip install -r requirements.txt        # Windows: venv\Scripts\pip

mysql -u root -e "CREATE DATABASE ccc CHARACTER SET utf8mb4;"
mysql -u root ccc < schema.sql

cp .env.example ccc.env        # then edit it
set -a; . ./ccc.env; set +a    # Windows PowerShell: set each var manually

venv/bin/uvicorn app:app --host 127.0.0.1 --port 8092 --reload
```

Open <http://127.0.0.1:8092/> — `app.py` serves the SPA from `CCC_WEB`.
`GET /health` is a dependency-free liveness check.

`schema.sql` is structure-only, so you start with an empty database. Create your
first user directly in `ccc_user`; passwords are hashed by the same helper the
app uses (`hash_pw`), so generate the hash with the app's own function rather
than inserting a plaintext value.

## API surface

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness |
| GET | `/meta` | categories, priorities, TAT matrix |
| POST | `/auth` | login, returns a signed token |
| POST | `/intake` | **inbound tickets from the gov EHR / LIS** |
| POST | `/ticket` | create a ticket from the console |
| GET | `/tickets` | list / filter |
| GET | `/ticket/{tid}` | one ticket with its event trail |
| POST | `/ticket/action` | assign, escalate, resolve, close |
| GET | `/dashboard` | CC-Manager KPIs |
| GET | `/users` | roster |

`/intake` is the integration point — the gov EHR posts here via `CCC_TICKET_URL`.
Keep its request shape backward-compatible or the EHR side breaks.

## Tables

`ccc_ticket` · `ccc_event` (append-only audit trail) · `ccc_user` · `ccc_config`

## Notes before you change anything

- **Diagnosis and parts must survive a Resolve action.** They were silently
  dropped once, which breaches SOP §8. There is a regression test for it — do
  not remove it.
- Ticket routing and TAT come from the CCC SOP matrix in `/meta`, not from
  hardcoded values. Change the matrix, not the handlers.
- `ccc_event` is append-only. Never update or delete a row — the audit trail is
  the evidence that TAT was met.
- Every ticket in production is currently **OPEN** — no ticket has ever reached a
  closed state. Verify the close path end-to-end before trusting the dashboard.

## Security

`.env` is deliberately excluded. The live values are only on `cct.bhspl.in`
(`/opt/ccc/ccc.env`, mode 0600). Use your own throwaway credentials locally, and
do not point a local build at the production database.
