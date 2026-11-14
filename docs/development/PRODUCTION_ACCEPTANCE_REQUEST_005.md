# ONESA AI PLATFORM — PRODUCTION ACCEPTANCE CONTINUATION 005
## Staging, Security, Observability, Recovery and Real Inference Acceptance

**Workspace:** `onesa ug/onesa-ai-platform/`

**Frontend:** `onesa-ai-platform-frontend/`

**Backend:** `onesa-ai-platform-backend/`

**Objective:** Resolve production release blockers without rewriting working functionality.

## 1. Current Status

The existing application reportedly includes:

- Onesa Chat
- Knowledge/RAG
- Agent tools
- Travel planning
- Authentication
- Persistent conversations
- Model inference adapters
- Model evaluation infrastructure
- Development and deployment documentation

Production release remains blocked by:

1. Target-host TLS and staging verification.
2. Security qualification.
3. Load/performance qualification.
4. Production monitoring.
5. Operational backups and recovery.
6. Legal/privacy decisions.
7. NVIDIA/vLLM inference acceptance.

Treat these items as unverified until actual tests produce evidence.

Do not declare the application production-ready based solely on existing unit or browser tests.

## 2. Read Existing Project State

Start by reviewing:

- Current repository architecture
- Frontend and backend configuration
- Inference adapters
- Authentication design
- Docker and deployment files
- Security documentation
- Test suites
- Database backup procedures
- Current production checklist
- Implementation status
- Session handoff

Run existing tests and record the baseline.

Preserve all working functionality and data.

Do not create a new application.

Do not modify the Company Portal or Robotics repositories.

## 3. Establish a Real Staging Environment

Prepare a production-like staging configuration.

Requirements:

- Independently deployable frontend and backend
- PostgreSQL with isolated staging data
- Private document storage
- Reverse proxy
- Configurable TLS
- Authentication/session configuration
- Private inference networking
- Health and readiness checks
- Application logs
- Proper secret management

If no remote staging host is available, create a reproducible local production-like staging environment with self-signed or locally trusted development certificates.

Clearly distinguish this from a verified public TLS deployment.

Provide an environment inventory and deployment diagram.

Document:

- Server requirements
- Operating system requirements
- DNS requirements
- TLS setup
- Ports
- Network boundaries
- Resource requirements
- Persistent volumes
- Backup locations
- Service startup order

Do not expose PostgreSQL, Ollama or vLLM publicly.

## 4. Security Qualification

Conduct a structured security review using relevant OWASP ASVS controls.

Prioritize:

- Authentication
- Session management
- Authorization
- User data isolation
- RAG document permissions
- Agent tool permissions
- Secure file uploads
- API validation
- Rate limiting
- Secure cookies
- CSRF protection
- CORS restrictions
- Security headers
- Secrets management
- Dependency vulnerabilities
- Prompt injection and tool misuse
- Logging of sensitive information

Add automated negative tests.

Verify one user cannot access another user's conversations, documents, travel plans or agent executions.

Verify model outputs cannot grant unauthorized tool permissions.

Document findings and remediation.

Do not claim a penetration test or external certification occurred unless performed.

## 5. Production Monitoring

Implement useful, privacy-conscious observability.

Include:

- Service availability
- HTTP request volume
- API latency
- HTTP error rates
- Database connectivity
- Authentication failures
- Background job failures
- Chat streaming errors
- Inference availability
- Inference latency
- Model readiness
- Storage capacity
- Backup status

Use structured logging and request correlation IDs.

Avoid logging full user conversations or private documents unnecessarily.

Document alert thresholds and runbooks.

If no external alert destination is configured, provide working local monitoring and clear instructions to connect alerts.

Do not claim alerts are operational without an actual delivery test.

## 6. Load and Performance Qualification

Build reproducible load tests for:

- Concurrent user sessions
- Chat API requests
- SSE streaming
- Conversation persistence
- Knowledge search
- Agent execution
- Travel planning
- Database connection handling

Separate API capacity testing with mock inference from actual model-serving capacity.

Record:

- Environment
- Model/backend configuration
- Number of concurrent users
- Request volume
- p50 latency
- p95 latency
- Error rate
- Time to first token
- Generated tokens per second
- Resource consumption
- Identified bottlenecks

Set performance targets based on product requirements.

Do not invent throughput results.

Do not use production customer data during load tests.

## 7. Backup and Recovery

Complete:

