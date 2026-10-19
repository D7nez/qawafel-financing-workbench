# Financing Evidence Workbench
**Version 1.2 · Abdulrahman Alrehaili · Qawafel Graduate Software Engineer assessment**

A local financing-evidence prototype: validate a wholesaler's invoices and bank statement, reconcile receipts, and help an analyst identify what needs attention. All data is fictional. This is an independent demonstration, not an official Qawafel product.

## Start here
Python **3.12** recommended. From this directory:
```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Windows activation: `.venv\Scripts\activate`. Open **http://127.0.0.1:8000**, then select **Run clean sample**. Fixtures are included; no generation step or API key is needed. After installation, the application and analysis work offline. Swagger /docs uses CDN assets; /openapi.json is local.

Keep the server on localhost and use fictional data: authentication and tenant isolation are not implemented. Docker files are an optional, **unverified** deployment example, not the tested setup path.

## New: source-to-analysis automation (mock APIs)
After installation, stop the old server with Ctrl+C and run:
```bash
python scripts/run_local.py
```
This starts the workbench on 8000 and **two fictional source APIs** on one separate local server at 8001. Open Source automation, grant explicit fictional read consent, then Sync sources now or start a 10/60-second recurring schedule. No upload is needed. Changed snapshots trigger analysis, unchanged hashes skip downloads, and errors/expiry/revocation are visible in persisted run history. Real ERP/bank connections and OAuth are not implemented.

Try an issues snapshot, 503 outage or checksum mismatch using the local controls; then restore Healthy. Revocation stops new reads and result publication; already downloaded processing may finish in the local cache. The scheduler needs a running server and one worker. The connector pulls full snapshots on change, not incremental production records. See **docs/automation.md** for the complete walkthrough, contract and boundaries. The optional Docker example supports the standalone workbench only; source automation is tested through the Python two-process launcher.

## What the analyst sees first
- **SAR 101,662.97 over 90 days overdue**: 36.95% of all overdue balances.
- **CUST-03 has SAR 163,896.93 overdue**: its fully paid invoices took 117.2 gross-amount-weighted days to collect (23 fully paid observations).
- **SAR 312,125.24 not-overdue receivables**: descriptive balance, not financing eligibility.

Supporting evidence: net sales **SAR 2,349,483.58**, matched receipts **SAR 2,114,649.31**, total overdue **SAR 275,131.68**, outstanding **SAR 587,256.92**, top-customer sales share **32.54%**, and **63** invoices with no matched payment. All figures are at **30 Sep 2026**. Recent not-due invoices explain some non-payment; no-payment is not synonymous with delinquency.

## Five-minute demo
1. Run the clean sample: 311 valid invoices, 10 customers, 362 bank transactions and zero structural blockers. Ready for analyst review is **not** approval.
2. Inspect aging and the top-five overdue customers. Payment duration is based on fully paid invoices only and is **not DSO**; unpaid invoices are explicitly excluded.
3. Open Invoice ledger and search `INV-202605-010`. This **deliberately planted sanity case** is a SAR 94,000 net / 108,100 gross order with 90-day terms, half collected. It tests retrieval of an obvious review case; it does not establish model accuracy.
4. Try data issues: the duplicate, three invalid rows and related unallocated receipts block readiness without inflating sales. Source rows remain visible.
5. Download the samples and upload them through the form. Repeating unchanged input reuses the analysis ID. Export JSON or print the analyst brief.
6. In Bank integration lab compare normal progression, invalid reversal, repeated approval and timeout. All unconfirmed observations remain UNVERIFIED/UNKNOWN. The error simulation demonstrates assumptions, not actual bank reliability.

## Included assessment deliverables
- `docs/Qawafel_Submission.pdf`: five-page written answers to Tasks 1, 2, 4, 5 and AI disclosure; source in `docs/submission.md`.
- `app/`, `data/`, `scripts/generate_data.py`: working Task 3 prototype and its reproducible data.
- `docs/schema.sql`: normalized PostgreSQL production **design**. Runtime persistence is a smaller SQLite JSON snapshot table.
- `docs/model-card.md`: anomaly-model purpose, settings and limitations.
- `docs/validation.md`: executed environment, test results and boundaries.
- `docs/Example_Analyst_Brief.pdf`: sample output from the improved clean scenario.

## Synthetic data design
Reporting window: **1 Oct 2025 to 30 Sep 2026**. Fictional Cedar Wholesale, one SAR grocery wholesaler/account. `data/manifest.json` records scenario seed **42**, payment seed **142**, monthly counts, customer profiles and the planted case.

Monthly invoice counts are **28, 27, 26, 21, 30, 33, 24, 25, 20, 23, 28, 26**. Orders follow customer-specific lognormal distributions (sigma 0.78) with stated bounds, modest growth and seasonal variation. Customer profiles have different payment terms, delays and non-payment tendencies; CUST-03 and CUST-09 are slower-paying scenarios. These choices are scenario assumptions, not a representative market sample or outcome fitted to review thresholds.

- `invoices_clean.xlsx` / `.csv`: 311 sales invoices. XLSX monetary cells are numeric. Clean means structurally valid, not healthy credit.
- `invoices_with_issues.xlsx` / `.csv`: duplicate at final row, negative amount at row 42, USD at row 82, malformed due date at row 122. Valid unique invoices remaining: 308.
- `bank_statement.pdf`: genuine PDF ingestion through pdfplumber, 12 closed months with opening/closing balances and 362 transactions. Only the supplied `QAWAFEL_SYNTHETIC_V1` text layout is supported. Other layouts/scans are rejected for review.
- `bank_transactions.csv`: independent reference ledger for inspection; **not** a substitute for PDF extraction in the application.

No opening receivables, credit notes, refunds, other currencies or real customers/accounts. Synthetic VAT is 15%. Owner inflows of SAR 100,000 are excluded from sales collections. Bank balance consistency does not establish authenticity.

**Largest realism gap:** every generated receipt carries an exact invoice reference. Real bank descriptions often do not. Production needs amount/date/customer candidate matching, batch allocation and ambiguity review; approximate candidates must not silently become confirmed matches. This prototype supports exact references and split payments only.

## Metric and AI boundaries
Net sales exclude VAT; collections / receivables include it. Match only accepted invoice IDs, receipts on/after issue and available gross balance. Unallocated receipts block readiness. Outstanding = gross less matched receipts; overdue = positive balance due before cutoff; not-overdue includes due today. 90+ means strictly over 90 days. The collection ratio is period receipts / gross period invoices, affected by recent invoices not yet due. Quarter comparison is last vs first three months, not year-on-year growth. Costs and debt schedules are absent: no profitability, affordability, default or lending decision is inferred.

Money is integer halalas and ROUND_HALF_UP. A native float within SAR **0.0000001** of a cent is normalized for representation noise; meaningful fractional cents and higher-precision text are rejected. Streamed workbook limits and source rows do not depend on producer dimension metadata.

Isolation Forest uses 200 trees, seed 42 and contamination 0.03. Features: log gross, payment terms and log customer-relative gross. Fit on each accepted upload (minimum 30 invoices). The 3% setting is a review-budget heuristic, unrelated to the bank's 3% status error, and forces a tail even on normal data. No predictive accuracy is claimed. The overview shows the top three flags by outstanding balance then gross amount; model score remains separate. All flags remain in exceptions and JSON. Illustrative >35% concentration and >10% overdue/gross triggers are independent of scenario outcomes and are not bank policy.

## API, state and persistence
- `POST /api/analyses`: multipart `invoices`, `bank_statement` -> Analysis.
- `POST /api/demo/clean` or `/api/demo/issues`: same ingestion pipeline.
- `GET /api/analyses/{id}` and `/{id}/export`: saved evidence / JSON attachment.
- `GET /api/samples/{name}`: whitelisted fixtures.
- `POST /api/bank-lab`: `{"observations":["PENDING","UNDER_REVIEW","APPROVED"]}`. Also accepts objects with `status` and timezone-aware `observed_at`. Strings have sequence only, no freshness guarantee.
- `POST /api/bank-lab/simulate`: seeded independent vs perfectly correlated 3% errors, conditioned on known PENDING; not a posterior correctness estimate.
- `GET /api/health`, `/openapi.json`, `/docs`.
- `/api/automation/*`: scoped demo consent, schedule, pull, scenario and run history; see docs/automation.md.

Limits: 5 MB/file, 12 MB/request with Content-Length, 10,000 invoice rows, 30 columns, 30 MB expanded XLSX and 40 PDF pages. Production requires streaming proxy limits, scanning, isolated workers and scoped access. SQLite snapshots in `runtime/analyses.sqlite3` are ignored by Git; `QAWAFEL_DB` can change the path. Original uploaded bytes are discarded after parsing; results/hashes remain until the local database is deleted. Cache key includes hashes, cutoff and calculation version. Version 1.2 prevents old result reuse; competing identical writers return the same canonical result.

## Reproduce and test
```bash
python -m pip install -r requirements-dev.txt
python scripts/generate_data.py
python -m pytest -q
python scripts/verify_fixture.py
python scripts/build_submission.py
```
`requirements-dev.txt` includes `requirements.txt`; reportlab is included for both generator and PDF rendering. Generation overwrites only named fixtures. Browser smoke check (separate optional dependencies):
```bash
python -m pip install -r requirements-ui.txt
python -m playwright install chromium
python scripts/check_ui.py
```
A system Chrome executable can be specified with `CHROME_EXECUTABLE`. See validation.md for actual results, the clean-environment installation check and untested production scope. `docs/CHANGES.md` lists changes, including v1.2 source automation.

## AI disclosure
I used ChatGPT/Codex to generate and refine the implementation, synthetic data, documentation and tests. The application uses local scikit-learn for exploratory anomaly detection and a deterministic template for the narrative brief. No runtime LLM, real customer data or real-provider API credentials are used. Executed checks and their environment are documented in `docs/validation.md`; they are not real-bank or production validation.

## Primary implementation references
- https://fastapi.tiangolo.com/tutorial/request-files/
- https://fastapi.tiangolo.com/tutorial/testing/
- https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html
- https://github.com/jsvine/pdfplumber
