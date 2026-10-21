# Implemented AI PostgreSQL schema

Generated from current SQLAlchemy PostgreSQL types and the Alembic revision 20261021_industrial. Schema metadata is not live database data. Foreign keys do not replace user ownership checks. ORM defaults and server defaults remain distinct.

## access_grants

| Field | PostgreSQL type | Nullable | Constraints / relationship |
| --- | --- | --- | --- |
| user_id | UUID | False | primary key; FK users.id / CASCADE |
| granted_at | TIMESTAMP WITH TIME ZONE | False | ORM default |
| expires_at | TIMESTAMP WITH TIME ZONE | False |  |

Indexes: []

Constraints: ["ForeignKeyConstraint: user_id", "PrimaryKeyConstraint: user_id"]

## agent_runs

| Field | PostgreSQL type | Nullable | Constraints / relationship |
| --- | --- | --- | --- |
| user_id | UUID | False | FK users.id / CASCADE |
| goal | VARCHAR | False |  |
| status | VARCHAR(20) | False | ORM default |
| steps | JSONB | False | ORM default |
| id | UUID | False | primary key; ORM default |
| created_at | TIMESTAMP WITH TIME ZONE | False | ORM default |

Indexes: [{"name": "ix_agent_runs_user_id", "columns": ["user_id"], "unique": false}]

Constraints: ["ForeignKeyConstraint: user_id", "PrimaryKeyConstraint: id", "status IN ('running', 'completed', 'failed', 'cancelled')"]

## auth_sessions

| Field | PostgreSQL type | Nullable | Constraints / relationship |
| --- | --- | --- | --- |
| user_id | UUID | False | FK users.id / CASCADE |
| token_hash | VARCHAR(64) | False | unique |
| csrf_hash | VARCHAR(64) | False |  |
| expires_at | TIMESTAMP WITH TIME ZONE | False |  |
| revoked_at | TIMESTAMP WITH TIME ZONE | True |  |
| id | UUID | False | primary key; ORM default |
| created_at | TIMESTAMP WITH TIME ZONE | False | ORM default |

Indexes: [{"name": "ix_auth_sessions_expires_at", "columns": ["expires_at"], "unique": false}, {"name": "ix_auth_sessions_user_id", "columns": ["user_id"], "unique": false}]

Constraints: ["ForeignKeyConstraint: user_id", "PrimaryKeyConstraint: id", "UniqueConstraint: token_hash"]

## bounded_uploads

| Field | PostgreSQL type | Nullable | Constraints / relationship |
| --- | --- | --- | --- |
| user_id | UUID | False | FK users.id / CASCADE |
| filename | VARCHAR(200) | False |  |
| media_type | VARCHAR(80) | False |  |
| size | INTEGER | False |  |
| checksum | VARCHAR(64) | False |  |
| received | INTEGER | False | ORM default |
| expires_at | TIMESTAMP WITH TIME ZONE | False |  |
| result | JSONB | True |  |
| id | UUID | False | primary key; ORM default |
| created_at | TIMESTAMP WITH TIME ZONE | False | ORM default |

Indexes: [{"name": "ix_bounded_uploads_expires_at", "columns": ["expires_at"], "unique": false}, {"name": "ix_bounded_uploads_user_id", "columns": ["user_id"], "unique": false}]

Constraints: ["ForeignKeyConstraint: user_id", "PrimaryKeyConstraint: id", "received BETWEEN 0 AND size", "size BETWEEN 1 AND 5242880"]

## conversations

| Field | PostgreSQL type | Nullable | Constraints / relationship |
| --- | --- | --- | --- |
| user_id | UUID | False | FK users.id / CASCADE |
| title | VARCHAR(200) | False | ORM default |
| selected_model_id | VARCHAR(80) | False | ORM default |
| updated_at | TIMESTAMP WITH TIME ZONE | False | ORM default |
| active_run_id | UUID | True |  |
| lease_until | TIMESTAMP WITH TIME ZONE | True |  |
| id | UUID | False | primary key; ORM default |
| created_at | TIMESTAMP WITH TIME ZONE | False | ORM default |

Indexes: [{"name": "conversation_owner_updated", "columns": ["user_id", "updated_at"], "unique": false}, {"name": "ix_conversations_user_id", "columns": ["user_id"], "unique": false}]

Constraints: ["ForeignKeyConstraint: user_id", "PrimaryKeyConstraint: id"]

## document_chunks

| Field | PostgreSQL type | Nullable | Constraints / relationship |
| --- | --- | --- | --- |
| document_id | UUID | False | FK documents.id / CASCADE |
| position | INTEGER | False |  |
| text | VARCHAR | False |  |
| embedding_version | VARCHAR(256) | False |  |
| embedding | VECTOR(256) | False |  |
| id | UUID | False | primary key; ORM default |
| created_at | TIMESTAMP WITH TIME ZONE | False | ORM default |

