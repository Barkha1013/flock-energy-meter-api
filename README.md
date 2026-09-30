# Flock Meter Data API

A documented FastAPI service that reads meter, distribution-transformer, network-hierarchy, and energy data from Urja Meter Ops. It keeps the bulk meter and transformer snapshot in SQLite. Recent energy readings are fetched from the portal when requested and cached locally. API consumers can query the service without opening the portal.

## Current portal-backed behavior

The service uses the portal's observed read endpoints. Run the included sync command once to populate meters, coordinates, nameplate fields, network hierarchy, and transformers. The readings endpoint fetches the selected meter's recent half-hourly registers from the portal and stores them in SQLite. If the portal is temporarily unavailable, it returns cached readings with `X-Data-Stale: true` when a cache exists.

Portal credentials are read only from local environment variables. They are not stored in this repository. No portal meter records or exported dataset are committed.

## Project layout

- `app/main.py`: FastAPI app and application lifecycle.
- `app/api.py`: documented, versioned HTTP routes.
- `app/portal_client.py`: portal session, signed export, transformer paging, and energy reads.
- `app/sync.py`: maps the portal snapshot into SQLite; also provides the `python -m app.sync` command.
- `app/services.py`: source timestamp normalization and cached-reading upserts.
- `app/repositories.py`: SQLite query functions.
- `app/models.py` and `app/database.py`: relational read model and sessions.
- `app/schemas.py`: public response schemas.
- `PROTOCOL.md`: observed portal navigation, endpoints, and quirks.
- `openapi.json`: generated OpenAPI 3.1 contract.

## Requirements and setup

- Python 3.11 or newer
- Network access to the portal
- The portal username and password supplied for the assignment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
Copy-Item .env.example .env
```

Edit `.env` locally and set `PORTAL_USERNAME` and `PORTAL_PASSWORD`. Keep `.env` private; it is ignored by Git. The service defaults to `sqlite:///./data/meters.db` and creates the `data/` directory automatically.

Sync the portal snapshot, then run the API:

```powershell
python -m app.sync
uvicorn app.main:app --reload
```

The sync command reads the portal's signed all-meter export and all pages of the transformer list. It does not write to the portal. Meter readings are loaded on demand by the API. Run `python -m app.sync` again to refresh the meter and transformer snapshot.

The API listens at `http://127.0.0.1:8000`. Interactive docs are at `/docs` and `/redoc`; the live schema is at `/openapi.json`. Regenerate the checked-in contract with:

```powershell
python scripts/export_openapi.py
```

## API

All data routes use `/api/v1`. The list routes use offset pagination with default `limit=50` and maximum `limit=200`. Reading timestamps accept timezone-qualified ISO 8601 values and are returned in UTC (`Z`). Portal timestamps are displayed in Jaipur local time and converted to UTC for storage.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Service availability |
| `GET` | `/api/v1/meters` | Search and filter synchronized meters |
| `GET` | `/api/v1/meters/{meter_id}` | Meter nameplate, coordinates, and full network path |
| `GET` | `/api/v1/transformers` | Distribution transformers, optionally filtered by `feeder_code` |
| `GET` | `/api/v1/meters/{meter_id}/readings` | Recent energy registers, optionally bounded by `start` and `end` |

Meter filters include `search` (meter ID or serial substring), `install_status`, `make`, `phase_type`, and `dt_code`. Readings are ordered newest first; their default limit is 100 and maximum is 1000. Missing meter IDs return HTTP 404. If portal access is unavailable and no readings are cached, the readings route returns HTTP 502; when cached data is available, it returns that data with `X-Data-Source: sqlite-cache` and `X-Data-Stale: true`.

### Example request

```http
GET /api/v1/meters?install_status=Installed&limit=20
GET /api/v1/meters/{meter_id}/readings?start=2025-01-01T00:00:00Z&limit=48
```

An energy response has this shape (illustrative values):

```json
[
  {
    "recorded_at": "2025-01-01T00:00:00Z",
    "kwh": 1234.5,
    "kvah": 1400.0,
    "voltage_r": 230
  }
]
```

