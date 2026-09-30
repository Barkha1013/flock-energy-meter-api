# Urja Meter Ops: protocol investigation

This note separates observed behavior from the assignment's description and from items that still need an authenticated investigation. It is intentionally conservative: no API routes or data fields are stated as facts without evidence.

## What the assignment says is available

The take-home brief describes the portal as a read-only operations interface for smart-meter information: meter details, a meter's position in the distribution network, and recent consumption. It also says the network is hierarchical. Those are product-level statements from the brief, not fields independently confirmed in a logged-in session.

## What I observed

- The base portal URL `https://urja-ops.flockenergy.tech` responds with a redirect to `/login`.
- The login page title is **Urja Meter Ops - Sign in** and identifies itself as a distribution metering operations portal.
- The page is a SvelteKit-rendered HTML page. Its sign-in form uses `method="POST"`, with fields named `email` and `password`, and submits to the current `/login` path.
- A normal HTTP GET of the public login page succeeded. A form POST to `/login` using the credentials supplied in the assignment returned HTTP 403 in this inspection environment. No authenticated session was obtained.

## Access and authentication

The only confirmed access flow is the public sign-in screen and its field names. I could not confirm whether a successful login issues a cookie, redirects to a dashboard route, or calls another service. Cookie/session behavior, CSRF requirements, session lifetime, and logout behavior remain unknown. The credentials are intentionally not repeated here or saved in the repository.

## Routes and data availability

| Area | Evidence / status |
|---|---|
| `/` | Request redirects to `/login`. |
| `/login` | Public sign-in page observed by GET. Form POST returned 403 from this environment. |
| Authenticated dashboard and meter pages | Not inspected because login did not complete. |
| Portal JSON/XHR endpoints or bulk export | Not confirmed. |
| Meter, network, and consumption field names, units, and paging | Not confirmed; the assignment only names the broad categories. |

The API in this repository therefore defines its own proposed normalized fields in `app/schemas.py`. The `POST /api/v1/imports` route accepts that normalized shape to make the read API demonstrable; it does not reproduce a portal request or assert that the portal uses these names. It requires timezone-qualified reading timestamps, converts them to UTC for storage, and returns UTC timestamps.

## Quirks and surprises

- The unauthenticated page is a SvelteKit application, so the UI is server-rendered and bootstrapped with client-side JavaScript.
- The supplied credentials and ordinary form fields did not produce a session in this environment; the server returned 403. This may be an environment restriction or a portal-side requirement, but the cause was not established.
- The assignment calls out a network hierarchy, but the actual hierarchy vocabulary and consistency of its data could not be checked.

## Next discovery steps

1. Open the supplied portal in an approved interactive browser session and sign in normally.
2. Record the dashboard route and the user-visible steps to a meter, its network context, and readings.
3. In browser developer tools, inspect only normal page traffic to identify read requests, response shapes, paging, and whether the UI uses HTML or JSON. Do not probe undocumented write paths.
4. Capture representative sanitized records and verify null handling, units, date/time zone, and hierarchy anomalies.
5. Repeat a read after session expiry or a transient error to learn the portal's session renewal and failure behavior.
6. Implement a read-only client for the confirmed flow, map source responses into the import contract, and add sanitized fixtures before enabling scheduled synchronization.
