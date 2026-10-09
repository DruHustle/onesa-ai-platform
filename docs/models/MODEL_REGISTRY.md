# Model registry and future profile metadata

Serving uses one environment-configured active model behind public alias default. No new
large-model servers or endpoint names are introduced. training/registry.py stores immutable
local candidate records; it does not implement a database/promotion/deployment API.

Records retain version, base model/revision, dataset version, adapter path, training config,
evaluation report and artifact SHA-256 hashes. Additive metadata now includes logical family
(general/enterprise/industrial/travel/multilingual/regional), purpose, language tags, domain
labels, license/provenance and not_deployed deployment status. Unknown old metadata defaults
to absent coverage/license/provenance, not invented claims. Existing records remain readable;
new registration embeds evaluation results and evaluation/config hashes to retain evidence.
Language tags and domains have no country whitelist. Declared coverage requires verified review.

```sh
python -m training.registry metadata.json data/model-registry
```

Registration requires PEFT config/safetensors presence and evaluation samples; it does not
prove quality or authenticate a license. Validated filenames cannot be overwritten; symlinks
are rejected. No adapter was trained or registered as a real model in this workspace.
Proposed Onesa profiles are documented in MODEL_CUSTOMIZATION_STRATEGY.md.

Review licenses/provenance, baseline regression, artifacts, GPU loading and rollback before
manually selecting an evaluated artifact. Public model responses remain unchanged and omit
internal URLs/paths/credentials. A durable deployment registry can later store this metadata
without restricting language/domain labels; live status must come from actual deployment evidence.

Milestone 2 runtime inventory: onesa-ai-platform-backend/evaluation/model_inventory.json defines initial comparison
candidates with identifier/base/quantization/backend/upstream and application modalities/context.
Actual versioned reports observe installed artifact digest, native capabilities and context,
evaluation results and measured usage/timing/resident allocation. These reports are foundation
baselines, separate from trained-adapter candidate registration. No model is promoted automatically.
Only Qwen3 4B is downloaded/verified; Qwen3.5 candidates remain untested.
