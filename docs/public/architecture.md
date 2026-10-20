# Public platform architecture

Applications communicate with one modular FastAPI service using authenticated HTTP and streamed responses. PostgreSQL stores user-owned conversations, documents, tool outcomes and trips. A shared model adapter abstracts inference. Knowledge retrieval supplies attributed untrusted context; permissions constrain tools independently of model output.

The model registry and dataset preparation are separate engineering workflows. Proposed fine-tuning does not imply deployed specialized models. [Explore the high-level views](/architecture). Detailed infrastructure, database engineering and operational materials belong to the access-controlled internal experience.

## Current provider paths

Vercel serves product frontends and public Docs. Oracle Cloud Infrastructure hosts
separate staging and production APIs and Portal background workers; Cloudflare provides
HTTPS ingress and security controls. The protected engineering site remains separate.
Databases, private Portal storage, mail and AI inference have their own service boundaries;
moving the API host did not move all data or model serving onto that VM.

The current AI configuration uses Cloudflare Workers AI for generation and semantic
embeddings. Real inference and retrieval have source-bound release evidence; that is
not proof of unrestricted availability, complete model-language quality or industrial
connectivity. Robot currently provides protected one-joint software simulation, with
no connected physical controller. Shared hosting has one failure domain and is not
high availability. Detailed configuration and incident/recovery records remain in
protected engineering documentation.