- Automated PostgreSQL backups
- Document storage backup strategy
- Encrypted backup storage where appropriate
- Backup retention
- Restoration scripts
- Database migration recovery
- Deployment rollback
- Backup failure detection

Perform a restoration test in an isolated environment.

Verify:

- User records
- Conversations
- Knowledge data
- Agent records
- Travel plans
- Required file references

Document data integrity results.

Record realistic recovery time and data loss measurements.

Do not claim recovery objectives have been achieved unless tested.

## 8. Real Model Inference Acceptance

Maintain separate acceptance paths.

### Apple Silicon / Ollama

If Ollama is available locally:

- Verify the configured Qwen model loads.
- Verify actual chat generation.
- Verify streaming.
- Verify cancellation.
- Verify conversation context.
- Measure inference latency.
- Measure memory usage where supported.
- Test backend disconnection and recovery.

Clearly identify which model is used and whether results came from real inference.

### NVIDIA / vLLM

Prepare GPU-host acceptance tests covering:

- NVIDIA driver detection
- GPU memory availability
- Container GPU access
- Model loading
- Context configuration
- Real chat generation
- SSE streaming
- Cancellation
- Error recovery
- Concurrent requests
- GPU memory utilization
- Performance
- Model quality baseline

If no compatible NVIDIA host is available, keep this acceptance gate pending.

Do not block all non-GPU software development solely because NVIDIA hardware is unavailable.

Do not label NVIDIA inference verified based on mock or Mac-only testing.

## 9. Operational Security

Implement:

- Environment-specific secrets
- Secret rotation documentation
- Restricted service networking
- Database least-privilege access
- Protected inference endpoints
- Secure backup credentials
- Controlled administrative access
- Safe deployment logging
- Documented incident response

Ensure development secrets and credentials are never embedded in production images.

Scan tracked files and generated build artifacts for accidental secrets.

## 10. Legal and Privacy Readiness

Prepare a factual review checklist for:

- Privacy notices
- Data controller identity
- User conversation storage
- Knowledge document processing
- Third-party processors
- Data retention
- Data deletion
- User access requests
- Model inference data flows
- Training-data consent
- GDPR obligations
- Applicable AI Act considerations
- Website legal notices

Do not claim regulatory compliance solely from application code.

List decisions requiring company management or qualified legal review.

Keep publication blocked where mandatory requirements are unresolved.

## 11. CI/CD and Release Engineering

Ensure the frontend and backend have independent production builds.

Implement or verify:

- Linting
- Type checking
- Unit testing
- Integration testing
- Browser testing
- API contract testing
- Container builds
- Migration testing
- Secret scanning
- Dependency scanning
- Staging deployment
- Release versioning
- Rollback procedure

Use controlled production promotion.

Do not deploy publicly without authorization.

## 12. Production Readiness Report

Create:

`docs/development/PRODUCTION_ACCEPTANCE_REPORT.md`

Include a release matrix with:

- Requirement
- Verification method
- Evidence
- Result
- Environment
- Blocker
- Required corrective action

Use these statuses:

- PASS
- FAIL
- BLOCKED
- NOT TESTED

Do not mark configuration files alone as proof of successful deployment.

Separate:

1. Software readiness
2. Staging readiness
3. Infrastructure readiness
4. AI inference readiness
5. Operational readiness
6. Legal/privacy approval
7. Public launch authorization

## 13. Acceptance Criteria

This stage is complete when:

1. The frontend and backend production images build.
2. A reproducible staging deployment works.
3. Authentication and authorization tests pass.
4. Security findings are documented and release blockers fixed.
5. Load tests run and report measured results.
6. Monitoring captures actual application activity.
7. Backup restoration succeeds.
8. Deployment rollback is demonstrated.
9. Ollama inference is verified where available.
10. NVIDIA acceptance remains accurately recorded until real hardware testing.
11. Privacy and legal decisions are documented.
12. A truthful production release report is generated.

## 14. Execute Now

Begin with the existing production blockers.

Prioritize:

1. Staging infrastructure.
2. Security remediation.
3. Operational monitoring.
4. Backup and restoration.
5. Performance/load qualification.
6. Real inference acceptance.
7. Legal/privacy checklist.
8. Production release assessment.

Implement the testable software and infrastructure first.

Record missing server, DNS, credential, GPU and legal prerequisites explicitly.

Do not change the product architecture unnecessarily.

Do not add major new AI features during this production qualification stage.

Run available tests, fix failures, document actual results and update the session handoff.

**Continue Onesa AI Platform production acceptance now.**