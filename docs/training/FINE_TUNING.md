# Fine-tuning

`python -m training.train CONFIG` validates config/dataset and prints a dry-run; it imports
no heavy training packages and starts no job. LoRA/QLoRA rank/alpha/learning rate/context/
steps/seed/output are configurable. Existing outputs are protected; resume requires a
checkpoint within the original experiment and matching config/dataset metadata.

Actual `--execute` requires ONESA_ALLOW_TRAINING=1, approved reviewed/consented data,
local pre-downloaded weights, CUDA and a positive measured ONESA_TRAINING_MEMORY_BUDGET_GIB
within available free GPU memory. It never downloads a base model. Run training in a separate
GPU environment: requirements.candidate.txt pins upstream package candidates, **not a tested
CUDA dependency lock**. Resolve compatible GPU wheels/versions and lock after hardware checks.

The execution path uses Transformers/Datasets/PEFT/TRL, all-linear LoRA, optional NF4 QLoRA,
local tokenizer/chat-template processing, bounded steps/checkpoints and adapter export.
It records config, dataset version, evaluation loss, library versions and GPU resource metadata.
BF16 is used only if supported, otherwise FP16. Actual execution/resume/export are unverified
because there is no approved dataset/GPU/weights in this environment. No training was started.

Follow the [official SFTTrainer docs](https://huggingface.co/docs/trl/v1.15.0/sft_trainer),
[PEFT LoRA docs](https://huggingface.co/docs/peft/main/package_reference/lora) and
[Transformers quantization docs](https://huggingface.co/docs/transformers/quantization/bitsandbytes)
when qualifying the chosen runtime. This is supervised adaptation, not foundation-model training.

Phase B adapts a broad general-purpose base for independently versioned enterprise, industrial,
travel, multilingual or optional regional releases. Dataset language/domain metadata is extensible.
Choose a coherent purpose, preserve general-assistant regression benchmarks and evaluate against
the original base; do not combine every specialization into one checkpoint by default.
See models/MODEL_CUSTOMIZATION_STRATEGY.md for the proposed, currently untrained profiles.
