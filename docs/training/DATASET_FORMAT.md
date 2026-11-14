# Dataset format

UTF-8 JSONL: one Example record per line, with id, language (bounded language-tag syntax, e.g. `en`, `de-DE`, `fr`, `es`, `sn`, `nd`, `mixed`),
messages (role/content), source, license, consent, reviewed and approved_for_training.
After optional first system turn, user/assistant must alternate and end in assistant.
Individual text is <=32k characters and a conversation <=96k. Empty/duplicate/unreviewed/
nonconsented/possible-PII examples are rejected. Preparation input limit is 20 MiB.

```sh
python -m training.pipeline prepare onesa-ai-platform-backend/training/examples/conversations.jsonl data/training-example
python -m training.train onesa-ai-platform-backend/training/examples/config.json
```

Preparation refuses existing output directories. At least three distinct examples are needed
for nonempty held-out splits. The default seed is 42; content hashes determine stable ordering.
Manifests record counts/checksums, dataset version, sources/licenses/languages/domains and aggregate
approval. Verification rejects tampering/leakage/approval inconsistency before execution.
The example dry-run passed; actual training remains disabled/unapproved.

Optional `domains` accepts up to 32 nonempty free-form labels (100 characters each), normalized
and deduplicated. Language tags are syntactically validated and lowercased, not checked against
a language registry or a verified model-coverage list. Legacy en/sn/nd/mixed records remain valid.
