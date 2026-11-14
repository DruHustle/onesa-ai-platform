# General-purpose and multi-domain dataset strategy

Phase B follows a qualified Phase A foundation and real-model baseline. Curate reviewed data
for general assistance, enterprise documents/workflows, industrial/engineering tasks, travel,
European languages and other international or optional regional specializations. English,
German, French and Spanish are relevant European targets; Shona and Ndebele remain additional
opportunities. No language-performance or training-ground-truth claim follows from these targets.

Language tags and optional free-form domain labels are extensible, not a country/language enum.
Use competent contributors and appropriate provenance/rights/consent/quality review per task.
Keep training and held-out evaluation isolated; preserve a general-assistant regression set
for each specialization. Independent datasets/adapters are preferable to indiscriminate merging.

pipeline.py normalizes NFC/whitespace/language tags, validates conversational roles, rejects
normalized duplicate examples/IDs, applies a limited email/phone PII screen and deterministic
nonempty splits. Manifests include sources/licenses/languages/domains and approval. Private
user conversations are never automatically collected or exported for training. Human review
and lawful-use assessment remain required; regex screening is not anonymization.

Committed English synthetic examples are software fixtures, labelled example-only and not
approved for training. No translated fixtures are linguistic evidence. Large-scale collection,
organizational datasets and real multilingual/domain benchmark curation remain future work.
