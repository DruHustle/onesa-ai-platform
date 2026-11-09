"""Literal AI release scopes; this module never issues or transfers authority.

The existing two- and six-profile policies remain supported. An explicitly
commissioned eight-profile policy adds shared identity without changing any
existing profile's authority. Each profile has one context per source. Paths and
modes cannot be supplied by callers.
"""

import re
from pathlib import Path

REPOSITORY = "DruHustle/onesa-ai-platform"
CANONICAL_REPOSITORY = "DruHustle/onesa-ug"
SOURCE_FIELDS = frozenset(
    {
        "schema_version",
        "repository",
        "repository_id",
        "product",
        "source_path",
        "candidate_commit",
        "source_tree",
        "product_source_tree",
        "branch",
    }
)
PROFILES = {
    "api": ("api", "foundation"),
    "frontend": ("frontend", "foundation"),
    "twins-api": ("api", "twins"),
    "twins-frontend": ("frontend", "twins"),
    "cybersecurity-api": ("api", "cybersecurity"),
    "cybersecurity-frontend": ("frontend", "cybersecurity"),
    "identity-api": ("api", "identity"),
    "identity-frontend": ("frontend", "identity"),
}
LEGACY = frozenset({"api", "frontend"})
IDENTITY = frozenset({"identity-api", "identity-frontend"})
SCOPED = frozenset(PROFILES) - IDENTITY
EXPANDED = frozenset(PROFILES)
MODES = frozenset({"foundation", "twins", "cybersecurity", "identity"})


class ProfileError(ValueError):
    pass


def require(value, code):
    if not value:
        raise ProfileError(code)


def source_binding(binding):
    """Validate source identity only; never qualify or commission a component."""
    require(
        isinstance(binding, dict) and SOURCE_FIELDS <= set(binding),
        "COMPLETE_CANONICAL_AI_SOURCE_REQUIRED",
    )
    source = {key: binding[key] for key in SOURCE_FIELDS}
    require(
        type(source["schema_version"]) is int
        and source["schema_version"] == 2
        and source["repository"] == CANONICAL_REPOSITORY
        and type(source["repository_id"]) is int
        and source["repository_id"] == 1444746154
        and source["product"] == "platform"
        and source["source_path"] == "onesa-ai-platform"
        and source["branch"] == "main"
        and all(
            isinstance(source[key], str) and re.fullmatch(r"[a-f0-9]{40}", source[key])
            for key in ("candidate_commit", "source_tree", "product_source_tree")
        ),
        "CANONICAL_AI_APPLICATION_SOURCE_SCOPE",
    )
    return source


def is_canonical(binding):
    return (
        isinstance(binding, dict) and binding.get("repository") == CANONICAL_REPOSITORY
    )


def scope(binding):
    name = component(binding)
    return (
        CANONICAL_REPOSITORY + ":platform:"
        if is_canonical(binding)
        else REPOSITORY + ":"
    ) + name


def source_identity(binding):
    fields = {"repository", "candidate_commit", "source_tree", "source_sha256"}
    if is_canonical(binding):
        source_binding(binding)
        fields |= SOURCE_FIELDS
    return {key: binding[key] for key in fields}


def frontend_root(binding=None):
    if is_canonical(binding):
        source_binding(binding)
        return "onesa-ai-platform/onesa-ai-platform-frontend/apps/chat"
    return "onesa-ai-platform-frontend/apps/chat"


def source_metadata(binding):
    if not is_canonical(binding):
        return {}
    source = source_binding(binding)
    return {
        "onesaSource" + suffix: str(source[key])
        for suffix, key in [
            ("Schema", "schema_version"),
            ("Repository", "repository"),
            ("RepositoryId", "repository_id"),
            ("Product", "product"),
            ("Path", "source_path"),
            ("RootTree", "source_tree"),
            ("ProductTree", "product_source_tree"),
            ("Branch", "branch"),
        ]
    }


def same_product(left, right):
    """Only source compatibility; signed dependency validation is separate."""
    component(left)
    component(right)
    return left.get("repository") == right.get("repository") or (
        is_canonical(left) and right.get("repository") == REPOSITORY
    )


def component(binding):
    value = binding.get("component") if isinstance(binding, dict) else None
    require(isinstance(value, str) and value in PROFILES, "UNKNOWN_AI_RELEASE_PROFILE")
    if is_canonical(binding):
        source_binding(binding)
    else:
        require(
            "repository" not in binding or binding["repository"] == REPOSITORY,
            "FOREIGN_AI_RELEASE_REPOSITORY",
        )
    return value


def kind(binding):
    return PROFILES[component(binding)][0]


def companion(binding, target):
    value = component(binding)
    require(target in {"api", "frontend"}, "UNKNOWN_AI_COMPONENT_KIND")
    if value in LEGACY:
        return target
    return PROFILES[value][1] + "-" + target


