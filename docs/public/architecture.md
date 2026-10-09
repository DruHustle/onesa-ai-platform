# Public platform architecture

Applications communicate with one modular FastAPI service using authenticated HTTP and streamed responses. PostgreSQL stores user-owned conversations, documents, tool outcomes and trips. A shared model adapter abstracts inference. Knowledge retrieval supplies attributed untrusted context; permissions constrain tools independently of model output.

The model registry and dataset preparation are separate engineering workflows. Proposed fine-tuning does not imply deployed specialized models. [Explore the high-level views](/architecture). Detailed infrastructure, database engineering and operational materials belong to the access-controlled internal experience.
