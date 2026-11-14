# General-purpose model customization

Phase A retains a broad, replaceable open-weight base: initially Qwen/Qwen3-4B-Instruct-2507.
First qualify general assistant/code/reasoning behavior on actual infrastructure. Geographic
specialization must not displace general-purpose quality during initial deployment.

Phase B is reusable multi-domain adaptation: general assistants, enterprise knowledge/workflows,
engineering/manufacturing, travel, European and international languages, multilingual reasoning,
regional knowledge and optional African-language contexts. Select reviewed datasets for a clear
purpose; do not merge every specialization into one checkpoint by default.

| Proposed profile | Intended purpose |
| --- | --- |
| Onesa General | General conversation and reasoning |
| Onesa Enterprise | Organizational knowledge, documents and workflows |
| Onesa Industrial | Engineering/manufacturing and industrial knowledge |
| Onesa Travel | Itineraries, destination and tourism tasks |
| Onesa Multilingual | Communication/translation/language adaptation |
| Onesa Regional | Optional regional/cultural knowledge, including African contexts |

These are logical candidate-metadata families, not trained models or six deployed servers.
Independently version adapters/releases where justified by evaluations; select one reviewed
active artifact through existing serving configuration. No per-country routing is introduced.

Keep approved provenance/licenses/consent, dataset manifests, immutable base revision, config,
adapter hashes and candidate evaluation. Compare each candidate with the unchanged base on
identical held-out cases, including general-assistant regression and target-domain/language
coverage. Limited term recall is an aid; human factual/safety/fluency/tool review is required.
No promotion or claimed language support follows from metadata or UI translations alone.