def policy_components(policy):
    require(isinstance(policy, dict), "AI_POLICY_REQUIRED")
    profiles = policy.get("components")
    require(isinstance(profiles, dict), "AI_POLICY_COMPONENTS_REQUIRED")
    canonical = policy.get("schema_version") == 2
    if canonical:
        source_binding(policy.get("toolchain", {}).get("source_binding"))
    prefix = CANONICAL_REPOSITORY + ":platform:" if canonical else REPOSITORY + ":"
    selected = next(
        (
            names
            for names in (LEGACY, SCOPED, EXPANDED)
            if set(profiles) == {prefix + c for c in names}
        ),
        None,
    )
    require(selected is not None, "AI_POLICY_PROFILE_SET_REFUSED")
    for name in selected:
        profile = profiles[prefix + name]
        require(
            isinstance(profile, dict)
            and type(profile.get("qualification_attempt_limit")) is int
            and profile["qualification_attempt_limit"] == 1,
            "ONE_CONTEXT_PER_PROFILE_SOURCE_REQUIRED",
        )
        if selected != LEGACY:
            require(
                profile.get("release_mode") == PROFILES[name][1],
                "FIXED_AI_PROFILE_MODE_REQUIRED",
            )
        else:
            require("release_mode" not in profile, "LEGACY_POLICY_MODE_SCHEMA_REFUSED")
    return selected


def validate_mode(binding, mode, policy):
    value = component(binding)
    selected = policy_components(policy)
    require(
        is_canonical(binding) == (policy.get("schema_version") == 2),
        "AI_PROFILE_SOURCE_POLICY_MISMATCH",
    )
    require(value in selected, "AI_PROFILE_NOT_COMMISSIONED")
    bound_mode(binding, mode)
    if selected != LEGACY:
        require(mode == PROFILES[value][1], "AI_PROFILE_MODE_MISMATCH")
    return mode


def bound_mode(binding, mode):
    value = component(binding)
    require(mode in MODES, "UNKNOWN_AI_RELEASE_MODE")
    require(mode != "identity" or value in IDENTITY, "IDENTITY_PROFILE_REQUIRED")
    if value not in LEGACY:
        require(mode == PROFILES[value][1], "AI_PROFILE_MODE_MISMATCH")
    return mode


def enabled_features(values, mode):
    """Use actual private runtime flags, never a caller-selected test subset."""
    require(mode in MODES, "UNKNOWN_AI_RELEASE_MODE")
    require(isinstance(values, dict), "AI_RUNTIME_FLAGS_REQUIRED")
    flags = {
        "twins": values.get("ONESA_DIGITAL_TWINS_ENABLED", "false"),
        "cybersecurity": values.get("ONESA_CYBERSECURITY_ENABLED", "false"),
    }
    require(
        all(
            type(value) is str and value in {"true", "false"}
            for value in flags.values()
        ),
        "EXPLICIT_AI_RUNTIME_FEATURE_FLAGS_REQUIRED",
    )
    enabled = frozenset(name for name, value in flags.items() if value == "true")
    require(
        mode == "identity"
        or (not enabled if mode == "foundation" else mode in enabled),
        "AI_RUNTIME_FEATURE_MODE_MISMATCH",
    )
    return enabled


def workflow_mode(mode, enabled):
    """Preserve native acceptance when shared identity is the changed capability."""
    require(mode in MODES, "UNKNOWN_AI_RELEASE_MODE")
    require(isinstance(enabled, (set, frozenset)), "ACTUAL_AI_FEATURE_SET_REQUIRED")
    require(enabled <= {"twins", "cybersecurity"}, "UNKNOWN_AI_RUNTIME_FEATURE")
    require(
        mode == "identity"
        or (not enabled if mode == "foundation" else mode in enabled),
        "AI_RUNTIME_FEATURE_MODE_MISMATCH",
    )
    if mode != "identity":
        return mode
    return (
        "twins" if "twins" in enabled else "cybersecurity" if enabled else "foundation"
    )


def plan_path(binding, api_plan, frontend_plan):
    value = component(binding)
    base = Path(api_plan if kind(binding) == "api" else frontend_plan)
    if is_canonical(binding):
        return base.with_name("oracle-ai-canonical-" + value + "-release.json")
    if value in LEGACY:
        return base
    return base.with_name("oracle-ai-" + value + "-release.json")


def artifact_folder(binding, root):
    value = component(binding)
    source = source_commit(binding)
    base = Path(root) / "canonical-platform" if is_canonical(binding) else Path(root)
    folder = base / "artifacts" / source
    return folder if value in LEGACY else folder / "profiles" / value


def configuration_folder(binding, root):
    value = component(binding)
    base = Path(root) / "canonical-platform" if is_canonical(binding) else Path(root)
    folder = base / source_commit(binding)
    return folder if value in LEGACY else folder / "profiles" / value


def source_commit(binding):
    source = binding.get("candidate_commit", "")
    require(
        isinstance(source, str) and re.fullmatch(r"[a-f0-9]{40}", source),
        "EXACT_AI_PROFILE_SOURCE_REQUIRED",
    )
    return source
