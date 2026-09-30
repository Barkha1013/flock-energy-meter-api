# Flock Meter Data API

A small FastAPI service that gives engineers a stable, documented way to query normalized smart-meter records. It stores meter identity, network placement, and consumption readings in SQLite. The HTTP API is read-oriented; a separate import route is the seam for loading a portal snapshot into the local database.

> **Integration status:** the assignment portal's public sign-in page was reachable during this work, but its sign-in POST returned HTTP 403 from the inspection environment. Authenticated screens, source endpoints, and real field names could not be verified. This repository therefore does not claim to be a working portal scraper. `PROTOCOL.md` records what was observed and what remains to investigate. The service can be run and evaluated with normalized data supplied to its import endpoint.

## What is included

- `app/main.py` creates the FastAPI app and database tables; `app/api.py` defines HTTP routes; `app/schemas.py` validates public input/output; `app/services.py` owns the import transaction; `app/repositories.py` contains read queries; `app/models.py` and `app/database.py` define persistence; `app/config.py` reads settings.
- `scripts/export_openapi.py` writes the generated schema to the repository root.
- `PROTOCOL.md` explains the observed portal behavior and the unverified parts of the integration.
- `openapi.json` is the generated OpenAPI 3.1 contract for this service.
- SQLite is created automatically at `./data/meters.db` by default.

## Requirements

- Python 3.11 or newer
- `pip` (or another installer that reads `pyproject.toml`)

## Install and run

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -e .
uvicorn app.main:app --reload
```

The server listens at `http://127.0.0.1:8000`. Browse `/docs` for interactive Swagger UI, `/redoc` for ReDoc, and `/openapi.json` for the live schema. Copy `.env.example` to `.env` to set the SQLite path; the app reads `.env` at startup. The checked-in `openapi.json` can be refreshed with:

```bash
python scripts/export_openapi.py
```

To store the database elsewhere, set `DATABASE_URL`, for example `sqlite:///./data/local.db`. The configured directory must be writable. The application creates the default `data/` directory automatically; create a custom database's parent directory before starting if it does not exist:

```bash
mkdir data
```

## API overview

All data endpoints use `/api/v1`. Reading timestamps must be timezone-qualified ISO 8601 values. Imports normalize them to UTC, and responses return UTC with a `Z` suffix. Confirm the portal's source timezone before mapping its timestamps.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Process-level availability check |
| `GET` | `/api/v1/meters` | List meters with optional `status`, `network_node_id`, `limit`, and `offset` |
| `GET` | `/api/v1/meters/{meter_id}` | Meter fields and its network node |
| `GET` | `/api/v1/meters/{meter_id}/readings` | Consumption readings, optionally bounded by inclusive `start` and `end` timestamps |
| `POST` | `/api/v1/imports` | Upsert a normalized snapshot into SQLite |

The list response includes `items`, `total`, `limit`, and `offset`. The default page size is 50 and the maximum is 200. Reading results are newest first; the default limit is 100 and maximum is 1000. Missing meter IDs return HTTP 404. `POST /imports` exists for local ingestion and adapter development; it is not a portal write operation and should be protected with authentication before deployment. A network node's parent must exist already or be included in the batch; the importer orders same-batch parents automatically and rejects cycles or missing parents.

### Sample request

With records loaded, request the newest readings for a meter:

```http
GET /api/v1/meters/MTR-001/readings?start=2026-01-01T00:00:00Z&limit=24
```

Example response shape (illustrative values, not portal data):

```json
[
  {"recorded_at": "2026-01-01T00:00:00Z", "consumption_kwh": 0.42},
  {"recorded_at": "2025-12-31T23:00:00Z", "consumption_kwh": 0.38}
]
```

Load normalized records by posting a JSON body to `/api/v1/imports`. Example:

```json
{
  "network_nodes": [
    {"id": "feeder-7", "name": "Feeder 7", "node_type": "feeder", "parent_id": null}
  ],
  "meters": [
    {
      "id": "MTR-001", "serial_number": "SN-001", "status": "active",
      "meter_type": "smart", "latitude": 12.97, "longitude": 77.59,
      "installed_on": "2025-01-15", "network_node_id": "feeder-7",
      "readings": [{"recorded_at": "2026-01-01T00:00:00Z", "consumption_kwh": 0.42}]
    }
  ]
}
```

## Data model and design choices

