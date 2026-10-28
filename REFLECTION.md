# Build reflection

## AI assistance

Codex performed portal inspection, implementation, automated testing, documentation and deployment work at the repository owner's request. These notes record that build's actual observations and decisions; they do not claim the owner independently performed the investigation. The assignment describes assistants as guidance and expects the candidate to own the core investigation, so this assistance must be disclosed when discussing the submission. This document is not a fabricated account of unaided candidate work.

## What assumptions were made?

The service treats source kWh/kVAh as cumulative registers based on increasing sequences and UI labels. Since source timestamps have no timezone, Asia/Kolkata is an explicit configurable assumption. An export is considered complete only when its row count matches its declared total. Network relationships are treated as source claims, not guaranteed physical truth, and shared demo credentials are assumed appropriate only for a small protected evaluation.

## What was most difficult, and how was it unblocked?

The main challenge was discovering the data path rather than the framework code. A plain login POST failed, and the meter page's initial HTML looked empty. Inspecting the normal form, page assets and export-button request sequence exposed the origin requirement, SvelteKit's HTTP-200 redirect envelope, and the signed full export. Reproducing that UI sequence provided a much simpler adapter and avoided coupling to two detail-page formats.

## What would improve with another day?

Run a measured long-session test against the real source, compare more individual meter-page values with export fields, and benchmark cold-cache latency and memory. Strengthen total request deadlines/cancellation and use a configurable proxy-level limit if expanding access. Add interval-usage calculations only after validating counter reset and rollover behavior. A larger data source would justify indexed snapshots and scheduled refresh; the current one does not require those services.

## What mistake occurred?

The first login attempt assumed a straightforward form POST and omitted the browser's Origin header, producing a 403. The corrected adapter reproduces the normal form's origin/referer and tests the exact redirect envelope. Browser validation also caught a mobile accessibility label positioned outside its scroll container; that overflow interfered with pagination taps and was corrected before the final browser run.

## What would a self-review criticise?

The demo relies on a reverse-engineered upstream contract that can change without notice. The complete catalogue is refreshed synchronously, portal operations are deliberately serialized, and expiry tests are mostly controlled simulations rather than a long production soak. The shared access token lacks individual user identities, while path-specific hierarchy nodes expose ambiguities without resolving the underlying data. Those limits are documented, but they would need work before calling this a production utility integration. The amount of AI implementation assistance also differs from the assignment's intended guidance-only workflow.
