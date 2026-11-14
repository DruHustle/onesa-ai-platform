# Model release and rollback

No automatic candidate promotion exists. Require a pinned base, approved/provenanced data,
reproducible config/environment, intact artifact hashes, held-out baseline comparison,
language/domain/safety/tool review, license review, real GPU loading/quality and operational
rollback before updating serving. Set acceptance thresholds/rubrics before evaluating.

Register a candidate with training.registry, attach a completed model card and reviewed
reports. Stage the adapter using compose.gpu.lora.yaml; configure an immutable base revision,
mounted artifact directory and adapter alias. Verify API discovery and real streamed output.
Public alias/API/UI remain stable. For rollback, select the previously validated base/adapter
configuration and compatible code/database snapshot; confirm health and a smoke request.

No Onesa adapter has been trained, loaded or promoted here. Production release thresholds,
approved datasets, GPU runtime lock and actual rollback timings remain operator work.

Record logical family/purpose, language/domain coverage, base/dataset versions and license/
provenance in the candidate registry. General, Enterprise, Industrial, Travel, Multilingual
and Regional are proposed profiles, not existing releases. Gate each independent adapter on
unchanged-base general-assistant regression plus specialization review; no need to deploy all
profiles or merge all datasets. Declared language labels are not measured proficiency.
