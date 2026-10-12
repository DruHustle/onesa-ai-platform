-- 001_initial.sql
CREATE TABLE users (id uuid PRIMARY KEY, email text UNIQUE NOT NULL, password_hash text NOT NULL, role text NOT NULL CHECK(role IN ('owner','administrator','editor','business','hr','viewer')), mfa_secret text, mfa_last_step bigint NOT NULL DEFAULT -1, disabled boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE sessions (token_hash text PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE, csrf text NOT NULL, expires_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX sessions_user ON sessions(user_id);
CREATE TABLE recovery_tokens (token_hash text PRIMARY KEY, user_id uuid REFERENCES users(id) ON DELETE CASCADE, expires_at timestamptz NOT NULL);
CREATE TABLE content (id uuid PRIMARY KEY, kind text NOT NULL CHECK(kind IN ('page','product','article','job','research','section')), slug text NOT NULL CHECK(slug ~ '^[a-z0-9][a-z0-9-]*$'), locale text NOT NULL CHECK(locale IN ('en','de')), title text NOT NULL, summary text NOT NULL DEFAULT '', body text NOT NULL DEFAULT '', metadata jsonb NOT NULL DEFAULT '{}', state text NOT NULL DEFAULT 'draft' CHECK(state IN ('draft','published','archived')), publish_at timestamptz, author_id uuid REFERENCES users(id), revision integer NOT NULL DEFAULT 1, updated_at timestamptz NOT NULL DEFAULT now(), UNIQUE(kind,slug,locale));
CREATE INDEX content_public ON content(locale,kind,state);
CREATE TABLE revisions (id bigserial PRIMARY KEY, content_id uuid REFERENCES content(id) ON DELETE CASCADE, snapshot jsonb NOT NULL, actor_id uuid REFERENCES users(id), created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE enquiries (id uuid PRIMARY KEY, category text NOT NULL CHECK(category IN ('general','enterprise','partnership','research','media')), name text NOT NULL, email text NOT NULL, organization text NOT NULL DEFAULT '', message text NOT NULL, locale text NOT NULL CHECK(locale IN ('en','de')), status text NOT NULL DEFAULT 'new' CHECK(status IN ('new','active','closed')), owner_id uuid REFERENCES users(id), notes text NOT NULL DEFAULT '', follow_up_at timestamptz, consent_at timestamptz NOT NULL DEFAULT now(), created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX enquiries_status ON enquiries(status,created_at);
CREATE TABLE files (id uuid PRIMARY KEY, filename text NOT NULL, mime text NOT NULL, size integer NOT NULL CHECK(size>0 AND size<=10485760), storage_key text UNIQUE NOT NULL, sha256 text NOT NULL, classification text NOT NULL CHECK(classification IN ('public','internal','confidential','applicant')), scan_status text NOT NULL DEFAULT 'quarantine' CHECK(scan_status IN ('quarantine','clean','rejected')), approval text NOT NULL DEFAULT 'pending' CHECK(approval IN ('pending','approved','rejected')), version integer NOT NULL DEFAULT 1, title text NOT NULL, owner_id uuid REFERENCES users(id), review_at timestamptz, association text, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE applications (id uuid PRIMARY KEY, job_id uuid NOT NULL REFERENCES content(id), name text NOT NULL, email text NOT NULL, message text NOT NULL DEFAULT '', file_id uuid UNIQUE NOT NULL REFERENCES files(id), status text NOT NULL DEFAULT 'new' CHECK(status IN ('new','review','interview','rejected','hired')), notes text NOT NULL DEFAULT '', consent_at timestamptz NOT NULL DEFAULT now(), delete_after timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE audit (id bigserial PRIMARY KEY, actor_id uuid REFERENCES users(id), action text NOT NULL, record_id text, request_id text, created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX audit_date ON audit(created_at);
CREATE TABLE jobs (id uuid PRIMARY KEY, kind text NOT NULL CHECK(kind IN ('email','reminder')), dedupe_key text UNIQUE NOT NULL, payload jsonb NOT NULL, status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','running','accepted','failed')), attempts integer NOT NULL DEFAULT 0, run_at timestamptz NOT NULL DEFAULT now(), locked_at timestamptz, last_error text, created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX jobs_pending ON jobs(status,run_at);
CREATE TABLE rate_limits (key text PRIMARY KEY, hits integer NOT NULL, expires_at timestamptz NOT NULL);
CREATE TABLE facts (key text PRIMARY KEY, value text, status text NOT NULL DEFAULT 'supplied' CHECK(status IN ('supplied','verified','missing')), source text NOT NULL, verified_by uuid REFERENCES users(id), verified_at timestamptz);
INSERT INTO facts(key,value,status,source) VALUES ('legal_name','Onesa UG (haftungsbeschränkt)','supplied','User implementation directive'),('location','Heidelberg, Germany','supplied','User implementation directive'),('register_number','HRB 757830','supplied','User implementation directive'),('register_court','Amtsgericht Mannheim','supplied','User implementation directive'),('director','Andrew Gotora','supplied','User implementation directive'),('address',NULL,'missing','Official register extract required'),('contact_email',NULL,'missing','Company approval required');
CREATE TABLE settings (key text PRIMARY KEY, value jsonb NOT NULL);
INSERT INTO settings VALUES ('legal', '{"impressumApproved":false,"privacyApproved":false,"recruitmentApproved":false,"providersReviewed":false}'),('retention','{"enquiryDays":365,"applicationDays":180}');
CREATE TABLE templates (key text PRIMARY KEY, title text NOT NULL, locale text NOT NULL DEFAULT 'en', body text NOT NULL, status text NOT NULL DEFAULT 'draft', version integer NOT NULL DEFAULT 1);


-- 002_security_workflows.sql
ALTER TABLE users ADD COLUMN mfa_pending text, ADD COLUMN enroll_hash text, ADD COLUMN enroll_expires timestamptz;
CREATE TABLE mfa_recovery (user_id uuid REFERENCES users(id) ON DELETE CASCADE, code_hash text NOT NULL, PRIMARY KEY(user_id,code_hash));
ALTER TABLE files ADD COLUMN parent_id uuid REFERENCES files(id), ADD COLUMN archived boolean NOT NULL DEFAULT false;
ALTER TABLE templates ADD CONSTRAINT templates_status CHECK(status IN ('draft','approved','archived'));
INSERT INTO settings VALUES ('brand','{"approved":false}');


-- 003_document_versions.sql
CREATE UNIQUE INDEX files_one_successor ON files(parent_id) WHERE parent_id IS NOT NULL;


-- 004_company_facts.sql
-- Correct only the original unverified seeded role inference; preserve reviewed records.
UPDATE facts SET value=NULL, status='missing', source='Founder supplied; director appointment requires official register evidence'
WHERE key='director' AND status='supplied' AND value='Andrew Gotora' AND source='User implementation directive';
INSERT INTO facts(key,value,status,source) VALUES
('founder','Andrew Gotora','supplied','Owner audit directive 2026-10-09; no ownership percentage inferred'),
('founding_year','2026','supplied','Owner audit directive 2026-10-09; exact incorporation date unverified')
ON CONFLICT(key) DO NOTHING;


-- 005_storage_deletion_outbox.sql
-- Metadata deletion and durable cleanup request commit together; physical deletion follows.
CREATE TABLE storage_deletions (
 storage_key text PRIMARY KEY CHECK(storage_key ~ '^[a-f0-9-]{36}$'),
 status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','running','accepted','failed')),
 attempts integer NOT NULL DEFAULT 0, run_at timestamptz NOT NULL DEFAULT now(),
 locked_at timestamptz, last_error text, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX storage_deletions_pending ON storage_deletions(status,run_at);


-- 006_bounded_transfers.sql
-- Additive durable transport; existing 10 MiB file and private/quarantine controls remain.
CREATE TABLE bounded_transfers (
 id uuid PRIMARY KEY,
 owner_id uuid REFERENCES users(id) ON DELETE CASCADE,
 peer_hash text NOT NULL,
 capability_hash text NOT NULL,
 scope text NOT NULL CHECK(scope IN ('application','document')),
 expected_bytes integer NOT NULL CHECK(expected_bytes BETWEEN 1 AND 15728640),
 checksum text NOT NULL,
 cursor integer NOT NULL DEFAULT 0,
 expires_at timestamptz NOT NULL DEFAULT now()+interval '20 minutes',
 result jsonb,
 result_status integer
);
CREATE INDEX bounded_transfers_expiry ON bounded_transfers(expires_at);
CREATE TABLE bounded_transfer_chunks (
 transfer_id uuid REFERENCES bounded_transfers(id) ON DELETE CASCADE,
 sequence integer NOT NULL CHECK(sequence>=0),
 encrypted_payload text NOT NULL,
 checksum text NOT NULL,
 PRIMARY KEY(transfer_id,sequence)
);


-- 007_operational_state.sql
CREATE TABLE operational_state (key text PRIMARY KEY, updated_at timestamptz NOT NULL DEFAULT now());
