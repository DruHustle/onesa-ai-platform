# Implemented PostgreSQL schema

Generated from SQLAlchemy metadata on 2026-10-09; real Alembic round-trip/metadata checks
pass on PostgreSQL/pgvector. UUIDs and timezone-aware timestamps are application defaults;
ORM defaults are not necessarily server defaults, so direct SQL inserts must supply required
values. All content queries also enforce owner predicates; foreign keys alone do not grant access.

## rate_buckets

| Field | Type | Nullable | Notes |
| --- | --- | --- | --- |
| key | `VARCHAR(64)` | False | primary key |
| count | `INTEGER` | False | ORM default 1 |
| expires_at | `DATETIME` | False | indexed |

Index `ix_rate_buckets_expires_at`: `expires_at`.

## users

| Field | Type | Nullable | Notes |
| --- | --- | --- | --- |
| email | `VARCHAR(254)` | False | unique |
| password_hash | `VARCHAR(256)` | False |  |
| display_name | `VARCHAR(80)` | False |  |
| status | `VARCHAR(20)` | False | ORM default 'active' |
| updated_at | `DATETIME` | False | ORM default now |
| id | `CHAR(32)` | False | primary key; ORM default uuid4 |
| created_at | `DATETIME` | False | ORM default now |

Check: `status IN ('active', 'disabled')`.

Unique: `email`.

## agent_runs

| Field | Type | Nullable | Notes |
| --- | --- | --- | --- |
| user_id | `CHAR(32)` | False | indexed; FK users.id, on delete CASCADE |
| goal | `VARCHAR` | False |  |
| status | `VARCHAR(20)` | False | ORM default 'running' |
| steps | `JSONB` | False | ORM default list |
| id | `CHAR(32)` | False | primary key; ORM default uuid4 |
| created_at | `DATETIME` | False | ORM default now |

Check: `status IN ('running', 'completed', 'failed', 'cancelled')`.

Index `ix_agent_runs_user_id`: `user_id`.

## auth_sessions

| Field | Type | Nullable | Notes |
| --- | --- | --- | --- |
| user_id | `CHAR(32)` | False | indexed; FK users.id, on delete CASCADE |
| token_hash | `VARCHAR(64)` | False | unique |
| csrf_hash | `VARCHAR(64)` | False |  |
| expires_at | `DATETIME` | False | indexed |
| revoked_at | `DATETIME` | True |  |
| id | `CHAR(32)` | False | primary key; ORM default uuid4 |
| created_at | `DATETIME` | False | ORM default now |

Unique: `token_hash`.

Index `ix_auth_sessions_expires_at`: `expires_at`.

Index `ix_auth_sessions_user_id`: `user_id`.

## conversations

| Field | Type | Nullable | Notes |
| --- | --- | --- | --- |
| user_id | `CHAR(32)` | False | indexed; FK users.id, on delete CASCADE |
| title | `VARCHAR(200)` | False | ORM default 'New conversation' |
| selected_model_id | `VARCHAR(80)` | False | ORM default 'default' |
| updated_at | `DATETIME` | False | ORM default now |
| active_run_id | `CHAR(32)` | True |  |
| lease_until | `DATETIME` | True |  |
| id | `CHAR(32)` | False | primary key; ORM default uuid4 |
| created_at | `DATETIME` | False | ORM default now |

Index `ix_conversations_user_id`: `user_id`.

Index `conversation_owner_updated`: `user_id`, `updated_at`.

## documents

| Field | Type | Nullable | Notes |
| --- | --- | --- | --- |
| user_id | `CHAR(32)` | False | indexed; FK users.id, on delete CASCADE |
| title | `VARCHAR(200)` | False |  |
| media_type | `VARCHAR(80)` | False |  |
| text | `VARCHAR` | False |  |
| checksum | `VARCHAR(64)` | False |  |
| embedding_version | `VARCHAR(256)` | False |  |
| id | `CHAR(32)` | False | primary key; ORM default uuid4 |
| created_at | `DATETIME` | False | ORM default now |

