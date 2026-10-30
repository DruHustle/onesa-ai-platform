"""Select only the independently commissioned Docs component implementation."""

import importlib

import oracle_owner as owner


def for_binding(binding):
    owner.require(
        binding.get("repository") == "DruHustle/onesa-ai-platform"
        and binding.get("component") in {"docs-public", "docs-internal"},
        "EXACT_INDEPENDENT_DOCS_DRIVER_SCOPE_REQUIRED",
    )
    return importlib.import_module(
        "oracle_docs_runner"
        if binding["component"] == "docs-public"
        else "oracle_docs_internal_runner"
    )


def for_component(store, component=None):
    if component is None:
        components = set(store.policy["components"])
        owner.require(
            len(components) == 1,
            "ONE_INDEPENDENT_DOCS_COMPONENT_PER_INSTALLATION_REQUIRED",
        )
        repository, component = next(iter(components)).split(":")
    else:
        repository = "DruHustle/onesa-ai-platform"
    binding = {"repository": repository, "component": component}
    owner.require(
        repository + ":" + component in store.policy["components"],
        "COMMISSIONED_DOCS_COMPONENT_REQUIRED",
    )
    return for_binding(binding)
