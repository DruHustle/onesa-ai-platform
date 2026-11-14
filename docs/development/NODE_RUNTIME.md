# Node runtime

New container candidates use Node 24.22.1 from the official Node 24 LTS security release. The Docker multi-architecture digest is pinned in each independent component. Earlier 9 October Node 24.21.0 and Node 20.20.1 host observations are historical and do not qualify a new release. Use the reviewed security runtime for current checks.

## Current security qualification

New runtime candidates pin official Node 24.22.1 and its verified multi-architecture Docker digest. This is the supported Node 24 security patch for the [21 October maintainer advisory](https://nodejs.org/en/blog/vulnerability/october-2026-security-releases). Earlier 24.21.0/Node 20 observations above are historical and do not qualify a new release. Install the checksum-verified native prerequisite with `.venv/bin/python scripts/local/install_node24.py`; it uses ignored `data/runtime/node24-24.22.1`, preserving any previous runtime directory. Make prefers that versioned path. Provider-managed Node patch levels still require actual provider/release evidence.
