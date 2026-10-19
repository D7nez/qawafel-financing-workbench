# Validation record - version 1.2
**Executed: 19 October 2026 · Python 3.12.14 · Linux x86_64**

## Fresh installation and reproducibility
A new virtual environment was created without system-site-packages. Installation from `requirements-ui.txt` (which includes dev and runtime requirements) succeeded. `python -m pip check` returned **No broken requirements found**. Automated tests (including fixture regeneration into a temporary directory), the submission renderer and UI smoke scripts were executed using that environment's Python; the UI script launches its server with the same interpreter. Installed versions are captured in `docs/requirements-tested.txt`.

Commands executed from the project directory, with the isolated interpreter:
```bash
python -m pip install -r requirements-ui.txt
python -m pip check
python -m pytest -q
python scripts/build_submission.py
python scripts/check_ui.py
python scripts/check_automation_ui.py
python scripts/verify_fixture.py
```
The UI check used `CHROME_EXECUTABLE` pointing to Chrome for Testing 145. The default Playwright browser-download endpoint was unavailable in this environment; an explicit Chrome executable was used. This does not verify Playwright's browser download on another machine. Installation and generation need internet/dependencies; the product works locally afterward.

## Automated results
**53 passed, 1 warning in 21.67 seconds.** The warning is a Starlette dependency deprecation about migrating TestClient from httpx to httpx2; tests passed with the pinned direct versions.

Coverage includes golden sums and receivable identities; duplicate suppression; invalid-row quarantine; missing months; split / early / excess receipts; owner inflow exclusion; strict dates; unsupported/malformed PDFs; balance mismatch and duplicate bank transaction IDs; deterministic model and planted-case retrieval; API upload/demo/cache/export and size/type guards; tiny native-float noise versus genuine fractional cents; missing XLSX dimensions and source rows after blank rows; per-customer balances and settlement samples; anomaly financial-priority ordering; bank normal progression/reversal/stale timestamps/timeout and deterministic correlation simulation; variable/reproducible generated data; and competing cache writers returning one canonical analysis ID. Seventeen new source-automation cases include consent denial/scope, initial HTTP pull, unchanged snapshots, changed snapshots, outage/hash recovery, scheduled ticks/expiry, mid-fetch and mid-processing revocation, busy-run protection, restored checkpoints, rejected external paths, API controls, backoff, interrupted-run recovery, mismatched entity/revisions, and timeout recording.

The concurrency test deliberately removes process-local serialization, synchronizes two computations, and verifies one persisted row and one shared ID. This closes a conflict observed while running two local servers at the same time.

Independent reference verification reads the two CSV files using Decimal without importing the application calculation engine. It confirms net SAR 2,349,483.58, gross SAR 2,701,906.23, receipts SAR 2,114,649.31, outstanding SAR 587,256.92 and 63 invoices without a payment. The app itself still reads the bank PDF.

## Browser results
The existing `scripts/check_ui.py` passed through a real local server using Chromium 145 at desktop 1440×1050 and mobile 390×844. Checks cover clean/dirty samples, highlighted 90+ balance, exactly three overview anomaly prompts, ledger search, repeated approval, normal status progression, timeout, the correlation simulation, actual XLSX/PDF file-picker upload, no document-width overflow, and no page JavaScript errors.

A separate visual pass inspected desktop/mobile/exception views and produced a **four-page** example analyst brief from the improved scenario. The **five-page** written submission, flow diagram, tables and statement PDF were rendered for visual inspection. Headline values round to whole SAR; narrative/export figures retain cents.

## Real HTTP source automation validation
`python scripts/check_automation_ui.py` passed with the one-command launcher, a workbench server on 8000, a separate mock source server on 8001, temporary isolated SQLite databases and Chromium 145. It exercised explicit consent, source pull, no-change handling, **two actual scheduled runs** (including one subsequent interval without a user sync), pause, changed invoices with five blockers, opening the imported package, HTTP 503, wrong checksum, recovery, and revocation that rejects another pull. Desktop/mobile source controls and history were inspected; no page JavaScript errors or page-width overflow were observed. Mock sources are real HTTP endpoints in the test; they are not real ERP/bank providers.

The 53 tests ran in a freshly created Python 3.12 virtual environment installed from requirements-ui.txt. `pip check` reported no broken requirements. httpx is now a runtime dependency. The unchanged reference CSV verification was rerun successfully. No fixture regeneration was necessary for source automation; financial values remain the v1.1 scenario.

## Fixture results
| Measure | Improved clean scenario |
| --- | --- |
| Valid invoices / bank transactions / matched receipts | 311 / 362 / 300 |
| Structural blockers | 0 |
| Net / gross invoiced | SAR 2,349,483.58 / SAR 2,701,906.23 |
| Matched collections / outstanding | SAR 2,114,649.31 / SAR 587,256.92 |
| Overdue / more than 90 days overdue | SAR 275,131.68 / SAR 101,662.97 |
| Share of overdue above 90 days | 36.95% |
| Not-overdue receivables | SAR 312,125.24 |
| Largest overdue customer | CUST-03, SAR 163,896.93 |
| Top net-sales concentration | 32.54% |
| Owner inflows excluded / closing bank cash | SAR 100,000.00 / SAR 1,022,222.74 |

Dirty fixture: **312 input rows, 308 valid unique invoices, 5 blockers** (duplicate, three invalid rows and an unallocated-receipts category). Accepted metrics remain inspectable, but the package is blocked. Clean means structurally valid, not creditworthy.

## Validation limits
Docker files are optional examples and were not built because Docker was unavailable. No live bank, public deployment, real borrower validation, OCR/other-bank-layout test, penetration/load test or calibrated credit-model evaluation occurred. Authentication, real provider OAuth/consent and approval workflow, encrypted cloud storage and the PostgreSQL schema remain production design. Local fictional read consent, expiration, revocation, source pulling and recurring snapshot scheduling are implemented. The scheduler requires one running workbench worker; it is not a distributed job system. Docker source automation was not tested; the optional container example only starts the workbench. Repeated observed status is never treated as verified truth. Reported timings are test-run observations, not performance SLAs.
