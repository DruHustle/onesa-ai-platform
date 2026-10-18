# Portal database schema

Generated from 11 pinned PostgreSQL migrations plus source-defined migration tracking, including internal governance. Schema definitions only; no live records or credentials. This is a source reference, not evidence of applied production migrations; consult the current deployment receipts and documentation-hosting guide. Preserve constraints, immutable approval triggers and migration checksums. Use the migration runner rather than applying this reference as a replacement migration plan.

```sql
-- Migration-runner metadata; application tables follow.
CREATE TABLE IF NOT EXISTS schema_migrations(name text PRIMARY KEY, checksum text NOT NULL, applied_at timestamptz DEFAULT now());

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

-- 008_privacy_governance.sql
-- Additive internal CMS extension. No public content, retention settings or jobs change.
CREATE TABLE governance_records (
 stable_id text PRIMARY KEY CHECK(stable_id ~ '^(ONESA-PRIV-(RET|PROC|DEC)-001|(RET|PROC|DEC)-[0-9]{2})$'),
 kind text NOT NULL CHECK(kind IN ('document','retention','processor','decision')),
 document_id text REFERENCES governance_records(stable_id) ON DELETE RESTRICT,
 classification text NOT NULL DEFAULT 'INTERNAL' CHECK(classification='INTERNAL'),
 current_revision integer NOT NULL CHECK(current_revision>0),
 effective_revision integer,
 archived boolean NOT NULL DEFAULT false,
 seed_fingerprint text CHECK(seed_fingerprint ~ '^[a-f0-9]{64}$'),
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 CHECK((kind='document' AND document_id IS NULL) OR (kind<>'document' AND document_id IS NOT NULL))
);
CREATE TABLE governance_versions (
 record_id text NOT NULL REFERENCES governance_records(stable_id) ON DELETE RESTRICT,
 revision integer NOT NULL CHECK(revision>0),
 version_label text NOT NULL,
 title text NOT NULL,
 owner text NOT NULL,
 product_scopes text[] NOT NULL,
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
 evidence_refs text[] NOT NULL DEFAULT '{}',
 status text NOT NULL DEFAULT 'draft_pending_review' CHECK(status IN ('draft','draft_pending_review','pending_review','approved','needs_changes','rejected')),
 source_fingerprint text NOT NULL CHECK(source_fingerprint ~ '^[a-f0-9]{64}$'),
 source_file text,
 created_by uuid REFERENCES users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL DEFAULT now(),
 review_due_at timestamptz,
 effective_at timestamptz,
 approved_by uuid REFERENCES users(id) ON DELETE RESTRICT,
 approved_email text,
 approved_role text CHECK(approved_role IS NULL OR approved_role='owner'),
 approved_at timestamptz,
 approval_scope text,
 approval_evidence_refs text[],
 PRIMARY KEY(record_id,revision),
 CHECK(status<>'approved' OR (approved_by IS NOT NULL AND approved_email IS NOT NULL AND approved_role IS NOT NULL AND approved_role='owner' AND approved_at IS NOT NULL AND effective_at IS NOT NULL AND review_due_at IS NOT NULL AND approval_scope IS NOT NULL AND length(approval_scope)>=10 AND approval_evidence_refs IS NOT NULL AND cardinality(approval_evidence_refs)>0 AND review_due_at>effective_at)),
 CHECK(status='approved' OR (approved_at IS NULL AND approved_by IS NULL AND effective_at IS NULL))
);
ALTER TABLE governance_records ADD CONSTRAINT governance_current_version FOREIGN KEY(stable_id,current_revision) REFERENCES governance_versions(record_id,revision) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE governance_records ADD CONSTRAINT governance_effective_version FOREIGN KEY(stable_id,effective_revision) REFERENCES governance_versions(record_id,revision) DEFERRABLE INITIALLY DEFERRED;
CREATE TABLE governance_events (
 id bigserial PRIMARY KEY,
 record_id text NOT NULL,
 revision integer NOT NULL,
 actor_id uuid REFERENCES users(id) ON DELETE RESTRICT,
 actor_email text,
 actor_role text,
 action text NOT NULL,
 note text NOT NULL DEFAULT '',
 scope text NOT NULL DEFAULT '',
 evidence_refs text[] NOT NULL DEFAULT '{}',
 request_id text,
 created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(record_id,revision) REFERENCES governance_versions(record_id,revision) ON DELETE RESTRICT
);
CREATE INDEX governance_kind ON governance_records(kind,archived);
CREATE INDEX governance_reviews ON governance_versions(review_due_at,status);
CREATE INDEX governance_events_record ON governance_events(record_id,id);
CREATE FUNCTION protect_governance_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' OR OLD.status='approved' THEN
  RAISE EXCEPTION 'Governance versions must be preserved; approved versions are immutable' USING ERRCODE='23514';
 END IF;
 IF (to_jsonb(NEW)-ARRAY['status','review_due_at','effective_at','approved_by','approved_email','approved_role','approved_at','approval_scope','approval_evidence_refs']) IS DISTINCT FROM
    (to_jsonb(OLD)-ARRAY['status','review_due_at','effective_at','approved_by','approved_email','approved_role','approved_at','approval_scope','approval_evidence_refs']) THEN
  RAISE EXCEPTION 'Amendments require a new governance version' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER governance_version_immutable BEFORE UPDATE OR DELETE ON governance_versions FOR EACH ROW EXECUTE FUNCTION protect_governance_version();
CREATE FUNCTION protect_governance_event() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Governance review events are append-only' USING ERRCODE='23514'; END $$;
CREATE TRIGGER governance_event_immutable BEFORE UPDATE OR DELETE ON governance_events FOR EACH ROW EXECUTE FUNCTION protect_governance_event();
REVOKE ALL ON governance_records,governance_versions,governance_events FROM PUBLIC;

-- 009_privacy_lifecycle.sql
-- Additive control plane only. No policy approval, business-data deletion or timer.
SET LOCAL lock_timeout='2s';
SET LOCAL statement_timeout='30s';

ALTER TABLE enquiries ADD COLUMN closed_at timestamptz;
ALTER TABLE applications ADD COLUMN rejected_at timestamptz;
ALTER TABLE files ADD COLUMN purpose_end_at timestamptz;
CREATE INDEX privacy_closed_enquiries ON enquiries(closed_at,id) WHERE status='closed';
CREATE INDEX privacy_rejected_applications ON applications(rejected_at,id) WHERE status='rejected';
CREATE INDEX privacy_ended_files ON files(purpose_end_at,id) WHERE purpose_end_at IS NOT NULL;

-- Do not invent historical outcome dates for existing closed/rejected records.
CREATE FUNCTION privacy_track_outcome() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_TABLE_NAME='enquiries' AND NEW.status IS DISTINCT FROM OLD.status THEN
  NEW.closed_at=CASE WHEN NEW.status='closed' THEN now() ELSE NULL END;
 ELSIF TG_TABLE_NAME='applications' AND NEW.status IS DISTINCT FROM OLD.status THEN
  NEW.rejected_at=CASE WHEN NEW.status='rejected' THEN now() ELSE NULL END;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER privacy_enquiry_outcome BEFORE UPDATE OF status ON enquiries FOR EACH ROW EXECUTE FUNCTION privacy_track_outcome();
CREATE TRIGGER privacy_application_outcome BEFORE UPDATE OF status ON applications FOR EACH ROW EXECUTE FUNCTION privacy_track_outcome();

CREATE TABLE privacy_holds (
 id uuid PRIMARY KEY,
 target_kind text NOT NULL CHECK(target_kind IN ('enquiry','application','file')),
 target_id uuid NOT NULL,
 reason text NOT NULL CHECK(length(reason) BETWEEN 10 AND 2000),
 evidence_refs text[] NOT NULL CHECK(cardinality(evidence_refs) BETWEEN 1 AND 20),
 created_by uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL DEFAULT now(),
 released_by uuid REFERENCES users(id) ON DELETE RESTRICT,
 released_at timestamptz,
 release_reason text,
 version integer NOT NULL DEFAULT 1 CHECK(version IN (1,2)),
 intent_sha256 text NOT NULL CHECK(intent_sha256 ~ '^[a-f0-9]{64}$'),
 CHECK((released_at IS NULL AND released_by IS NULL AND release_reason IS NULL AND version=1)
    OR (released_at IS NOT NULL AND released_by IS NOT NULL AND release_reason IS NOT NULL AND length(release_reason)>=10 AND version=2))
);
CREATE INDEX privacy_active_holds ON privacy_holds(target_kind,target_id) WHERE released_at IS NULL;

CREATE TABLE privacy_lifecycle_requests (
 id uuid PRIMARY KEY,
 request_kind text NOT NULL CHECK(request_kind IN ('erasure','retention')),
 case_reference text NOT NULL CHECK(length(case_reference) BETWEEN 1 AND 2000),
 identity_evidence_refs text[] NOT NULL CHECK(cardinality(identity_evidence_refs) BETWEEN 1 AND 20),
 created_by uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL DEFAULT now(),
 state text NOT NULL DEFAULT 'planned' CHECK(state IN ('planned','cancelled','executing','storage_pending','completed','partial')),
 policy_id text,
 policy_revision integer,
 plan_sha256 text NOT NULL CHECK(plan_sha256 ~ '^[a-f0-9]{64}$'),
 plan jsonb NOT NULL CHECK(jsonb_typeof(plan)='object'),
 intent_sha256 text NOT NULL CHECK(intent_sha256 ~ '^[a-f0-9]{64}$'),
 reviewed_by uuid REFERENCES users(id) ON DELETE RESTRICT,
 reviewed_at timestamptz,
 cancelled_at timestamptz,
 completed_at timestamptz,
 version integer NOT NULL DEFAULT 1 CHECK(version>0),
 FOREIGN KEY(policy_id,policy_revision) REFERENCES governance_versions(record_id,revision) ON DELETE RESTRICT,
 CHECK((request_kind='erasure' AND policy_id IS NULL AND policy_revision IS NULL)
    OR (request_kind='retention' AND policy_id IS NOT NULL AND policy_revision IS NOT NULL))
);
CREATE INDEX privacy_requests_created ON privacy_lifecycle_requests(created_at DESC,id);
CREATE TABLE privacy_lifecycle_targets (
 request_id uuid NOT NULL REFERENCES privacy_lifecycle_requests(id) ON DELETE RESTRICT,
 target_kind text NOT NULL CHECK(target_kind IN ('enquiry','application','file')),
 target_id uuid NOT NULL,
 record_sha256 text CHECK(record_sha256 ~ '^[a-f0-9]{64}$'),
 result text NOT NULL CHECK(result IN ('planned','held','not_due','not_found','deleted','storage_pending','failed','skipped')),
 result_code text NOT NULL,
 storage_key text,
 updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(request_id,target_kind,target_id)
);
CREATE TABLE privacy_lifecycle_events (
 id bigserial PRIMARY KEY,
 lifecycle_request_id uuid REFERENCES privacy_lifecycle_requests(id) ON DELETE RESTRICT,
 hold_id uuid REFERENCES privacy_holds(id) ON DELETE RESTRICT,
 actor_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 action text NOT NULL,
 note text NOT NULL DEFAULT '',
 evidence_refs text[] NOT NULL DEFAULT '{}',
 http_request_id text,
 created_at timestamptz NOT NULL DEFAULT now(),
 CHECK(lifecycle_request_id IS NOT NULL OR hold_id IS NOT NULL)
);
CREATE INDEX privacy_events_request ON privacy_lifecycle_events(lifecycle_request_id,id);
CREATE INDEX privacy_events_hold ON privacy_lifecycle_events(hold_id,id);
CREATE TRIGGER privacy_events_immutable BEFORE UPDATE OR DELETE ON privacy_lifecycle_events FOR EACH ROW EXECUTE FUNCTION protect_governance_event();

CREATE FUNCTION privacy_protect_hold() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Privacy hold history must be preserved' USING ERRCODE='23514'; END IF;
 IF OLD.released_at IS NOT NULL OR
  (to_jsonb(NEW)-ARRAY['released_by','released_at','release_reason','version']) IS DISTINCT FROM
  (to_jsonb(OLD)-ARRAY['released_by','released_at','release_reason','version']) THEN
  RAISE EXCEPTION 'Only explicit release of an active privacy hold is permitted' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER privacy_hold_history BEFORE UPDATE OR DELETE ON privacy_holds FOR EACH ROW EXECUTE FUNCTION privacy_protect_hold();

CREATE FUNCTION privacy_prevent_held_delete() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE target text := TG_ARGV[0];
BEGIN
 PERFORM pg_advisory_xact_lock(hashtextextended('privacy:'||target||':'||OLD.id::text,0));
 IF EXISTS(SELECT 1 FROM privacy_holds WHERE target_kind=target AND target_id=OLD.id AND released_at IS NULL) THEN
  RAISE EXCEPTION 'An active privacy hold prevents deletion' USING ERRCODE='23514',CONSTRAINT='privacy_active_hold';
 END IF;
 IF target='application' THEN
  IF EXISTS(SELECT 1 FROM privacy_holds WHERE target_kind='file' AND target_id=OLD.file_id AND released_at IS NULL) THEN
   RAISE EXCEPTION 'An associated file has an active privacy hold' USING ERRCODE='23514',CONSTRAINT='privacy_active_hold';
  END IF;
 END IF;
 IF target='file' AND EXISTS(SELECT 1 FROM privacy_holds h JOIN applications a ON a.id=h.target_id WHERE h.target_kind='application' AND a.file_id=OLD.id AND h.released_at IS NULL) THEN
  RAISE EXCEPTION 'The application has an active privacy hold' USING ERRCODE='23514',CONSTRAINT='privacy_active_hold';
 END IF;
 RETURN OLD;
END $$;
CREATE TRIGGER privacy_enquiry_hold BEFORE DELETE ON enquiries FOR EACH ROW EXECUTE FUNCTION privacy_prevent_held_delete('enquiry');
CREATE TRIGGER privacy_application_hold BEFORE DELETE ON applications FOR EACH ROW EXECUTE FUNCTION privacy_prevent_held_delete('application');
CREATE TRIGGER privacy_file_hold BEFORE DELETE ON files FOR EACH ROW EXECUTE FUNCTION privacy_prevent_held_delete('file');
REVOKE ALL ON privacy_holds,privacy_lifecycle_requests,privacy_lifecycle_targets,privacy_lifecycle_events FROM PUBLIC;

-- Append-only identities, not copies of erased personal data. No deletion is executed here.
SET LOCAL lock_timeout='2s';
SET LOCAL statement_timeout='30s';
CREATE TABLE privacy_erasure_journal (
 id bigserial PRIMARY KEY,
 target_kind text NOT NULL CHECK(target_kind IN ('enquiry','application','file')),
 target_id uuid NOT NULL,
 erased_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX privacy_erasure_journal_time ON privacy_erasure_journal(erased_at,id);
CREATE TRIGGER privacy_erasure_journal_immutable BEFORE UPDATE OR DELETE ON privacy_erasure_journal FOR EACH ROW EXECUTE FUNCTION protect_governance_event();
CREATE FUNCTION privacy_record_erasure() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 INSERT INTO privacy_erasure_journal(target_kind,target_id) VALUES(TG_ARGV[0],OLD.id);
 RETURN OLD;
END $$;
CREATE TRIGGER privacy_record_enquiry_erasure AFTER DELETE ON enquiries FOR EACH ROW EXECUTE FUNCTION privacy_record_erasure('enquiry');
CREATE TRIGGER privacy_record_application_erasure AFTER DELETE ON applications FOR EACH ROW EXECUTE FUNCTION privacy_record_erasure('application');
CREATE TRIGGER privacy_record_file_erasure AFTER DELETE ON files FOR EACH ROW EXECUTE FUNCTION privacy_record_erasure('file');
REVOKE ALL ON privacy_erasure_journal FROM PUBLIC;

-- Preserve reviewed plan identities and monotonic request history at the SQL boundary.
SET LOCAL lock_timeout='2s';
SET LOCAL statement_timeout='30s';
CREATE FUNCTION privacy_protect_request() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Lifecycle request history must be preserved' USING ERRCODE='23514'; END IF;
 IF (to_jsonb(NEW)-ARRAY['state','reviewed_by','reviewed_at','cancelled_at','completed_at','version']) IS DISTINCT FROM
    (to_jsonb(OLD)-ARRAY['state','reviewed_by','reviewed_at','cancelled_at','completed_at','version']) THEN
  RAISE EXCEPTION 'Lifecycle plan identity is immutable' USING ERRCODE='23514';
 END IF;
 IF (
  (OLD.state='planned' AND NEW.state='executing' AND NEW.version=OLD.version AND NEW.reviewed_by IS NOT NULL AND NEW.reviewed_at IS NOT NULL AND NEW.cancelled_at IS NULL AND NEW.completed_at IS NULL) OR
  (OLD.state='planned' AND NEW.state='cancelled' AND NEW.version=OLD.version+1 AND NEW.cancelled_at IS NOT NULL AND NEW.reviewed_by IS NULL AND NEW.reviewed_at IS NULL AND NEW.completed_at IS NULL) OR
  (OLD.state='executing' AND NEW.state IN ('partial','storage_pending') AND NEW.version=OLD.version+1 AND NEW.reviewed_by=OLD.reviewed_by AND NEW.reviewed_at=OLD.reviewed_at AND NEW.cancelled_at IS NULL AND NEW.completed_at IS NULL) OR
  (OLD.state IN ('partial','storage_pending') AND NEW.state='completed' AND NEW.version=OLD.version+1 AND NEW.completed_at IS NOT NULL AND NEW.reviewed_by=OLD.reviewed_by AND NEW.reviewed_at=OLD.reviewed_at AND NEW.cancelled_at IS NULL)
 ) IS NOT TRUE THEN RAISE EXCEPTION 'Invalid lifecycle transition' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER privacy_request_integrity BEFORE UPDATE OR DELETE ON privacy_lifecycle_requests FOR EACH ROW EXECUTE FUNCTION privacy_protect_request();
CREATE FUNCTION privacy_protect_target() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Lifecycle target history must be preserved' USING ERRCODE='23514'; END IF;
 IF NEW.request_id IS DISTINCT FROM OLD.request_id OR NEW.target_kind IS DISTINCT FROM OLD.target_kind OR NEW.target_id IS DISTINCT FROM OLD.target_id OR NEW.record_sha256 IS DISTINCT FROM OLD.record_sha256 THEN
  RAISE EXCEPTION 'Lifecycle target identity is immutable' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER privacy_target_integrity BEFORE UPDATE OR DELETE ON privacy_lifecycle_targets FOR EACH ROW EXECUTE FUNCTION privacy_protect_target();

-- 010_engineering_identity.sql
-- Separate documentation identities. No administrative role, existing account or Access policy is changed.
SET LOCAL lock_timeout='2s';
SET LOCAL statement_timeout='30s';
CREATE TABLE engineering_memberships (
 id uuid PRIMARY KEY,
 email text UNIQUE NOT NULL CHECK(email=lower(email)),
 enabled boolean NOT NULL DEFAULT false,
 access_policy_evidence text NOT NULL,
 approved_by uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 approved_at timestamptz NOT NULL DEFAULT now(),
 revision integer NOT NULL DEFAULT 1 CHECK(revision>0)
);
CREATE TABLE engineering_identity_records (
 model text NOT NULL,
 id text NOT NULL,
 encrypted_payload text NOT NULL,
 uid text,
 grant_id text,
 account_id text,
 expires_at timestamptz NOT NULL,
 consumed_at bigint,
 PRIMARY KEY(model,id)
);
CREATE INDEX engineering_identity_uid ON engineering_identity_records(model,uid) WHERE uid IS NOT NULL;
CREATE INDEX engineering_identity_grant ON engineering_identity_records(grant_id) WHERE grant_id IS NOT NULL;
CREATE INDEX engineering_identity_expiry ON engineering_identity_records(expires_at);
CREATE TABLE engineering_email_challenges (
 interaction_uid text PRIMARY KEY,
 membership_id uuid REFERENCES engineering_memberships(id) ON DELETE CASCADE,
 code_hash text NOT NULL,
 attempts integer NOT NULL DEFAULT 0 CHECK(attempts BETWEEN 0 AND 5),
 expires_at timestamptz NOT NULL,
 consumed_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now()
);
REVOKE ALL ON engineering_memberships,engineering_identity_records,engineering_email_challenges FROM PUBLIC;

-- 011_access_registration.sql
-- Registration is separate from authorization; no existing account or approval is changed.
SET LOCAL lock_timeout='2s';
SET LOCAL statement_timeout='30s';
CREATE TABLE access_registrations (
 id uuid PRIMARY KEY,
 email text NOT NULL CHECK(email=lower(email)),
 audience text NOT NULL CHECK(audience IN ('admin','engineering')),
 display_name text NOT NULL,
 password_hash text,
 state text NOT NULL DEFAULT 'unverified' CHECK(state IN ('unverified','pending','approved','rejected')),
 email_verified_at timestamptz,
 reviewed_by uuid REFERENCES users(id) ON DELETE RESTRICT,
 review_note text NOT NULL DEFAULT '',
 revision integer NOT NULL DEFAULT 1 CHECK(revision>0),
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(email,audience)
);
CREATE TABLE access_links (
 token_hash text PRIMARY KEY,
 purpose text NOT NULL CHECK(purpose IN ('registration','admin','engineering')),
 registration_id uuid REFERENCES access_registrations(id) ON DELETE CASCADE,
 user_id uuid REFERENCES users(id) ON DELETE CASCADE,
 membership_id uuid REFERENCES engineering_memberships(id) ON DELETE CASCADE,
 interaction_uid text,
 identity_hash text,
 expires_at timestamptz NOT NULL,
 consumed_at timestamptz,
 attempts integer NOT NULL DEFAULT 0 CHECK(attempts BETWEEN 0 AND 5),
 created_at timestamptz NOT NULL DEFAULT now(),
 CHECK((purpose='registration' AND registration_id IS NOT NULL AND user_id IS NULL AND membership_id IS NULL AND interaction_uid IS NULL)
    OR (purpose='admin' AND user_id IS NOT NULL AND registration_id IS NULL AND membership_id IS NULL AND interaction_uid IS NULL)
    OR (purpose='engineering' AND membership_id IS NOT NULL AND interaction_uid IS NOT NULL AND registration_id IS NULL AND user_id IS NULL))
);
CREATE INDEX access_links_expiry ON access_links(expires_at);
CREATE TABLE engineering_credentials (
 membership_id uuid PRIMARY KEY REFERENCES engineering_memberships(id) ON DELETE CASCADE,
 password_hash text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
REVOKE ALL ON access_registrations,access_links,engineering_credentials FROM PUBLIC;
```
