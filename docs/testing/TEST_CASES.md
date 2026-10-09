# Test cases

| Area | Evidence |
| --- | --- |
| Foundation/serving | Probe behavior, timeout/error redaction, config, unicode/cancellation, HTTP/SSE vLLM contracts |
| Auth/content | Real PostgreSQL sessions, expiry/rotation/revocation, CSRF/Origin/throttle, ownership/CRUD/pagination |
| Streaming | Completed persistence, failed partial cleanup, concurrent lease rejection, expiry recovery, actual socket disconnect |
| Knowledge | TXT validation/duplicate/index/retrieval/reindex/cascade, other-user isolation, persisted sources |
| Agents/travel | Registered tool permissions/finite input/deadline/cancellation, owned history, structured trips/revisions and invalid model proposals |
| Training | Nonempty deterministic splits, duplicate/PII/review rejection, tamper detection, execution approval gate, artifact hashes/immutability |
| Release | Production config guards, protected metrics, total-body bounds, migration round-trip |
| Browser | Registration → stream → reopen → rename/delete → login; document chat/tools/travel revisions; mobile keyboard/nav |

See IMPLEMENTATION_STATUS.md for the final passing counts/limitations. Backup/restore and
small health-load probes are actual local operations recorded separately. No real-model
quality, trained language scores, GPU throughput or production certification is asserted.

Amendment 001 regression coverage: European/international plus legacy language records,
free-form domain labels, general-assistant regression against paired base predictions,
proposed families remaining not_deployed, and persisted interface-language preference.
Synthetic scores in unit fixtures are not performance evidence.
