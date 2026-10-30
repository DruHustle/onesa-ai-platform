"""Closed source/runtime identity for the owner-controlled Docs native tool."""

import re

import oracle_owner as owner

SOURCE_CLOSURE = frozenset(
    {
        "scripts/release/oracle_docs_contract.py",
        "scripts/release/oracle_docs_native_local.py",
        "scripts/release/oracle_docs_native_probe.mjs",
        "scripts/release/oracle_docs_build.py",
        "scripts/release/oracle_docs_checks.py",
        "scripts/release/oracle_owner.py",
        "scripts/docs/native-owner.mjs",
        "scripts/docs/acceptance.mjs",
        "scripts/docs/preview-access.mjs",
        "docs/documentation-policy.json",
        "onesa-ai-platform-frontend/apps/docs/package.json",
        "onesa-ai-platform-frontend/apps/docs/package-lock.json",
        "onesa-ai-platform-frontend/packages/onesa-design/onesa-applications.json",
        "onesa-ai-platform-frontend/apps/docs/static/brand/icons/v1/sources.json",
    }
)
RUNTIME_PINS = frozenset({"node", "openssl", "browser_packages"})
PRIVATE_SOURCE_CLOSURE = SOURCE_CLOSURE | frozenset(
    {
        "scripts/docs/internal-native.mjs",
        "scripts/docs/internal-acceptance.mjs",
        "scripts/release/oracle_docs_internal_build.py",
        "scripts/release/oracle_docs_internal_checks.py",
    }
)


def source_closure(component="docs-public"):
    owner.require(
        component in {"docs-public", "docs-internal"},
        "EXACT_NATIVE_DOCS_COMPONENT_REQUIRED",
    )
    return SOURCE_CLOSURE if component == "docs-public" else PRIVATE_SOURCE_CLOSURE


def producer_digest(files, runtime, *, component="docs-public"):
    owner.require(
        isinstance(files, dict)
        and files.keys() == source_closure(component)
        and isinstance(runtime, dict)
        and runtime.keys() == RUNTIME_PINS,
        "CLOSED_NATIVE_PRODUCER_AND_RUNTIME_REQUIRED",
    )
    owner.require(
        all(
            isinstance(pin, str) and re.fullmatch("[a-f0-9]{64}", pin)
            for pin in [*files.values(), *runtime.values()]
        ),
        "LITERAL_NATIVE_CODE_AND_RUNTIME_PINS_REQUIRED",
    )
    return owner.digest({"source": files, "runtime": runtime})
