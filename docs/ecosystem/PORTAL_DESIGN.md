# Company Portal technical design

## Runtime components

Next.js serves the company site and authenticated business administration through host-aware boundaries. Fastify/Zod exports the actual API schema. The backend runtime executes compiled dist/src/server.js; the worker executes dist/src/jobs/worker.js. The image must contain migrations. Native Docker CMD avoids quoted shell-command failures.

## Business state and permissions

Content drafts/revisions are approved before publication. Enquiries and applications persist independently of notification delivery. Owner, administrator, editor, business, HR and viewer checks run at API boundaries. Sensitive account changes use transactional fresh password/MFA proof. Published corporate facts retain verification state; a draft template is not an approved official company record.

## Files, queues and durability

Private object storage is shared by API and worker. Bounded upload and download chunks enforce authorization, expiry, size and checksums. Antivirus uses a bounded INSTREAM protocol and accepts only the complete clean response. Email and deletion jobs have finite attempts and explicit terminal states after expired final leases. No HTTP wrapper should pretend to be a background executor.

## Deployment acceptance

Configure DATABASE_URL, SESSION_KEY, PUBLIC_ORIGIN, PROXY_SHARED_KEY, S3_BUCKET, S3_ENDPOINT, S3_REGION and scoped AWS credentials on the correct isolated services. Set company/portal frontend origins separately. Keep owner migration credentials out of runtime. DATABASE_ROLE errors require verified restricted privileges, not disabling readiness. Confirm operational records, backups and target identity before cutover. Configure worker email, scanner and storage, then test a synthetic persisted enquiry through actual delivery without losing accepted work on notification failure.

Full Portal contracts and SQL-derived schema appear in the internal explorers. Hosted production readiness must be independently rechecked.
