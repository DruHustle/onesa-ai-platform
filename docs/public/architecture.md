# Public platform architecture

Applications communicate with one modular FastAPI service using authenticated HTTP and streamed responses. PostgreSQL stores user-owned conversations, documents, tool outcomes and trips. A shared model adapter abstracts inference. Knowledge retrieval supplies attributed untrusted context; permissions constrain tools independently of model output.

The model registry and dataset preparation are separate engineering workflows. Proposed fine-tuning does not imply deployed specialized models. [Explore the high-level views](/architecture). Detailed infrastructure, database engineering and operational materials belong to the access-controlled internal experience.

## Current provider paths

Vercel serves product frontends and the public docs. Render serves product APIs. Portal's Oracle background executor and ClamAV have passed synthetic staging checks; production replacement qualification is separate. AI's Workers AI generation and semantic embedding paths have passed real staging tests; production acceptance and corrected staging storage qualification remain separate. Robot is cloud software simulation with physical actuation disabled. Detailed environment, schema, recovery and onboarding references belong in the separate engineering build.
