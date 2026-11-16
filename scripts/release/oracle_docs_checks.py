"""Portable typed public Docs checks; the caller supplies exact source contracts.

No provider, account, credential, repository path or release authority is read here.
"""


def validate(acceptance, registry, manifest, *, require):
    """Require per-view evidence, rather than counts of unstructured PASS placeholders."""
    accessibility = acceptance.get("accessibility", [])
    require(
        isinstance(accessibility, list) and len(accessibility) >= 124,
        "Complete Docs accessibility views required",
    )
    coordinates = set()
    routes = set()
    for view in accessibility:
        require(
            isinstance(view, dict)
            and isinstance(view.get("route"), str)
            and view["route"].startswith("/")
            and "?" not in view["route"]
            and "#" not in view["route"]
            and view.get("mode") in {"light", "dark"}
            and view.get("width") in {320, 1440}
            and isinstance(view.get("violations"), list),
            "Structured Docs accessibility view required",
        )
        coordinate = (view["route"], view["mode"], view["width"])
        require(coordinate not in coordinates, "Duplicate Docs accessibility view")
        coordinates.add(coordinate)
        routes.add(view["route"])
        for violation in view["violations"]:
            require(
                isinstance(violation, dict)
                and isinstance(violation.get("id"), str)
                and violation.get("impact") in {None, "minor", "moderate"}
                and isinstance(violation.get("nodes"), list),
                "Blocking or malformed Docs accessibility violation",
            )
    require(
        coordinates
        == {
            (route, mode, width)
            for route in routes
            for mode in ["light", "dark"]
            for width in [320, 1440]
        },
        "Both system modes and widths required for every public Docs route",
    )
    widths = acceptance.get("widths", [])
    expected = {
        (route, "dark", width)
        for route in ["/", "/architecture", "/downloads", "/api-explorer"]
        for width in [320, 390, 768, 1024, 1440]
    }
    actual = []
    require(isinstance(widths, list), "Docs width evidence required")
    for view in widths:
        require(
            isinstance(view, dict) and view.get("overflow") is False,
            "Malformed or overflowing Docs width view",
        )
        actual.append((view.get("route"), view.get("mode"), view.get("width")))
    require(
        len(actual) == len(set(actual)) and set(actual) == expected,
        "Exact Docs width matrix required",
    )
    navigation = acceptance.get("navigation", [])
    expected_links = [
        {"label": app["label"], "href": app["href"].rstrip("/")}
        for app in registry["applications"]
    ]
    require(
        isinstance(navigation, list)
        and len(navigation) == 2
        and all(
            isinstance(view, dict) and view.get("links") == expected_links
            for view in navigation
        )
        and {view.get("view") for view in navigation} == {"desktop", "mobile"},
        "Exact four-product Docs navigation in both views required",
    )
    icons = acceptance.get("icons", [])
    expected_icons = {}
    for file in manifest["products"][0]["files"]:
        if file["name"] in {"onesa-docs.svg", "onesa-docs.ico", "onesa-docs-180.png"}:
            route = (
                "/favicon.ico"
                if file["name"].endswith(".ico")
                else "/brand/icons/v1/" + file["name"]
            )
            expected_icons[route] = file
    require(
        isinstance(icons, list) and len(icons) == 3,
        "Docs identity icon evidence required",
    )
    paths = []
    for icon in icons:
        require(
            isinstance(icon, dict) and icon.get("path") in expected_icons,
            "Structured Docs identity icon required",
        )
        expected_icon = expected_icons[icon["path"]]
        mimes = (
            {"image/x-icon", "image/vnd.microsoft.icon"}
            if icon["path"] == "/favicon.ico"
            else {expected_icon["mime"]}
        )
        require(
            icon.get("status") == 200
            and icon.get("sha256") == expected_icon["sha256"]
            and icon.get("mime") in mimes,
            "Actual Docs icon bytes/status/MIME required",
        )
        paths.append(icon["path"])
    require(len(set(paths)) == 3, "Duplicate Docs identity icon")
