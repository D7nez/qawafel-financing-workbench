# Source automation - v1.2
## What actually runs
A separate local HTTP server provides two fictional read APIs: accounting invoices and a bank statement. The workbench pulls them without file selection, validates their scope/content and invokes the same analysis engine as manual upload. A recurring scheduler is implemented. **No real ERP, bank API, OAuth, live account or bank submission is connected.**

Start both services from the project root, in Python 3.12:
```bash
python scripts/run_local.py
```
Workbench: http://127.0.0.1:8000. Fictional sources / contract: http://127.0.0.1:8001/docs. Stop an older server on port 8000 first. Ctrl+C stops both services. Source automation requires both services; the older uvicorn command starts manual-upload mode and its scheduler, but cannot fetch an absent source server.

## Demonstration
1. Open **Source automation**. Select the checkbox for fictional entity/period/read scope and **Grant demo consent** (60-minute expiry).
2. Select **Sync sources now**. The workbench reads both manifests, downloads CSV/PDF over HTTP, verifies checksums and analyzes them. **Open latest analysis** displays the imported package.
3. Sync again. Status **unchanged** confirms only manifests were fetched: file downloads and analysis were skipped.
4. Choose **10 seconds (demo)** and **Start recurring sync**. Keep the server running; a run appears without another click. Its trigger is scheduled.
5. Change Invoice snapshot to **Invoices with data issues** and apply. The next pull imports a changed snapshot, records **needs_review**, and exposes five blockers. No bank request is submitted.
6. Set Source behavior to **HTTP 503 outage** or **Wrong checksum**, apply and sync. A failed run is recorded, the prior checkpoint/result is retained, and scheduled failures back off. Restore Healthy to recover.
7. **Revoke & stop**. New reads/publication stop; the recurring schedule is disabled. Granting consent again does not silently restart the schedule.

## Source contract
`GET /accounting/v1/manifest` and `GET /bank/v1/manifest` return fixed fictional entity, reporting period, integer snapshot revision, SHA-256, size and a relative file path. Read calls require the documented mock header `X-Demo-Consent: fictional-read-scope`; this is a demonstration guard, not a security/OAuth implementation.

`GET /accounting/v1/files/invoices.csv?revision=N` and `GET /bank/v1/files/statement.pdf?revision=N` return source bytes. A revision change between manifest and file produces 409; the next pull restarts coherently. Both manifests must have the same mock revision. The connector allowlists the exact loopback origin/path contract, does not follow redirects, ignores proxy environment variables and bounds payload size/timeouts. It never follows arbitrary URLs supplied by a manifest.

`POST /control/scenario` modifies only the mock source: profile clean/issues; fault healthy/unavailable/bad_hash. Changes increment its revision. Controls are deliberately local and unauthenticated simulation controls, not production administration.

## Workbench API and storage
- `GET /api/automation/status`: consent, schedule, checkpoint, latest package and last 20 runs.
- `POST /api/automation/consent`: accepted=true and expires_in_minutes (1-480); starts no schedule by itself.
- `POST /api/automation/revoke`: revoke and disable schedule.
- `POST /api/automation/schedule`: enabled and interval_seconds (10-86400).
- `POST /api/automation/sync`: pull now; 403 without consent, 409 if already running. A failed source pull is an inspected run result, not a lending decision.
- `POST /api/automation/scenario`: fixed local proxy for the mock scenario controls, gated by active demo consent.

SQLite `sync_state` stores consent expiry/generation, enabled/interval/next_due, content checkpoint, last analysis/revision and failure count. `sync_runs` stores run ID, trigger, times, status, reason, package ID and revision. Revocation is checked before requests, during response streaming and before result publication. Already downloaded processing may complete into the local analysis cache after revocation; the sync checkpoint/latest link is not published. Consent revocation does not erase historical data; deletion is a separate policy.

Unchanged source hashes plus calculation version skip document retrieval. Changed snapshots are imported in full and content-deduplicated by the existing engine. **This is snapshot synchronization, not incremental invoice/event ingestion or a production cursor protocol.** A structurally invalid but readable snapshot is checkpointed as needs_review, so it is not reprocessed every interval; a later corrected snapshot changes hashes and is analyzed again. Transport/hash/scope failures never advance the checkpoint.

## Scheduling and recovery
The scheduler checks due work every two seconds. Normal repeat interval is chosen by the user; bounded exponential retry is min(3600 seconds, interval × 2^failure_count), exponent capped at six. No tight retries or duplicate POST submissions. Pause stops future scheduled runs; it does not revoke consent or cancel an active manual pull. Revocation/expiry stops new reads and publication. Runs require a running server and **one workbench worker**; no distributed scheduling/leader election is implemented. On process restart, abandoned running records are marked interrupted and an enabled, unexpired schedule can resume from its prior checkpoint. Stop both services before launching another copy against the same databases.

## Production boundary
Replace fixed mock adapters with provider-approved contracts, OAuth/token storage and real consent scope/expiry, pagination and stable record IDs, entity/account ownership checks, encryption, tenant isolation, robust distributed jobs/leases, secret management, and provider-specific statement/OCR support. Review ambiguous allocations and obtain named approval/customer consent for one immutable package before any bank submission. Read-only automation does not implement approval, disbursement or a bank credit decision.
