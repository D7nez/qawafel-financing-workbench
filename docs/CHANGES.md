# Version 1.2
- Working HTTP pull from two separate fictional accounting/bank APIs; explicit read-scope consent and expiry; recurring synchronization; persisted checkpoints/run history.
- No-change runs skip file downloads/analysis. Changed snapshots produce a new or reused immutable package. Scope/hash/outage failures preserve the prior checkpoint and use bounded scheduled backoff.
- Demonstrates source changes, data correction, outage, checksum failure, pause and revocation. Source API contracts, full-snapshot limitations and real-provider roadmap are documented.
- One command starts both local processes. Python 3.12 is explicit in setup, including the private Arabic guide.

# Version 1.1
- Variable monthly invoice volumes, customer-specific lognormal order sizes, varied terms and separate customer payment profiles. Scenario assumptions and both seeds are recorded in manifest.json.
- Overview prioritizes 90+ overdue, the customer with largest overdue balance and not-overdue receivables. Adds per-customer arrears and weighted days to full settlement with paid-invoice counts and explicit censoring limits.
- Top three anomaly prompts ordered by outstanding/gross financial exposure; full flags/scores retained.
- Tiny native-float noise accepted within a documented tolerance; real fractional cents rejected. ROUND_HALF_UP consistent across generator/calculations. Streamed XLSX limits work without dimensions; blank-row source locations retained.
- Bank lab separates normal progression, invalid reversal and stale timestamps; includes timeout guidance and a reproducible error-correlation illustration. No observed state is promoted to verified truth.
- Five-page written submission, concise three-request bank-call script, first-person AI disclosure without unperformed personal review claims.
- Public project archive excludes the private Arabic learning guide and runtime/cache files. No duplicate README copies are included.
- Concurrent identical analyses resolve to one canonical SQLite result even with competing writers.
- Automated tests, browser checks, generator and PDF rebuilt for the changed data; clean-environment verification is recorded in validation.md.
