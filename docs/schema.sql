-- PostgreSQL production design only; local prototype stores immutable JSON snapshots.
CREATE TABLE organizations (id UUID PRIMARY KEY, legal_name TEXT NOT NULL, registration_reference TEXT);
CREATE TABLE financing_requests (
 id UUID PRIMARY KEY, org_id UUID NOT NULL REFERENCES organizations, period_start DATE NOT NULL,
 period_end DATE NOT NULL, amount_halalas BIGINT CHECK(amount_halalas>0), currency CHAR(3) NOT NULL DEFAULT 'SAR',
 state TEXT NOT NULL, CHECK(period_end>=period_start)
);
CREATE TABLE package_versions (
 id UUID PRIMARY KEY, request_id UUID NOT NULL REFERENCES financing_requests, version INTEGER NOT NULL,
 state TEXT NOT NULL, calculation_version TEXT NOT NULL, evidence_json JSONB NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(request_id,version)
);
CREATE TABLE documents (
 id UUID PRIMARY KEY, request_id UUID NOT NULL REFERENCES financing_requests, version INTEGER NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('invoices','bank_statement')), sha256 CHAR(64) NOT NULL,
 object_key TEXT NOT NULL, parser_version TEXT NOT NULL, UNIQUE(request_id,kind,version)
);
CREATE TABLE invoices (
 id UUID PRIMARY KEY, package_id UUID NOT NULL REFERENCES package_versions, external_id TEXT NOT NULL,
 customer_id TEXT NOT NULL, issued DATE NOT NULL, due DATE NOT NULL,
 net_halalas BIGINT NOT NULL CHECK(net_halalas>0), vat_halalas BIGINT NOT NULL CHECK(vat_halalas>=0),
 source_document_id UUID NOT NULL REFERENCES documents, source_row INTEGER NOT NULL CHECK(source_row>=2),
 UNIQUE(package_id,external_id), CHECK(due>=issued)
);
CREATE TABLE bank_transactions (
 id UUID PRIMARY KEY, package_id UUID NOT NULL REFERENCES package_versions, external_id TEXT NOT NULL,
 booked_date DATE NOT NULL, signed_halalas BIGINT NOT NULL CHECK(signed_halalas<>0), kind TEXT NOT NULL,
 reference TEXT, source_document_id UUID NOT NULL REFERENCES documents, source_page INTEGER CHECK(source_page>0),
 UNIQUE(package_id,external_id)
);
CREATE TABLE payment_allocations (
 id UUID PRIMARY KEY, invoice_id UUID NOT NULL REFERENCES invoices, transaction_id UUID NOT NULL REFERENCES bank_transactions,
 amount_halalas BIGINT NOT NULL CHECK(amount_halalas>0), UNIQUE(invoice_id,transaction_id)
);
-- Application transaction / row locks must ensure same package, receipt sign/type,
-- sum allocations <= receipt amount AND <= invoice gross; CHECK cannot enforce cross-row sums.
CREATE TABLE issues (
 id UUID PRIMARY KEY, package_id UUID NOT NULL REFERENCES package_versions, severity TEXT NOT NULL,
 code TEXT NOT NULL, source_locator JSONB NOT NULL, message TEXT NOT NULL,
 disposition TEXT, resolved_by UUID, resolved_at TIMESTAMPTZ
);
CREATE TABLE reviews (
 id UUID PRIMARY KEY, package_id UUID NOT NULL REFERENCES package_versions, actor_id UUID NOT NULL,
 approved BOOLEAN NOT NULL, consent_reference TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE bank_submissions (
 id UUID PRIMARY KEY, package_id UUID UNIQUE NOT NULL REFERENCES package_versions,
 idempotency_key UUID UNIQUE NOT NULL, bank_reference TEXT UNIQUE, state TEXT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE bank_observations (
 id UUID PRIMARY KEY, submission_id UUID NOT NULL REFERENCES bank_submissions, external_event_id TEXT UNIQUE,
 raw_status TEXT NOT NULL, source_timestamp TIMESTAMPTZ, observed_at TIMESTAMPTZ NOT NULL,
 verified_at TIMESTAMPTZ, confirmation_reference TEXT
);
CREATE TABLE outbox (
 id UUID PRIMARY KEY, submission_id UUID UNIQUE NOT NULL REFERENCES bank_submissions,
 attempt_count INTEGER NOT NULL DEFAULT 0, next_attempt_at TIMESTAMPTZ NOT NULL, dispatched_at TIMESTAMPTZ
);
CREATE TABLE audit_events (
 id UUID PRIMARY KEY, org_id UUID NOT NULL REFERENCES organizations, actor_id UUID,
 resource_id UUID NOT NULL, action TEXT NOT NULL, payload_hash CHAR(64) NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Before production: identity/users, org-scoped authorization/RLS, encryption/key
-- management, migrations, retention, append-only permissions, tenant-bound FK policy.
