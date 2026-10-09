# Evaluation workflow

Prepare approved held-out cases separately from training. JSONL cases have id/language/
required_terms; predictions have id/response. Duplicate/missing/extra case IDs fail.

```sh
python -m training.evaluate cases.jsonl predictions.jsonl data/new-evaluation.json
```

Output path must be new. The report gives sample counts and mean required-term recall by
language, and marks human review required. This proxy does not measure truth, safety,
fluency, cultural accuracy or instruction-following comprehensively. Add reviewed rubrics
and representative general-assistant, European/international language, domain and tool cases
(including optional African/regional coverage where relevant) before any model release.

Compare unchanged base and candidate under the same prompt/serving setup; preserve case
version, outputs, methodology and hardware measurements. No real-model benchmark scores
have been produced in this session. Synthetic unit fixtures are not benchmark evidence.

Use `--baseline base-predictions.jsonl` to compare on exactly the same held-out cases. Reports
include the base report and per-language mean deltas; negative deltas expose proxy regression.
No automatic quality threshold or promotion is authorized. Preserve case/prompt/serving versions,
review reasoning, safety and core assistant regression as well as the targeted specialization.
