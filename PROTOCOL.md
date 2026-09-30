# Urja Meter Ops protocol notes

These notes describe the live portal pages and read requests inspected for the take-home. The portal was used in read-only fashion. No real meter export or portal credentials are included in this repository.

## Pages and navigation

- The base URL sends an unauthenticated visitor to `/login`.
- The sign-in page is a SvelteKit form with `email` and `password` fields. Its browser action submits a `POST /login` request with `x-sveltekit-action: true`; a successful session is then represented by the browser's session cookie.
- After sign-in, the navigation exposes `/meters` and `/transformers`.
- `/meters` displays a 403-meter total, 20 rows per page, and a search box. Rows show meter ID, serial number, make, phase type, installation status, and distribution-transformer code.
- Selecting a meter opens `/meters/{meterId}`. The page shows nameplate details, its seven-level network path, coordinates, and recent energy readings.
- `/transformers` lists distribution transformer code, name, feeder code, and capacity in kVA. It is paginated and includes an **Export all meters** action.

## Observed data fields

The meter export contains objects with these source fields:

| Source field | Observed meaning |
|---|---|
| `meterId` | Meter identifier |
| `serialNo` | Serial number |
| `make` | Manufacturer |
| `phaseType` | `single` or `three` |
| `installStatus` | Values observed include `Installed`, `Faulty`, and `Decommissioned` |
| `installType` | Installation type, such as `Whole Current` |
| `build` | Portal-provided meter build value |
| `dtCode` | Distribution-transformer code |
| `hierarchy` | Objects for `zone`, `circle`, `division`, `subdivision`, `substation`, `feeder`, and `dt`; each has `name` and `code` |
| `geo` | `lat` and `lng` coordinates |

Transformer rows use `code`, `name`, `feederCode`, and `capacityKva`. Meter energy rows use `timestamp`, `kwh`, `kvah`, and `voltR`. The displayed kWh and kVAh values increase as register readings, so the API preserves them as meter registers instead of describing them as interval consumption. The detail page shows recent readings at 30-minute intervals.

## Read routes used by the portal UI

The page's bundled client code calls these routes:

| Request | Response use |
|---|---|
| `GET /portal/meters/search?q={query}&page={n}` | Meter table results with `data` and `total`; the UI uses pages of 20. |
| `GET /portal/dts?page={n}` | Transformer table results with `data` and `total`; the UI uses pages of 20. |
| `GET /portal/meters/{meterId}/geo` | Meter coordinate data. |
| `GET /portal/meters/{meterId}/energy` | Recent energy rows used by the detail page. |
| `GET /portal/export?page=1` | Full meter export used by the UI's export action; it returned all 403 meter records in one response. |
| `GET /portal/keys` | Authenticated UI retrieves the request-signing secret for the export call. This secret is kept in memory by the client and is never logged or stored. |

Requests without an authenticated portal session to `/portal/keys`, meter search, and the transformer list returned HTTP 401 during inspection. The data calls are reads. The only POST in the normal flow is the sign-in form.

## Export signature

The browser signs the bulk export request using HMAC-SHA256. For the observed export call, it computes the signature over four newline-separated values:

```text
GET
/portal/export
page=1
{unix_timestamp_seconds}
```

It sends the timestamp in `x-timestamp` and the lowercase hex digest in `x-signature`. `app/portal_client.py` follows that observed format. It retrieves the secret only after establishing a session and does not persist it.

## Hierarchy behavior

The meter export includes a hierarchy object per meter, so the sync process can rebuild the hierarchy without scraping every meter detail page. Codes are not globally unique across the full hierarchy: repeated codes can occur below different parents. The local database therefore identifies nodes by their full ancestor path plus level/code. This preserves branches instead of merging nodes solely because their display code matches.

The seven hierarchy levels are ordered as zone → circle → division → subdivision → substation → feeder → distribution transformer. The detail page renders the same path as a breadcrumb. Some exported meters are decommissioned or faulty; the API preserves those statuses and does not filter them out by default.

## Authentication and session limits

The web UI uses a session cookie after the form sign-in. API read calls require that session. The adapter obtains credentials from `PORTAL_USERNAME` and `PORTAL_PASSWORD`, performs the SvelteKit form action with `Origin`, `Referer`, and `x-sveltekit-action` headers, and reuses the cookie jar. An initial direct POST without the browser's `Origin` header returned HTTP 403; matching the normal browser request resolved it. The implemented client was then able to fetch the signed meter export, all transformer pages, and one meter's energy rows. It retrieved 403 meters, 40 transformers, and 337 energy readings in that session.

The portal UI handles session access and reports page/route errors. The API adapter adds request timeouts, clear HTTP errors, a one-time session refresh on unauthorized reads, bounded transformer pagination, and cached energy fallback. A scheduled refresh is intentionally left to deployment configuration; `python -m app.sync` refreshes the local metadata snapshot on demand.

## Mapping into this API

The API provides a stable, readable contract instead of exposing portal response objects verbatim:

- `serialNo` becomes `serial_number`; installation and phase fields retain clear snake_case names.
- Hierarchy entries become linked SQLite nodes and appear as `network_hierarchy` on meter detail.
- `capacityKva` becomes `capacity_kva`.
- Energy's `voltR` becomes `voltage_r`; timestamps are interpreted in `Asia/Kolkata`, stored as UTC, and returned with a `Z` suffix.
- The CLI loads the signed bulk export and all transformer pages. The readings route fetches and caches energy only for the requested meter.

The SQLite file and any locally downloaded `meter-export.json` contain operational meter data. Keep them out of source control and only retain them on an appropriately protected machine.