- **SQLite** keeps local setup simple and is sufficient for a take-home-sized, single-instance read service. SQLAlchemy isolates persistence so PostgreSQL can replace it if concurrent ingestion or larger workloads require it.
- **Three entities** keep meter attributes, network hierarchy, and time-series readings separate. A reading is unique per meter and timestamp; re-import updates a matching reading rather than duplicating it.
- **Stable IDs** are strings because external portal identifiers may not be numeric. IDs and attributes are a proposed normalized contract and must be mapped against the authenticated portal before production use.
- **Small layers** separate HTTP validation (`schemas.py`/`api.py`), query construction (`repositories.py`), transaction behavior (`services.py`), and storage (`models.py`/`database.py`). This keeps the future portal client replaceable without coupling it to HTTP response formats.
- **Pagination and bounded readings** prevent an accidental request from returning an unbounded history. The API uses offset pagination for simplicity; cursor pagination would be safer for frequently changing large datasets.

## Assumptions

- The service should expose meter details, network placement, and recent consumption because these are the data categories named in the assignment background.
- The local SQLite database is a normalized read model. A source-specific ingestion adapter should map portal fields into the import shape.
- Meter identifiers are unique; a timestamp identifies at most one reading per meter; consumption is non-negative and measured in kWh.
- No production identity or authorization scheme was specified. This local prototype has no read-endpoint authentication and must not be exposed publicly as-is. Protect both read and import access before deployment.
- The source timezone and reading interval are unknown. API consumers should use timezone-qualified timestamps until the portal's actual conventions are established.

## Intentionally left out

- **Portal login/session client and synchronization job:** authentication succeeded nowhere in the inspection environment; implementing a guessed session or parser would create a misleading integration. `PROTOCOL.md` lists the evidence and next discovery steps.
- **Real portal data or fabricated seed rows:** the database starts empty. The sample payload is only an API shape illustration.
- **Authentication, role-based access, rate limits, and deployment configuration:** these need the utility's identity, network, and operational requirements. Do not put portal credentials in source control.
- **Map, anomaly detection, cache, and background scheduling:** useful follow-on features, but they depend on verified coordinates, data volume, and refresh semantics.

## Improvements with more time

1. Inspect the authenticated portal in a supported browser session; record exact navigation, network requests, field names, units, timezone, paging behavior, and session expiry.
2. Build a narrowly scoped read-only portal client with explicit timeouts, bounded retries, session refresh, and clear source errors; map its results into the normalized model.
3. Add automated contract, repository, and endpoint tests, plus fixture-based tests for malformed and inconsistent source records.
4. Add API-key or OIDC authentication, audit logs, request limits, and deployment health/readiness checks.
5. Move to PostgreSQL and cursor pagination if the dataset or concurrent read/write workload outgrows SQLite; add a measurable freshness policy before caching.

## Reflection

### What assumptions did you make?

I treated the assignment's named data categories as the initial domain and modeled meters, network nodes, and timestamped kWh readings. I assumed stable string identifiers and one reading per meter at a timestamp. I did not assume the portal's actual fields, hierarchy labels, unit conventions, or refresh cadence because I could not reach an authenticated screen.

### Which part was most difficult, and how did you get unstuck?

The hard part was distinguishing the API we can design from the undocumented behavior we need to discover in the legacy portal. I inspected the public sign-in page and attempted its normal form submission with the supplied take-home credentials. The hosted instance returned 403 on that request, so I stopped short of guessing hidden routes and wrote the integration boundary and evidence into `PROTOCOL.md`.

### If you had another day, what would you improve?

I would repeat portal discovery in an approved interactive session, then implement and fixture-test the smallest read-only synchronization path. After verifying source semantics, I would add authentication, freshness reporting, and an automated test suite.

### What mistake did you make while solving this?

I initially treated the assignment's description of meter, network, and consumption data as sufficient to shape the API. Those categories describe the product need, not verified portal fields. I corrected the documentation to label the schema as a proposal and the integration as incomplete.

### If you were reviewing your own submission, what would you criticise?

The central risk is that this is a well-shaped API and local data store, not a proven end-to-end bridge to the running portal. It also lacks automated tests and authentication, and its timestamp handling needs a confirmed source timezone before consumers rely on time-range queries.

## Further reading

- [Portal investigation and protocol notes](PROTOCOL.md)
- [OpenAPI 3.1 contract](openapi.json)