Unique: `user_id`, `checksum`.

Index `ix_documents_user_id`: `user_id`.

## trips

| Field | Type | Nullable | Notes |
| --- | --- | --- | --- |
| user_id | `CHAR(32)` | False | indexed; FK users.id, on delete CASCADE |
| destination | `VARCHAR(200)` | False |  |
| duration | `INTEGER` | False |  |
| budget | `FLOAT` | False |  |
| currency | `VARCHAR(3)` | False |  |
| preferences | `VARCHAR` | False |  |
| revision | `INTEGER` | False | ORM default 1 |
| itinerary | `JSONB` | False |  |
| updated_at | `DATETIME` | False | ORM default now |
| id | `CHAR(32)` | False | primary key; ORM default uuid4 |
| created_at | `DATETIME` | False | ORM default now |

Check: `budget > 0`.

Check: `duration BETWEEN 1 AND 14`.

Check: `revision > 0`.

Index `ix_trips_user_id`: `user_id`.

## document_chunks

| Field | Type | Nullable | Notes |
| --- | --- | --- | --- |
| document_id | `CHAR(32)` | False | indexed; FK documents.id, on delete CASCADE |
| position | `INTEGER` | False |  |
| text | `VARCHAR` | False |  |
| embedding_version | `VARCHAR(256)` | False |  |
| embedding | `VECTOR(256)` | False |  |
| id | `CHAR(32)` | False | primary key; ORM default uuid4 |
| created_at | `DATETIME` | False | ORM default now |

Unique: `document_id`, `position`.

Check: `position >= 0`.

Index `ix_document_chunks_document_id`: `document_id`.

## inference_runs

| Field | Type | Nullable | Notes |
| --- | --- | --- | --- |
| request_id | `CHAR(32)` | False |  |
| user_id | `CHAR(32)` | False | indexed; FK users.id, on delete CASCADE |
| conversation_id | `CHAR(32)` | False | FK conversations.id, on delete CASCADE |
| model_id | `VARCHAR(80)` | False | ORM default 'default' |
| status | `VARCHAR(20)` | False | ORM default 'running' |
| latency_ms | `INTEGER` | True |  |
| input_tokens | `INTEGER` | True |  |
| output_tokens | `INTEGER` | True |  |
| id | `CHAR(32)` | False | primary key; ORM default uuid4 |
| created_at | `DATETIME` | False | ORM default now |

Check: `status IN ('running', 'completed', 'failed', 'cancelled')`.

Check: `latency_ms >= 0 AND input_tokens >= 0 AND output_tokens >= 0`.

Index `ix_inference_runs_user_id`: `user_id`.

## messages

| Field | Type | Nullable | Notes |
| --- | --- | --- | --- |
| conversation_id | `CHAR(32)` | False | FK conversations.id, on delete CASCADE |
| role | `VARCHAR(20)` | False |  |
| content | `JSONB` | False |  |
| status | `VARCHAR(20)` | False | ORM default 'completed' |
| sequence | `INTEGER` | False |  |
| model_id | `VARCHAR(80)` | True |  |
| id | `CHAR(32)` | False | primary key; ORM default uuid4 |
| created_at | `DATETIME` | False | ORM default now |

Check: `sequence > 0`.

Check: `role IN ('user', 'assistant', 'system')`.

Check: `status IN ('completed', 'failed', 'cancelled')`.

Unique: `conversation_id`, `sequence`.

Messages use JSONB text/source content with future attachment extension space. Trip
itineraries and bounded agent steps are structured JSONB validated at the API boundary.
Documents retain extracted text/checksum and embedding version; chunks use vector(256).
Changing embedding dimensions requires a migration, separate version and reindexing.
Conversations carry active-run/lease fields for short-lock generation coordination.

Current model selection is configuration-only; immutable Phase B candidate metadata lives
in local registry files. Collection/group permissions, object storage, normalized agent/itinerary
children and dataset/deployment tables are future requirements, not existing tables.
