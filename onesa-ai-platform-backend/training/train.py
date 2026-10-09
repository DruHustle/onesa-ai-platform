"""Dry-run by default. Actual training requires approved data and a CUDA environment."""

import argparse
import json
import os
import sys
from importlib.metadata import version
from pathlib import Path

from training.pipeline import check_config, verify_dataset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--resume", type=Path)
    args = parser.parse_args()
    config = check_config(args.config, allow_existing_output=args.resume is not None)
    manifest = verify_dataset(Path(config.dataset_dir))
    if not args.execute:
        print(
            json.dumps(
                {
                    "status": "configuration_validated",
                    "training_started": False,
                    "config": config.model_dump(),
                    "dataset": manifest,
                },
                indent=2,
            )
        )
        return
    if os.environ.get("ONESA_ALLOW_TRAINING") != "1" or not manifest["approved_for_training"]:
        raise SystemExit("Execution requires ONESA_ALLOW_TRAINING=1 and a human-approved dataset")
    if args.resume and (
        not args.resume.is_dir()
        or not args.resume.resolve().is_relative_to(Path(config.output_dir).resolve())
    ):
        raise SystemExit("Resume checkpoint must exist inside this experiment directory")
    # Heavy dependencies are deliberately imported only after execution gates.
    import torch
    from datasets import load_dataset
    from peft import LoraConfig, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import SFTConfig, SFTTrainer

    if not torch.cuda.is_available():
        raise SystemExit("A configured CUDA GPU is required")
    if not Path(config.model_name).exists():
        raise SystemExit(
            "Use pre-downloaded local weights; this command never downloads the base model"
        )
    memory_budget = float(os.environ.get("ONESA_TRAINING_MEMORY_BUDGET_GIB", "0"))
    free_memory, total_memory = torch.cuda.mem_get_info()
    if memory_budget <= 0 or free_memory < memory_budget * 1024**3:
        raise SystemExit("Configure a positive measured memory budget within available GPU memory")
    snapshot = {
        "config": config.model_dump(),
        "dataset_version": manifest["dataset_version"],
    }
    output = Path(config.output_dir)
    if args.resume:
        if json.loads((output / "run-config.json").read_text()) != snapshot:
            raise SystemExit("Resume configuration/dataset differs from the original experiment")
    else:
        output.mkdir(parents=True, exist_ok=False)
        (output / "run-config.json").write_text(json.dumps(snapshot, indent=2) + "\n")
    tokenizer = AutoTokenizer.from_pretrained(
        config.model_name, local_files_only=True, trust_remote_code=False
    )
    kwargs = {
        "local_files_only": True,
        "trust_remote_code": False,
        "dtype": torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
    }
    if config.method == "qlora":
        kwargs["device_map"] = {"": torch.cuda.current_device()}
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=kwargs["dtype"],
        )
    model = AutoModelForCausalLM.from_pretrained(config.model_name, **kwargs)
    if config.method == "qlora":
        model = prepare_model_for_kbit_training(model)
    files = {
        split: str(Path(config.dataset_dir) / f"{split}.jsonl") for split in ("train", "validation")
    }
    dataset = load_dataset("json", data_files=files)
    dataset = dataset.remove_columns(
        [name for name in dataset["train"].column_names if name != "messages"]
    )
    training_args = SFTConfig(
        output_dir=config.output_dir,
        max_steps=config.max_steps,
        learning_rate=config.learning_rate,
        max_length=config.max_length,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        seed=config.seed,
        bf16=torch.cuda.is_bf16_supported(),
        fp16=not torch.cuda.is_bf16_supported(),
        report_to="none",
        save_steps=25,
        save_total_limit=2,
        eval_strategy="steps",
        eval_steps=25,
    )
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        processing_class=tokenizer,
        peft_config=LoraConfig(
            r=config.rank,
            lora_alpha=config.alpha,
            target_modules="all-linear",
            task_type="CAUSAL_LM",
        ),
    )
    trainer.train(resume_from_checkpoint=str(args.resume) if args.resume else None)
    trainer.save_model(str(Path(config.output_dir) / "adapter"))
    tokenizer.save_pretrained(str(Path(config.output_dir) / "adapter"))
    result = {
        "config": config.model_dump(),
        "dataset_version": manifest["dataset_version"],
        "evaluation": trainer.evaluate(),
        "deployment_status": "candidate",
        "python": sys.version,
        "libraries": {
            name: version(name) for name in ["torch", "transformers", "datasets", "peft", "trl"]
        },
        "gpu": torch.cuda.get_device_name(),
        "gpu_total_bytes": total_memory,
        "gpu_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
    }
    (Path(config.output_dir) / "experiment.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