Indexes: [{"name": "ix_document_chunks_document_id", "columns": ["document_id"], "unique": false}]

Constraints: ["ForeignKeyConstraint: document_id", "PrimaryKeyConstraint: id", "UniqueConstraint: document_id, position", "position >= 0"]

## documents

| Field | PostgreSQL type | Nullable | Constraints / relationship |
| --- | --- | --- | --- |
| user_id | UUID | False | FK users.id / CASCADE |
| title | VARCHAR(200) | False |  |
| media_type | VARCHAR(80) | False |  |
| text | VARCHAR | False |  |
| checksum | VARCHAR(64) | False |  |
| embedding_version | VARCHAR(256) | False |  |
| id | UUID | False | primary key; ORM default |
| created_at | TIMESTAMP WITH TIME ZONE | False | ORM default |

Indexes: [{"name": "ix_documents_user_id", "columns": ["user_id"], "unique": false}]

Constraints: ["ForeignKeyConstraint: user_id", "PrimaryKeyConstraint: id", "UniqueConstraint: user_id, checksum"]

## identity_audit

| Field | PostgreSQL type | Nullable | Constraints / relationship |
| --- | --- | --- | --- |
| actor_id | UUID | True | FK users.id / SET NULL |
| event | VARCHAR(40) | False |  |
| record_id | UUID | True |  |
| id | UUID | False | primary key; ORM default |
| created_at | TIMESTAMP WITH TIME ZONE | False | ORM default |

Indexes: []

Constraints: ["ForeignKeyConstraint: actor_id", "PrimaryKeyConstraint: id"]

## identity_mail

| Field | PostgreSQL type | Nullable | Constraints / relationship |
| --- | --- | --- | --- |
| token_id | UUID | False | primary key; FK identity_tokens.id / CASCADE |
| state | VARCHAR(20) | False | ORM default |
| attempts | INTEGER | False | ORM default |
| next_attempt_at | TIMESTAMP WITH TIME ZONE | False | ORM default |
| lease_until | TIMESTAMP WITH TIME ZONE | True |  |
| lease_id | UUID | True |  |
| provider_id | VARCHAR(200) | True |  |

Indexes: []

Constraints: ["ForeignKeyConstraint: token_id", "PrimaryKeyConstraint: token_id", "attempts BETWEEN 0 AND 5", "state IN ('queued', 'leased', 'accepted', 'failed', 'cancelled')"]

## identity_tokens

| Field | PostgreSQL type | Nullable | Constraints / relationship |
| --- | --- | --- | --- |
| purpose | VARCHAR(20) | False |  |
| email | VARCHAR(254) | False |  |
| user_id | UUID | True | FK users.id / CASCADE |
| token_hash | VARCHAR(64) | False | unique |
| expires_at | TIMESTAMP WITH TIME ZONE | False |  |
| grant_expires_at | TIMESTAMP WITH TIME ZONE | True |  |
| consumed_at | TIMESTAMP WITH TIME ZONE | True |  |
| revoked_at | TIMESTAMP WITH TIME ZONE | True |  |
| id | UUID | False | primary key; ORM default |
| created_at | TIMESTAMP WITH TIME ZONE | False | ORM default |

Indexes: [{"name": "ix_identity_tokens_expires_at", "columns": ["expires_at"], "unique": false}]

Constraints: ["ForeignKeyConstraint: user_id", "PrimaryKeyConstraint: id", "UniqueConstraint: token_hash", "purpose IN ('invitation', 'recovery')"]

## industrial_investigations

| Field | PostgreSQL type | Nullable | Constraints / relationship |
| --- | --- | --- | --- |
| user_id | UUID | False | FK users.id / CASCADE |
| revision | INTEGER | False | ORM default |
| status | VARCHAR(20) | False | ORM default |
| updated_at | TIMESTAMP WITH TIME ZONE | False | ORM default |
| payload | JSONB | False |  |
| id | UUID | False | primary key; ORM default |
| created_at | TIMESTAMP WITH TIME ZONE | False | ORM default |

Indexes: [{"name": "ix_industrial_investigations_user_id", "columns": ["user_id"], "unique": false}]

Constraints: ["ForeignKeyConstraint: user_id", "PrimaryKeyConstraint: id", "revision > 0", "status IN ('ready', 'running', 'completed', 'failed', 'cancelled')"]

## inference_runs

| Field | PostgreSQL type | Nullable | Constraints / relationship |
| --- | --- | --- | --- |
| request_id | UUID | False |  |
| user_id | UUID | False | FK users.id / CASCADE |
| conversation_id | UUID | False | FK conversations.id / CASCADE |
| model_id | VARCHAR(80) | False | ORM default |
| status | VARCHAR(20) | False | ORM default |
| latency_ms | INTEGER | True |  |
| input_tokens | INTEGER | True |  |
| output_tokens | INTEGER | True |  |
| id | UUID | False | primary key; ORM default |
| created_at | TIMESTAMP WITH TIME ZONE | False | ORM default |

