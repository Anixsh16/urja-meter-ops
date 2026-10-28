# Verification evidence

This file distinguishes completed checks from planned or externally blocked work. It is updated after final deployment validation.

## Local evidence recorded during construction

- Backend: 47 tests passed, covering public contracts, session/login/signature behavior, source failures, cache expiry/single-flight/bounds, hierarchy conflicts, filtering, precision and missing values.
- Live adapter: authenticated, matched all 403 export records to the declared total, and retrieved energy for `J100000` (legacy), `J100004` (v2), and `J100400` (special short history).
- Observed hierarchy: 240 path-specific nodes, 17 roots including unresolved lower-level roots, and 191 nodes with warnings. Fourteen meters had missing/inconsistent fields. These counts describe the tested snapshot, not fixed application constants.
- Frontend TypeScript check and production build passed.
- All six browser journeys passed on desktop Chromium and mobile Chromium after fixing a mobile table accessibility-label overflow.
- Docker built successfully; the running production container passed live authenticated API checks and complete desktop/mobile journeys against all 403 source records.
- GitHub Actions run 40703233336 passed all checks, including tests, TypeScript/build, browser journeys and Docker build, on commit `1d7107a37c194748130813fe9b455c1fd9a8fc99`.

## Final release evidence

Pending final verification. A successful local build alone does not establish a working hosted demo.
