# Urja portal protocol investigation

Observed against the running portal on 28 October 2026 using the supplied normal operator account. No writes to meter or network data were performed. Authentication POSTs create login sessions; all subsequent integration operations are reads. These findings describe observed behavior, not a published upstream compatibility guarantee.

## Discovery path

1. The public root redirects to `/login`. The HTML contains an email/password form and SvelteKit assets.
2. A bare POST without an `Origin` returned 403. Repeating the normal form submission with the matching HTTPS origin and referer succeeded.
3. `/meters` initially renders an empty HTML table; its ordinary shipped page script fetches the real list after mount. Treating the initial HTML's `0 total` as data would be wrong.
4. The Transformers page's **Export all meters** button fetches a signing key and signs `/portal/export`. Reproducing this normal UI sequence returned all 403 records, including hierarchy and geography. This became the catalogue source.
5. A meter detail page supplies nameplate/hierarchy in its SvelteKit page data, then fetches geo and energy separately. Source rendering supports both parameter-list and `classData`/`installed_meter` detail formats. The bulk export avoids binding our public API to either page format.

## Authentication

`POST /login`, form-urlencoded fields `email` and `password`, headers `Origin: <portal-origin>` and `Referer: <portal-origin>/login`.

The observed successful response is **HTTP 200 with a SvelteKit action envelope**:

```json
{"type":"redirect","status":303,"location":"/meters"}
```

The response also sets an HTTP-only secure session cookie named `__Secure-better-auth.session_token`. Do not assume the embedded `status:303` is an actual HTTP redirect. Our adapter accepts either this action response or a normal HTTP 302/303 to `/meters`, but requires a cookie as well. HTTPX retains cookies in memory. No cookie values belong in this file.

Unauthorized data reads can redirect to login or return an auth error; the adapter also recognizes login HTML to avoid parsing it as data. Recovery is bounded to one reauthentication per affected read. A signed export re-fetches the signing key and regenerates its signature after a session change. Cookie lifetime and signing-key lifetime have not been measured with a long-running soak; expiry recovery is tested with controlled fixtures.

## Observed read requests

| Request | Observed shape / use |
| --- | --- |
| `GET /portal/meters/search?q=&page=1` | `{data:[...], total:403, page:1, pageSize:20}`; ID/serial search in the UI |
| `GET /portal/dts?page=1` | Transformer registry, 20 rows/page, observed total 40; fields `code`, `name`, `feederCode`, `capacityKva` |
| `GET /portal/keys` | `{data:{signingSecret:...}}`, available to the logged-in export UI |
| `GET /portal/export?page=1` | Signed full export: `{data:[...], total:403}`; all 403 rows returned in this single observed response |
| `GET /meters/{id}` | HTML detail page with server-supplied nameplate/hierarchy and client-side geo/energy requests |
| `GET /portal/meters/{id}/geo` | `{data:{latitude:"...",longitude:"..."}}` (numeric strings observed) |
| `GET /portal/meters/{id}/energy` | `{data:[{timestamp,kwh,kvah,voltR},...]}` |
| `GET /portal/meters/{id}/energy?from=2026-06-29&to=2026-06-30` | Inclusive date filtering observed; the API also enforces the requested dates after parsing |

The service uses `/login`, `/portal/keys`, `/portal/export`, and `/portal/meters/{id}/energy`. Other requests were inspected to understand and cross-check the UI. It does not proxy arbitrary user-supplied URLs or expose the signing key.

## Export signature

The normal export button signs these four UTF-8 values, separated by a **single LF** (`\n`):

```text
GET
/portal/export
page=1
<current Unix timestamp in seconds>
```

Compute `HMAC-SHA256(signingSecret, message)` and encode the result as lowercase hex. Send `x-timestamp` and `x-signature`, using the exact query string that was signed, plus the session cookie. The signing key comes from the normal authenticated `/portal/keys` request; it is not a guessed or hardcoded secret. Keys are fetched before each export and never returned by our API.

`page=1` is the UI's own query. Despite that parameter, the observed export returns the entire dataset and has no page/pageSize metadata. We do not assume this will remain true: the adapter checks `len(data) == total` and refuses an incomplete response instead of exposing a partial catalogue as complete.

## Catalogue data and hierarchy

Export fields observed: `meterId`, `serialNo`, `make`, `phaseType`, `installStatus`, `installType`, `build`, `dtCode`, `hierarchy`, `geo`.

`hierarchy` contains `zone`, `circle`, `division`, `subdivision`, `substation`, `feeder`, `dt`, each normally with `code` and `name`. `geo` contains numeric `lat`/`lng`, unlike the geo endpoint's numeric strings. The export contains 238 legacy records and 165 v2 records in this observed snapshot; all 403 meter IDs are distinct.

There is no guarantee the hierarchy forms one clean tree. Observations include reused codes under differing ancestry, missing hierarchy fields, and transformer naming variants. The last three records (`J100400`–`J100402`) use `DT-007` with the name `Old Malviya Nagar Xfmr`, while other observations use different names for that transformer code. Source code alone is therefore insufficient as a unique tree node ID.

Our node ID hashes `(parent path, level, source code)`. Multiple names under the same code/path become visible aliases; differing parent paths remain separate nodes with warnings. Missing hierarchy levels break the chain instead of inventing an edge over the gap. A lower-level orphan is exposed as a root with a warning. Node counts mean distinct meters belonging to **that path**, not globally deduplicated physical assets. In the initial export this produced 240 nodes, 17 roots including orphans, 191 nodes with warnings, and 14 meters with missing/inconsistent fields. These are snapshot observations and can change.

## Consumption semantics and quirks

- Timestamps are strings in `DD/MM/YYYY HH:mm`, with no offset or timezone field. `Asia/Kolkata` is a documented, configurable geographic assumption. Both the interpreted offset timestamp and original text are returned.
- `kwh`, `kvah`, and `voltR` are decimal strings. The increasing kWh/kVAh sequences are treated as cumulative registers. We do not sum them or claim interval usage. Units follow the UI labels: kWh, kVAh, and volts.
- The default observed legacy and v2 examples each return 337 half-hourly readings from 23 June 2026 23:30 to 30 June 2026 23:30. This dataset does not track today's date. A special meter (`J100400`) returned only 8 readings in its default window.
- Missing values and zero must stay distinct. The original UI uses a truthy fallback for readings; our API preserves an actual zero and our chart leaves missing values as gaps.
- An unknown meter energy request returned HTTP 404 with `{"error":"not_found","message":"Meter not found"}`.
- No rate-limit threshold, absolute date-range limit, or long-running session lifetime has been established. The service uses a small bounded cache, serialized logical reads, explicit timeouts, bounded retries, and a local request quota rather than aggressively probing those limits.

## Evidence and limits

The live adapter was checked against legacy, v2, and special records, and the catalogue count was matched to the export's declared total. Automated tests use synthetic responses representing the observed protocol and failure cases. No raw full export, session cookie, source signing key, portal password, or management token is committed to this repository. AI assistance performed the investigation and implementation; see [the disclosure](REFLECTION.md).
