# Picomatch 2.x scoped security fork

Source: https://github.com/micromatch/picomatch/tree/2.3.2 (MIT)
CVE-2026-112366 / GHSA-fc5q-39xc-vjpf
Backport: reject repeated extglob branches containing unescaped glob stars, and multi-character repetition overlaps, before constructing attacker-controlled exponential regular expressions. Based on upstream unmerged proposal https://github.com/micromatch/picomatch/pull/235 (v4), backported against v2 parser. This is **not** an official 2.3.3 release.

This local fork replaces the Docs' 2.x matcher, separately from Chat's 4.x fork. Do not infer security from the fork's name or audit output alone: real Docusaurus, micromatch, fast-glob, classified-doc publication and adversarial ReDoS tests must pass before this candidate can be merged. Preserve upstream MIT license and source attribution. Replace with a reviewed upstream security release when available.
