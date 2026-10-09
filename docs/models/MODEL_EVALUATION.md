# Reproducible real-model baseline evaluation

The independent onesa-ai-platform-backend/evaluation/cases.jsonl contains 13 author-curated synthetic software acceptance
cases: general conversation, reasoning/format adherence, English/German instructions, German/French
facts, multi-turn memory, source grounding/citation, absent facts, structured JSON, tool proposals,
privacy and prompt injection. These are disjoint from training/examples; they are not comprehensive
linguistic, safety or factual benchmarks. Further regional-language cases need reviewed data.

```sh
.venv/bin/python -m evaluation.local evaluate data/new-baseline.json \
  --base-url http://127.0.0.1:11434/v1 --max-tokens 192
```

The runner records case-file SHA-256, unchanged model digest/settings, actual outputs/latency/usage,
mechanical per-case checks, sample count and a separate native function-call probe. No function
proposals execute through the probe. Human quality review remains required. Never claim broad
language/safety/tool capability from one successful prompt. Output reports are immutable paths.

On 2026-10-09 the actual Qwen3 4B Q4_K_M baseline passed 12/13 mechanical cases and the native
add-function proposal probe. The reasoning case calculated the correct answer but added explanation
instead of returning only 10, failing exact-format instruction adherence. This failure is retained;
no prompt was rewritten or score hidden. German exact instruction and simple German/French fact
cases passed; these establish only those prompts, not multilingual proficiency.

Future adapters must use the same approved/versioned held-out cases and prompt/serving setup,
retain base and candidate outputs and preserve general-assistant regression. training/evaluate.py
--baseline supports paired proxy comparisons; its substring recall is not a full quality judge.
Define reviewed reasoning/factual/safety/tool and language/domain rubrics before release. Real
NVIDIA, other candidate models and specialist-language evaluation remain unverified.
