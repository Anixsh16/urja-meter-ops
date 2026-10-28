# Verification evidence

This file distinguishes completed checks from planned or externally blocked work. It is updated after final deployment validation.

## Local evidence recorded during construction

- Backend: 50 tests passed, covering public contracts, session/login/signature behavior, repeated expiry budgets, source failures, cache expiry/single-flight/bounds, hierarchy conflicts/cycle prevention, filtering, precision and missing values.
- Live adapter: authenticated, matched all 403 export records to the declared total, and retrieved energy for `J100000` (legacy), `J100004` (v2), and `J100400` (special short history).
- Observed hierarchy: 240 path-specific nodes, 17 roots including unresolved lower-level roots, and 191 nodes with warnings. Fourteen meters had missing/inconsistent fields. These counts describe the tested snapshot, not fixed application constants.
- Frontend TypeScript check and production build passed.
- All six browser journeys passed on desktop Chromium and mobile Chromium after fixing a mobile table accessibility-label overflow.
- Docker built successfully; the running production container passed live authenticated API checks and complete desktop/mobile journeys against all 403 source records.
- GitHub Actions run 40703233336 passed all checks, including tests, TypeScript/build, browser journeys and Docker build, on commit `1d7107a37c194748130813fe9b455c1fd9a8fc99`.

## Final release evidence

- Hosted service: [https://urja-meter-ops-qy60.onrender.com](https://urja-meter-ops-qy60.onrender.com). Render service `srv-dbh05hfb9u1s739ccudg`, free Docker runtime, Singapore, one process. Runtime configuration contains portal credentials and the demo token only; management tokens are not deployed.
- Health responds 200. A request without a demo token receives 401. Authenticated catalogue requests return all 403 records.
- Hosted detail checks succeeded for legacy `J100000`, v2 `J100004`, and special `J100400`. A default `J100004` energy request returned 337 readings; 29–30 June returned 96 readings. A July window correctly returned an empty list.
- Hosted network roots and level queries succeed. The observed transformer level has 54 path variants representing 40 distinct source transformer codes; the application does not mislabel those variants as 54 unique physical transformers.
- The explicit live browser script passed on desktop Chromium and mobile Chromium against the hosted service: login, page navigation, meter search, profile/chart, hierarchy expansion, network filtering, no horizontal document overflow, and sign-out. No uncaught browser errors were recorded. The first hosted browser check was recorded on 28 October 2026 at 14:14 UTC (19:44 IST).
- An isolated urllib read timed out during an additional hosted network-level query; retrying the same query with HTTPX returned 200 and the complete response. This was not treated as proof the service was down; the successful browser and API checks provide stronger evidence. No reliability/uptime SLO is claimed for free hosting.
- The release procedure deploys only a revision whose completed GitHub Actions runs succeeded. Initial CI evidence: [run 40703233336](https://github.com/Anixsh16/urja-meter-ops/actions/runs/40703233336); frontend formatting/live-check tooling also passed [run 40704278083](https://github.com/Anixsh16/urja-meter-ops/actions/runs/40704278083). The [workflow history](https://github.com/Anixsh16/urja-meter-ops/actions/workflows/ci.yml) records the final source revision's result.
- Deployments are manually triggered after checks pass for this API-created service (`autoDeployTrigger=off`). The reusable Blueprint requests `checksPass` for accounts with linked GitHub checks. Roll back to a known successful Render deploy if a new runtime smoke check fails.
- The demo token is saved privately on the owner's machine in `~/.config/urja-meter-ops/demo-access.txt`. The source portal password, signing keys and management credentials are excluded from Git; no raw full export is committed.
- Submission email has not been sent. The owner has authorized building/publishing/hosting the project, not contacting the assignment recipient.

## Remaining limits

Expiry, repeated expiry, source failures and malformed data are tested with synthetic transports. A prolonged live-session soak and precise scale/latency benchmarks were intentionally deferred. The configured timezone and cumulative-register interpretation remain documented assumptions. The delivered hierarchy describes observed source paths with warnings; it does not resolve contradictory physical-network data. AI assistance is disclosed in REFLECTION.md.