Portal `kWh` and `kVAh` values are cumulative register readings, not interval usage. A consumer that needs interval consumption should calculate the difference between adjacent readings and account for meter resets or rollovers.

## Design decisions and assumptions

- **SQLite is the local read model.** It keeps evaluation and single-machine setup simple. SQLAlchemy separates persistence from HTTP routes; PostgreSQL is a reasonable next step for concurrent production workloads.
- **Bulk export for meter metadata.** The portal exposes a signed export containing all 403 meters, which avoids walking 21 UI pages. The API sync maps its nameplate, geo, and hierarchy data into relational tables.
- **Read energy on demand.** Energy is exposed by a per-meter portal endpoint. Fetching it only when requested avoids making hundreds of requests during initial setup; successful responses are cached in SQLite.
- **Keep all hierarchy branches.** Codes repeat under different parents in the export. Database node IDs therefore include the full ancestor path; a bare code is not treated as globally unique.
- **Normalize time once.** Portal timestamps are shown as local Jaipur time, so the adapter interprets unzoned portal timestamps as `Asia/Kolkata`, converts them to UTC, and emits UTC in the API.
- **Keep source and API field names separate.** Portal names such as `serialNo`, `installStatus`, `voltR`, and `capacityKva` are mapped to readable API names.
- **Bound results.** List and readings endpoints have explicit page/row limits. Offset pagination is simple at the portal's current data size; cursor pagination is a future option for rapidly changing larger datasets.

## Security and operating limits

- The API currently has no consumer authentication. Keep it bound to a trusted network or add OIDC/API-key protection before exposing it beyond a local or private environment.
- The sync command and readings route use portal credentials from `.env`; do not commit that file, browser cookies, signing secrets, or portal exports.
- The service only calls portal sign-in and documented/read-only data endpoints. It does not modify portal records.
- SQLite is appropriate for this small assignment dataset and one API process. Use a server database and coordinated background sync before scaling to multiple workers.

## Intentionally left out

- A scheduled sync worker: refreshing the bulk snapshot is an explicit CLI action so freshness is visible and easy to control.
- A map, anomaly detection, and cache expiry policy: these need product decisions about location use, anomaly definitions, and acceptable staleness.
- Authentication for API consumers: no identity requirements were specified, so the README warns against public deployment without adding a guessed scheme.
- Automated tests: the take-home prioritizes investigation and reasoning. The OpenAPI document is generated from the live FastAPI route/schema definitions.

## Reflection

### What assumptions did you make?

I assumed the portal's Jaipur timestamps use India Standard Time, the bulk export is the authoritative meter snapshot, and the `kWh`/`kVAh` columns are cumulative register values. The portal UI and export were inspected to confirm field names; hierarchy node identity is path-scoped because codes repeat across branches.

### Which part was most difficult, and how did you get unstuck?

The difficult part was moving from the visible portal to its read protocol. I inspected the authenticated meter and transformer pages, used the normal bulk export, and read the page's bundled client code to identify the data routes and request-signing format. The implemented client then retrieved 403 meters, 40 transformers, and 337 readings for one meter without putting source data in the repository.

### If you had another day, what would you improve?

I would add automated tests using sanitized fixtures, measure API freshness under portal timeouts, add a scheduled sync with clear freshness reporting, and add an authentication scheme before deployment to a shared network.

### What mistake did you make while solving this?

I initially treated the assignment's broad data categories as if they were verified portal fields. During integration I also missed the same-origin `Origin` header required by the sign-in form, which caused an initial 403. I corrected the request after comparing it with the browser action and then fetched the portal records successfully.

### If you were reviewing your own submission, what would you criticise?

The adapter has been exercised against the portal's sign-in, bulk export, transformer pages, and one meter's recent energy response. It still needs automated tests, consumer authentication, and a scheduled freshness policy before production use.

## Further reading

- [Portal protocol investigation](PROTOCOL.md)
- [OpenAPI 3.1 contract](openapi.json)
