# Build order and completion checklist

The agreed scope is a required API submission followed by selected extras: robustness, a hierarchy explorer, a meter-focused dashboard, local execution, and a protected hosted demo. No fixed time budget was selected. The assignment's own suggested core effort is 4–6 hours; this broader implementation is not presented as having met that time box.

| Order | Milestone | Acceptance evidence |
| --- | --- | --- |
| 1 | Investigate normal read-only portal access | PROTOCOL.md and live adapter smoke checks |
| 2 | Reusable authenticated portal client | Origin/cookie/signature/session tests |
| 3 | Typed versioned API | Meter search/detail/consumption and documented error tests |
| 4 | Complete required handoff | README, PROTOCOL.md, generated openapi.json, reflections |
| 5 | Robustness and freshness | Bounded retries, expiry recovery, cache expiry/single-flight tests |
| 6 | Hierarchy and dashboard | Alias/parent conflict tests and desktop/mobile browser journeys |
| 7 | Reproducible packaging and hosted demo | Docker smoke, remote CI, hosted API/browser verification |

## Requirements mapped to artifacts

- API source: `src/urja/`.
- README covering purpose, structure, install/configuration/run, sample requests, assumptions, decisions, trade-offs, omissions, future work and document links: repository README.
- How portal data/auth/access actually work, with quirks: PROTOCOL.md.
- OpenAPI 3.x for the clean service: openapi.json, generated from FastAPI; consistency is checked.
- Notes on assumptions, trade-offs, skipped work, future improvements: README and docs/ARCHITECTURE.md.
- All five reflection questions: REFLECTION.md, with explicit AI disclosure.
- Selected hierarchy extension: path-specific graph and visible source warnings.
- Selected robustness extension: bounded errors/recovery, quotas, freshness metadata, TTL cache.
- Selected modern client: directory, search/filter, profile, chart, source readings, hierarchy, empty/failure states.
- Public GitHub repository and protected hosted demo: final links and status in docs/VERIFICATION.md.
- Submission email: not sent; emailing a third party requires a separate explicit user instruction.

## Decisions resolved by investigation

HTTPX is sufficient; no runtime browser is needed. The export path provides the complete catalogue and geography. Both legacy and v2 formats are present. Fixed June readings and missing timezone metadata require visible historical dates and an explicit timezone assumption. Inconsistent hierarchy fields require a forest with path variants. A small in-memory query layer is justified by the complete 403-row export; persistent indexing and background ingestion are intentionally deferred.
