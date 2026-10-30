"""Typed protected Docs observations; these values alone grant no authority.

Only the separately commissioned closed native producer may attest them. The
owner driver independently binds the source, complete artifact and live provider
Access policy before accepting an observation into the one-use release ledger.
"""


def validate(
    value,
    *,
    navigation,
    catalog,
    registry,
    icon_manifest,
    assets,
    origins,
    team_origin,
    require,
    rollback=None,
):
    require(isinstance(value, dict), "STRUCTURED_PROTECTED_DOCS_ACCEPTANCE_REQUIRED")
    require(
        value.get("result") == "PASS" and value.get("javascript_errors") == [],
        "COMPLETE_PROTECTED_UI_WITHOUT_SCRIPT_ERRORS_REQUIRED",
    )
    expected_layouts = {
        (route, mode, width)
        for route in ["/", "/architecture", "/onboarding"]
        for mode in ["light", "dark"]
        for width in [320, 768, 1440]
    }
    observed = []
    for view in value.get("layouts", []):
        require(
            isinstance(view, dict)
            and view.get("overflow") is False
            and view.get("diagram_visible")
            is (view.get("route") in {"/architecture", "/onboarding"}),
            "COMPLETE_PROTECTED_REFLOW_AND_RENDERING_REQUIRED",
        )
        observed.append((view.get("route"), view.get("mode"), view.get("width")))
    require(
        len(observed) == len(set(observed)) and set(observed) == expected_layouts,
        "ALL_EIGHTEEN_PROTECTED_LAYOUTS_REQUIRED",
    )
    audited = []
    for view in value.get("accessibility", []):
        require(
            isinstance(view, dict) and isinstance(view.get("violations"), list),
            "STRUCTURED_PROTECTED_ACCESSIBILITY_REQUIRED",
        )
        audited.append((view.get("route"), view.get("mode"), view.get("width")))
        for violation in view["violations"]:
            require(
                isinstance(violation, dict)
                and isinstance(violation.get("id"), str)
                and violation.get("impact") in {None, "minor", "moderate"}
                and isinstance(violation.get("nodes"), list),
                "BLOCKING_OR_MALFORMED_PROTECTED_ACCESSIBILITY",
            )
    require(
        len(audited) == len(set(audited)) and set(audited) == expected_layouts,
        "ALL_EIGHTEEN_PROTECTED_ACCESSIBILITY_VIEWS_REQUIRED",
    )
    topics = navigation["architecture"]
    require(
        len(topics) == 18
        and len(navigation["chapters"]) == 17
        and len(navigation["days"]) == 4
        and len(catalog) == 87,
        "EXACT_QUALIFIED_ENGINEERING_SOURCE_CONTRACT_REQUIRED",
    )
    require(
        value.get("architecture")
        == [
            {"diagram": topic["diagram"], "url": topic["url"], "visible": True}
            for topic in topics
        ],
        "EVERY_QUALIFIED_ARCHITECTURE_TOPIC_REQUIRED",
    )
    require(
        value.get("diagram_controls")
        == {"zoom": True, "keyboard_pan": True, "dialog": True, "escape": True},
        "ACTUAL_ENGINEERING_DIAGRAM_CONTROLS_REQUIRED",
    )
    require(
        value.get("chapters")
        == [
            {"url": chapter["url"], "http_status": 200}
            for chapter in navigation["chapters"]
        ],
        "EVERY_SOURCE_BOUND_ONBOARDING_CHAPTER_REQUIRED",
    )
    require(
        value.get("learning_days")
        == [
            {"id": day["id"], "checkpoints": len(day["checkpoints"])}
            for day in navigation["days"]
        ]
        and value.get("existing_progress_preserved") is True
        and value.get("progress_mutations") == 0,
        "FOUR_DAYS_AND_EXISTING_OWNER_PROGRESS_PRESERVATION_REQUIRED",
    )
    require(
        value.get("search") == {"query": "Day 4", "results_visible": True}
        and value.get("sidebar")
        == [
            "Start here",
            "Product guides",
            "Tutorials",
            "API",
            "Architecture",
            "Troubleshooting and releases",
        ],
        "ENGINEERING_SEARCH_AND_LEARNING_NAVIGATION_REQUIRED",
    )
    expected_links = [
        {"label": app["label"], "href": app["href"].rstrip("/")}
        for app in registry["applications"]
    ]
    require(
        value.get("application_navigation")
        == [{"view": view, "links": expected_links} for view in ["desktop", "mobile"]],
        "EXACT_APPROVED_APPLICATION_NAVIGATION_REQUIRED",
    )
    icons = []
    for icon in icon_manifest["products"][0]["files"]:
        if icon["name"] in {"onesa-docs.svg", "onesa-docs.ico", "onesa-docs-180.png"}:
            icons.append(
                {
                    "path": "/favicon.ico"
                    if icon["name"].endswith(".ico")
                    else "/brand/icons/v1/" + icon["name"],
                    "sha256": icon["sha256"],
                }
            )
    require(
        len(icons) == 3 and value.get("icons") == icons,
        "QUALIFIED_PROTECTED_DOCS_ICON_BYTES_REQUIRED",
    )
    require(
        value.get("api_reference")
        == [
            {
                "product": product,
                "source_status": 200,
                "swagger_visible": True,
                "execution_controls": 0,
            }
            for product in ["ai", "portal", "robot"]
        ]
        and value.get("assistant")
        == {"available": False, "form_count": 0, "network_mutations": 0},
        "READ_ONLY_API_AND_DISABLED_HOSTED_ASSISTANT_REQUIRED",
    )
    require(
        type(value.get("manuals")) is int
        and value["manuals"] == 22
        and type(value.get("links_checked")) is int
        and 0 < value["links_checked"] <= 500000,
        "COMPLETE_ENGINEERING_MANUALS_AND_LINKS_REQUIRED",
    )
    require(
        isinstance(assets, list)
        and 100 <= len(assets) <= 20000
        and len(set(assets)) == len(assets),
        "ROOT_BOUND_COMPLETE_PROTECTED_ASSET_SET_REQUIRED",
    )
    secured = []
    for result in value.get("asset_security", []):
        require(
            isinstance(result, dict)
            and result.get("route") in assets
            and isinstance(result.get("cache_control"), str)
            and "no-store"
            in {part.strip().lower() for part in result["cache_control"].split(",")}
            and isinstance(result.get("robots"), str)
            and "noindex"
            in {part.strip().lower() for part in result["robots"].split(",")}
            and result.get("nosniff") == "nosniff",
            "EVERY_AUTHENTICATED_ASSET_MUST_REMAIN_PRIVATE_NOINDEX_NOSTORE",
        )
        secured.append(result["route"])
    require(
        len(secured) == len(set(secured)) and set(secured) == set(assets),
        "COMPLETE_PRIVATE_ASSET_SECURITY_REQUIRED",
    )
    require(
        isinstance(origins, list) and len(origins) == len(set(origins)) == 3,
        "EXACT_EXISTING_CANONICAL_CUSTOM_AND_PREVIEW_ORIGINS_REQUIRED",
    )
    expected_denials = {(origin, route) for origin in origins for route in assets}
    denied = []
    for result in value.get("anonymous_denials", []):
        require(
            isinstance(result, dict)
            and result.get("followed_redirect") is False
            and type(result.get("http_status")) is int
            and result["http_status"] in {302, 401, 403}
            and (
                result.get("redirect_origin") == team_origin
                if result["http_status"] == 302
                else result.get("redirect_origin") is None
            ),
            "GENUINE_ALL_PATH_ACCESS_DENIAL_REQUIRED_NO_BYPASS",
        )
        denied.append((result.get("origin"), result.get("route")))
    require(
        len(denied) == len(set(denied)) and set(denied) == expected_denials,
        "EVERY_ASSET_ON_ALL_THREE_HOST_ALIASES_MUST_DENY_ANONYMOUS_ACCESS",
    )

    if rollback is not None:
        require(
            value.get("rollback_readiness")
            == {
                **rollback,
                "origin": "https://docs.engineering.onesa.eu",
                "private_headers": True,
                "index_and_provenance_read_back": True,
                "classification": "internal",
                "provider_writes": 0,
            },
            "ACTUAL_RETAINED_PRIVATE_ROLLBACK_READBACK_REQUIRED",
        )
    else:
        require(
            "rollback_readiness" not in value,
            "PRIVATE_ROLLBACK_PROOF_HAS_NO_SIGNED_TARGET",
        )
