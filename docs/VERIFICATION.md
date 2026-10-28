# Verification evidence

This file distinguishes completed checks from planned or externally blocked work. It is updated after final deployment validation.

## Local evidence recorded during construction

- Backend: 46 tests passed, covering public contracts, session/login/signature behavior, source failures, cache expiry/single-flight/bounds, hierarchy conflicts, filtering, precision and missing values.
- Live adapter: authenticated, matched all 403 export records to the declared total, and retrieved energy for `J100000` (legacy), `J100004` (v2), and `J100400` (special short history).
- Observed hierarchy: 240 path-specific nodes, 17 roots including unresolved lower-level roots, and 191 nodes with warnings. Fourteen meters had missing/inconsistent fields. These counts describe the tested snapshot, not fixed application constants.
- Frontend TypeScript check and production build passed.
- Initial desktop browser journeys passed; a mobile pagination overflow issue was found and fixed. The final cross-device result, Docker result, CI revision, and hosted result are pending final validation below.

## Final release evidence

Pending final verification. A successful local build alone does not establish a working hosted demo.
