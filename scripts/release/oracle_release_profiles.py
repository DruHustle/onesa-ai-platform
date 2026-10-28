"""Literal AI release scopes; this module never issues or transfers authority.

The legacy two-profile policy remains supported. A newly commissioned six-profile
policy gives foundation, Twins and Cybersecurity separate exact component scopes,
each with one context per source. Paths and modes cannot be supplied by callers.
"""

import re
from pathlib import Path

REPOSITORY = "DruHustle/onesa-ai-platform"
PROFILES = {
    "api": ("api", "foundation"),
    "frontend": ("frontend", "foundation"),
    "twins-api": ("api", "twins"),
    "twins-frontend": ("frontend", "twins"),
    "cybersecurity-api": ("api", "cybersecurity"),
    "cybersecurity-frontend": ("frontend", "cybersecurity"),
}
LEGACY = frozenset({"api", "frontend"})
SCOPED = frozenset(PROFILES)


class ProfileError(ValueError):
    pass


def require(value, code):
    if not value:
        raise ProfileError(code)


def component(binding):
    value = binding.get("component") if isinstance(binding, dict) else None
    require(isinstance(value, str) and value in PROFILES, "UNKNOWN_AI_RELEASE_PROFILE")
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
    scopes = {REPOSITORY + ":" + c for c in LEGACY}
    complete = {REPOSITORY + ":" + c for c in SCOPED}
    require(set(profiles) in [scopes, complete], "AI_POLICY_PROFILE_SET_REFUSED")
    selected = LEGACY if set(profiles) == scopes else SCOPED
    for name in selected:
        profile = profiles[REPOSITORY + ":" + name]
        require(
            isinstance(profile, dict)
            and type(profile.get("qualification_attempt_limit")) is int
            and profile["qualification_attempt_limit"] == 1,
            "ONE_CONTEXT_PER_PROFILE_SOURCE_REQUIRED",
        )
        if selected == SCOPED:
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
    require(value in selected, "AI_PROFILE_NOT_COMMISSIONED")
    bound_mode(binding, mode)
    if selected == SCOPED:
        require(mode == PROFILES[value][1], "AI_PROFILE_MODE_MISMATCH")
    return mode


def bound_mode(binding, mode):
    value = component(binding)
    require(mode in {"foundation", "twins", "cybersecurity"}, "UNKNOWN_AI_RELEASE_MODE")
    if value not in LEGACY:
        require(mode == PROFILES[value][1], "AI_PROFILE_MODE_MISMATCH")
    return mode


def enabled_features(values, mode):
    """Use actual private runtime flags, never a caller-selected test subset."""
    require(mode in {"foundation", "twins", "cybersecurity"}, "UNKNOWN_AI_RELEASE_MODE")
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
        not enabled if mode == "foundation" else mode in enabled,
        "AI_RUNTIME_FEATURE_MODE_MISMATCH",
    )
    return enabled


def plan_path(binding, api_plan, frontend_plan):
    value = component(binding)
    base = Path(api_plan if kind(binding) == "api" else frontend_plan)
    if value in LEGACY:
        return base
    return base.with_name("oracle-ai-" + value + "-release.json")


def artifact_folder(binding, root):
    value = component(binding)
    source = source_commit(binding)
    folder = Path(root) / "artifacts" / source
    return folder if value in LEGACY else folder / "profiles" / value


def configuration_folder(binding, root):
    value = component(binding)
    folder = Path(root) / source_commit(binding)
    return folder if value in LEGACY else folder / "profiles" / value


def source_commit(binding):
    source = binding.get("candidate_commit", "")
    require(
        isinstance(source, str) and re.fullmatch(r"[a-f0-9]{40}", source),
        "EXACT_AI_PROFILE_SOURCE_REQUIRED",
    )
    return source