Indexes: [{"name": "ix_inference_runs_user_id", "columns": ["user_id"], "unique": false}]

Constraints: ["ForeignKeyConstraint: conversation_id", "ForeignKeyConstraint: user_id", "PrimaryKeyConstraint: id", "latency_ms >= 0 AND input_tokens >= 0 AND output_tokens >= 0", "status IN ('running', 'completed', 'failed', 'cancelled')"]

## messages

| Field | PostgreSQL type | Nullable | Constraints / relationship |
| --- | --- | --- | --- |
| conversation_id | UUID | False | FK conversations.id / CASCADE |
| role | VARCHAR(20) | False |  |
| content | JSONB | False |  |
| status | VARCHAR(20) | False | ORM default |
| sequence | INTEGER | False |  |
| model_id | VARCHAR(80) | True |  |
| id | UUID | False | primary key; ORM default |
| created_at | TIMESTAMP WITH TIME ZONE | False | ORM default |

Indexes: []

Constraints: ["ForeignKeyConstraint: conversation_id", "PrimaryKeyConstraint: id", "UniqueConstraint: conversation_id, sequence", "role IN ('user', 'assistant', 'system')", "sequence > 0", "status IN ('completed', 'failed', 'cancelled')"]

## model_leases

| Field | PostgreSQL type | Nullable | Constraints / relationship |
| --- | --- | --- | --- |
| user_id | UUID | False | FK users.id / CASCADE |
| expires_at | TIMESTAMP WITH TIME ZONE | False |  |
| id | UUID | False | primary key; ORM default |
| created_at | TIMESTAMP WITH TIME ZONE | False | ORM default |

Indexes: [{"name": "ix_model_leases_expires_at", "columns": ["expires_at"], "unique": false}, {"name": "ix_model_leases_user_id", "columns": ["user_id"], "unique": false}]

Constraints: ["ForeignKeyConstraint: user_id", "PrimaryKeyConstraint: id"]

## rate_buckets

| Field | PostgreSQL type | Nullable | Constraints / relationship |
| --- | --- | --- | --- |
| key | VARCHAR(64) | False | primary key |
| count | INTEGER | False | ORM default |
| expires_at | TIMESTAMP WITH TIME ZONE | False |  |

Indexes: [{"name": "ix_rate_buckets_expires_at", "columns": ["expires_at"], "unique": false}]

Constraints: ["PrimaryKeyConstraint: key"]

## trips

| Field | PostgreSQL type | Nullable | Constraints / relationship |
| --- | --- | --- | --- |
| user_id | UUID | False | FK users.id / CASCADE |
| destination | VARCHAR(200) | False |  |
| duration | INTEGER | False |  |
| budget | FLOAT | False |  |
| currency | VARCHAR(3) | False |  |
| preferences | VARCHAR | False |  |
| revision | INTEGER | False | ORM default |
| itinerary | JSONB | False |  |
| updated_at | TIMESTAMP WITH TIME ZONE | False | ORM default |
| id | UUID | False | primary key; ORM default |
| created_at | TIMESTAMP WITH TIME ZONE | False | ORM default |

Indexes: [{"name": "ix_trips_user_id", "columns": ["user_id"], "unique": false}]

Constraints: ["ForeignKeyConstraint: user_id", "PrimaryKeyConstraint: id", "budget > 0", "duration BETWEEN 1 AND 14", "revision > 0"]

## upload_chunks

| Field | PostgreSQL type | Nullable | Constraints / relationship |
| --- | --- | --- | --- |
| upload_id | UUID | False | primary key; FK bounded_uploads.id / CASCADE |
| sequence | INTEGER | False | primary key |
| data | BYTEA | False |  |

Indexes: []

Constraints: ["ForeignKeyConstraint: upload_id", "PrimaryKeyConstraint: upload_id, sequence", "octet_length(data) BETWEEN 1 AND 524288", "sequence BETWEEN 0 AND 9"]

## users

| Field | PostgreSQL type | Nullable | Constraints / relationship |
| --- | --- | --- | --- |
| email | VARCHAR(254) | False | unique |
| password_hash | VARCHAR(256) | False |  |
| display_name | VARCHAR(80) | False |  |
| status | VARCHAR(20) | False | ORM default |
| updated_at | TIMESTAMP WITH TIME ZONE | False | ORM default |
| id | UUID | False | primary key; ORM default |
| created_at | TIMESTAMP WITH TIME ZONE | False | ORM default |

Indexes: []

Constraints: ["PrimaryKeyConstraint: id", "UniqueConstraint: email", "status IN ('active', 'disabled')"]
