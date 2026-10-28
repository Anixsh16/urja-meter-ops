# Urja Meter Workspace

A read-only API and dashboard over the Urja Meter Ops portal. Search a meter, inspect its nameplate and cumulative energy readings, and follow its network path without using the legacy UI.

The integration uses the portal's **normal signed export**, rather than scraping a detail page for every meter. An observed export contains 403 meters across legacy and v2 formats. Source inconsistencies are retained as warnings, not silently repaired.

## Start here

- [Protocol investigation](PROTOCOL.md): authentication, observed requests, signing, data shapes, and quirks.
- [API contract](openapi.json): generated OpenAPI 3.1 description of this service.
- [Architecture and decisions](docs/ARCHITECTURE.md): stack, data flow, freshness, and limitations.
- [Build order and requirement checklist](docs/BUILD_PLAN.md).
- [Verification evidence](docs/VERIFICATION.md).
- [Reflection and AI assistance disclosure](REFLECTION.md).

## Run locally

Prerequisites: Python 3.11+ (Docker/CI use 3.12), [uv](https://docs.astral.sh/uv/getting-started/installation/), and Node.js 24 with npm. Portal access is supplied separately in the assignment. No LLM key, database, map key, or paid service is required.

```sh
git clone https://github.com/Anixsh16/urja-meter-ops.git
cd urja-meter-ops
uv sync --frozen
```

Copy `.env.example` to `.env` and fill in `PORTAL_USERNAME`, `PORTAL_PASSWORD`, and a random `DEMO_API_KEY` of at least 24 characters. `.env` is ignored by Git. Generate a demo token with:

```sh
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Build the frontend, then start the combined service:

```sh
cd web
npm ci
npm run build
cd ..
uv run uvicorn urja.main:app --host 127.0.0.1 --port 8000 --no-access-log --log-config logging.json
```

Open [the workspace](http://localhost:8000) and enter your demo token. The same token authorizes requests in [Swagger UI](http://localhost:8000/docs). Reloading the workspace clears its in-memory login.

On the original development machine, credentials are already stored **outside this repository**. The convenience command `uv run python scripts/local.py` uses that private configuration without needing a `.env` file. `--config /path/to/credentials.json` supports another location. Only portal configuration and the demo token enter the application process; GitHub/Render management credentials are not loaded by the application.

For frontend development, run the API on port 8000 and `npm run dev` in `web/`. Vite proxies `/api` to the backend. Build the frontend to use the combined service at port 8000.

## Make a request

Set `DEMO_API_KEY` in your shell to the configured demo token:

```sh
curl -H "Authorization: Bearer $DEMO_API_KEY" \
  'http://localhost:8000/api/v1/meters?q=J100000'

curl -H "Authorization: Bearer $DEMO_API_KEY" \
  'http://localhost:8000/api/v1/meters/J100000/consumption?from=2026-06-29&to=2026-06-30'
```

PowerShell equivalent (using `$env:DEMO_API_KEY`):

```powershell
Invoke-RestMethod 'http://localhost:8000/api/v1/meters?q=J100000' `
  -Headers @{ Authorization = "Bearer $env:DEMO_API_KEY" }
```

Responses use `{ "data": ..., "meta": { "fetched_at": ..., "cache": "hit|miss", "age_seconds": ..., "warnings": [...] } }`. Decimal registers are JSON **strings**, so precision is preserved. `null` means unavailable; `"0"` means an actual zero reading. All errors from documented data routes have `{ "error": { "code", "message", "request_id" } }`.

| Method / route | Behavior |
| --- | --- |
| `GET /healthz` | Process health; no login or portal request |
| `GET /api/v1/meters` | Complete-catalogue search and pagination |
| `GET /api/v1/meters/{meter_id}` | Nameplate, coordinates, source hierarchy, and warnings |
| `GET /api/v1/meters/{meter_id}/consumption` | Cumulative registers, optional inclusive `from`/`to` dates |
| `GET /api/v1/network/nodes` | Roots by default; children with `parent_id`, or all nodes at `level` |
| `GET /api/v1/network/nodes/{node_id}` | One path-specific network node |
| `GET /openapi.json`, `GET /docs` | Schema and interactive documentation |

Meter list parameters: `q` searches ID/serial case-insensitively, `status` matches status case-insensitively, `node_id` filters a network path and descendants, `page` starts at 1, and `page_size` defaults to 20 (maximum 100). Ordering is stable by meter ID within a snapshot. Out-of-range pages return an empty page. Filters operate on the verified complete export, not on one portal page.

Consumption dates use `YYYY-MM-DD`; reversed ranges and ranges greater than 366 days are rejected. Omitting dates uses the source default window. **Observed data ends in June 2026**, so selecting today's date can legitimately produce no readings. `fetched_at` describes when the service retrieved data, not when the meter was last read.

Data-route status codes: 401 missing/invalid demo token; 404 unknown meter/node; 422 invalid parameters; 429 local demo quota (120 authenticated requests/minute); 502 malformed/rejected/incomplete source responses; 503 source authentication, rate limiting, connectivity, or availability failure; 504 source timeout. Caller authentication is distinct from portal authentication. Framework 404/405 responses for unknown routes/methods retain FastAPI's normal shape.

## Configuration and freshness

| Variable | Default / meaning |
| --- | --- |
| `PORTAL_URL` | `https://urja-ops.flockenergy.tech`; HTTPS required |
| `PORTAL_USERNAME`, `PORTAL_PASSWORD` | Required, server-only |
| `DEMO_API_KEY` | Required, at least 24 characters; share privately |
| `PORTAL_TIMEZONE` | `Asia/Kolkata`; explicitly an assumption because source timestamps have no offset |
| `CATALOG_TTL` | 300 seconds; catalogue, details, and derived hierarchy share the same snapshot |
| `ENERGY_TTL` | 60 seconds per meter/date window |
| `CACHE_ENTRIES` | 128 bounded LRU entries, including the catalogue |
| `UPSTREAM_CONCURRENCY` | 2 waiting slots; logical portal operations are serialized for session safety |
| `WEB_DIST` | `web/dist`; built static frontend location |

Caches and sessions are process-local and disappear on restart. Expired results are never silently served after a failed refresh. Identical concurrent reads share a cache fill. No cookies, portal signing keys, or meter exports are persisted by the service. Use one backend process for this demo.

## Verify

From the repository root:

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run python scripts/export_openapi.py
git diff --exit-code -- openapi.json
cd web
npm ci
npm run build
npx playwright install chromium
npm run test:e2e
```

On Linux, `npx playwright install --with-deps chromium` also installs browser system dependencies. Browser tests automatically start a local API with explicitly synthetic records. No portal credentials or network portal calls are required for automated tests. Results cover desktop and mobile lookup, pagination, filters, hierarchy, zero/missing readings, empty windows, failure recovery, token rejection, and sign-out. Screenshots are written to ignored `artifacts/`. CI also builds the production container.

## Docker and hosting

```sh
docker build -t urja-meter-ops .
docker run --rm -p 8000:8000 --env-file .env urja-meter-ops
```

The image builds the frontend and runs one unprivileged Python process. Management tokens must never be Docker build arguments or application environment variables. Only supply portal credentials and the private demo token at runtime.

`render.yaml` describes one free Docker web service in Singapore, with `/healthz` as its health check. Deploy this public repository through Render, supply the portal credentials privately, and retain the generated demo token for reviewers. Check CI before deployment; the Blueprint requests deployment after checks pass. If the host cannot link CI checks, use manual deployment after verifying the selected commit's checks. No custom domain is necessary.

Free Render services can sleep and restart, so the first load may take about a minute. Storage is ephemeral, which is acceptable because this app has no persistent database. See [Render's limitations](https://render.com/docs/free). Deployment status and verified URL belong in [verification evidence](docs/VERIFICATION.md).

## Intentional scope and trade-offs

The complete required API/documentation milestone is followed by robustness, a hierarchy explorer, and the meter-focused dashboard. The signed export made a small in-memory query layer useful without introducing a persistent index. Hierarchy shares the catalogue TTL rather than a separate 15-minute cache so details and network relationships remain from one snapshot.

We intentionally omit a persistent database, background sync, geographic-radius queries, fleet anomaly scoring, interval-usage totals, user accounts, multi-tenant credentials, and distributed workers. A shared demo bearer token is suitable for a small protected demonstration, not a production authorization model. For a larger catalogue, replace repeated in-memory scans with indexed storage and a background refresh; benchmark before claiming a precise scale limit. Current memory use and rebuild cost grow with the catalogue and hierarchy path count.

See the [architecture notes](docs/ARCHITECTURE.md) for failure modes, assumptions, and what to improve with more time, and [the reflection](REFLECTION.md) for the five requested reflection answers and AI disclosure.
