# Model card - exploratory invoice exceptions (v1.2; algorithm unchanged)
**Purpose:** prioritize source-document review. **Not for:** credit scoring, fraud accusations, affordability, approval or rejection.

**Algorithm:** IsolationForest, 200 trees, contamination 0.03, random_state 42, n_jobs 1. Fit per upload (at least 30 accepted unique invoices). Features: log(1 + gross SAR), payment term days, log(1 + gross / same-customer median gross). No labels, pretrained model or cross-company training.

**Threshold:** 0.03 is an explicit, uncalibrated review-budget heuristic and unrelated to the bank's status error rate. It produces tail flags even on normal inputs. Negative decision-function values are model outliers, not probabilities.

**Display priority:** overview shows three flags ordered by unpaid gross balance, then original gross value, then anomaly score. All flags and scores remain in exceptions/export. This is a review-priority overlay, not a modification of the model score or a claim of causal feature attribution. A fully paid bulk invoice may be a lower financial priority than an unpaid unusual invoice.

**Data:** 311 fictional invoices, variable monthly volumes, customer-specific right-skewed order sizes and different payment profiles. Seed 42 for invoices and 142 for payments. INV-202605-010 is deliberately planted: SAR 94,000 net with 90-day terms and half collected. Similar terms occur naturally elsewhere. Detecting the planted order is a sanity check, not a representative accuracy test. Its financial exposure, not surprise discovery, explains its display priority.

**Validation:** repeatability, planted-case retrieval and display-order tests. No measured precision, recall, calibrated default probabilities or production readiness. Production would need analyst-labeled exceptions, precision at a review budget, customer-size/seasonality checks, stability monitoring and recorded review outcomes.

**Limits:** genuine bulk orders, small/seasonal purchases and unusual terms may be flagged. Customer medians can be contaminated; small groups are unstable. Unpaid invoices are not necessarily overdue. Human verification remains necessary. Invalid data is quarantined and blocks package readiness independently of anomaly output.
