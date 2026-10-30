"""Synthetic typed native contracts; no hosted identity, content or authority."""

import copy
import unittest

import oracle_docs_internal_checks as checks
import oracle_owner as owner


class ProtectedNativeContractTests(unittest.TestCase):
    def setUp(self):
        self.navigation = {
            "architecture": [
                {"diagram": "topic-" + str(i), "url": "/docs/topic-" + str(i)}
                for i in range(18)
            ],
            "chapters": [{"url": "/docs/chapter-" + str(i)} for i in range(17)],
            "days": [
                {"id": str(i), "checkpoints": ["synthetic checkpoint"]}
                for i in range(4)
            ],
        }
        self.catalog = [{"id": "diagram-" + str(i)} for i in range(87)]
        self.registry = {
            "applications": [
                {"label": name, "href": "https://" + name + ".example.invalid/"}
                for name in ["portal", "ai", "robot", "docs"]
            ]
        }
        self.icons = {
            "products": [
                {
                    "files": [
                        {"name": name, "sha256": chr(97 + i) * 64}
                        for i, name in enumerate(
                            ["onesa-docs.svg", "onesa-docs.ico", "onesa-docs-180.png"]
                        )
                    ]
                }
            ]
        }
        self.assets = ["/fixture-" + str(i) for i in range(100)]
        self.origins = [
            "https://" + name + ".example.invalid"
            for name in ["canonical", "custom", "preview"]
        ]
        self.team = "https://engineering.cloudflareaccess.com"
        views = [
            (route, mode, width)
            for route in ["/", "/architecture", "/onboarding"]
            for mode in ["light", "dark"]
            for width in [320, 768, 1440]
        ]
        self.value = {
            "result": "PASS",
            "javascript_errors": [],
            "layouts": [
                {
                    "route": route,
                    "mode": mode,
                    "width": width,
                    "overflow": False,
                    "diagram_visible": route != "/",
                }
                for route, mode, width in views
            ],
            "accessibility": [
                {"route": route, "mode": mode, "width": width, "violations": []}
                for route, mode, width in views
            ],
            "architecture": [
                {"diagram": topic["diagram"], "url": topic["url"], "visible": True}
                for topic in self.navigation["architecture"]
            ],
            "diagram_controls": {
                "zoom": True,
                "keyboard_pan": True,
                "dialog": True,
                "escape": True,
            },
            "chapters": [
                {"url": chapter["url"], "http_status": 200}
                for chapter in self.navigation["chapters"]
            ],
            "learning_days": [
                {"id": day["id"], "checkpoints": len(day["checkpoints"])}
                for day in self.navigation["days"]
            ],
            "existing_progress_preserved": True,
            "progress_mutations": 0,
            "search": {"query": "Day 4", "results_visible": True},
            "sidebar": [
                "Start here",
                "Product guides",
                "Tutorials",
                "API",
                "Architecture",
                "Troubleshooting and releases",
            ],
            "application_navigation": [
                {
                    "view": view,
                    "links": [
                        {"label": app["label"], "href": app["href"].rstrip("/")}
                        for app in self.registry["applications"]
                    ],
                }
                for view in ["desktop", "mobile"]
            ],
            "icons": [
                {
                    "path": "/favicon.ico"
                    if icon["name"].endswith(".ico")
                    else "/brand/icons/v1/" + icon["name"],
                    "sha256": icon["sha256"],
                }
                for icon in self.icons["products"][0]["files"]
            ],
            "api_reference": [
                {
                    "product": product,
                    "source_status": 200,
                    "swagger_visible": True,
                    "execution_controls": 0,
                }
                for product in ["ai", "portal", "robot"]
            ],
            "assistant": {"available": False, "form_count": 0, "network_mutations": 0},
            "manuals": 22,
            "links_checked": 100,
            "asset_security": [
                {
                    "route": route,
                    "cache_control": "private, no-store",
                    "robots": "noindex, nofollow",
                    "nosniff": "nosniff",
                }
                for route in self.assets
            ],
            "anonymous_denials": [
                {
                    "origin": origin,
                    "route": route,
                    "http_status": 302,
                    "followed_redirect": False,
                    "redirect_origin": self.team,
                }
                for origin in self.origins
                for route in self.assets
            ],
        }

    def validate(self, value):
        checks.validate(
            value,
            navigation=self.navigation,
            catalog=self.catalog,
            registry=self.registry,
            icon_manifest=self.icons,
            assets=self.assets,
            origins=self.origins,
            team_origin=self.team,
            require=owner.require,
        )

    def test_complete_typed_contract_is_not_itself_release_authority(self):
        self.assertIsNone(self.validate(self.value))
        self.assertNotIn("authorization", self.value)

    def test_every_required_field_is_mandatory_no_placeholder_pass(self):
        for key in self.value:
            value = copy.deepcopy(self.value)
            value.pop(key)
            with self.subTest(key=key), self.assertRaises(owner.Rejected):
                self.validate(value)
        with self.assertRaises(owner.Rejected):
            self.validate({"result": "PASS", "checks": {"workflow": "PASS"}})

    def test_missing_duplicate_overflow_or_wrong_mode_views_are_rejected(self):
        for field in ["layouts", "accessibility"]:
            for change in ["missing", "duplicate", "wrong-mode"]:
                value = copy.deepcopy(self.value)
                if change == "missing":
                    value[field].pop()
                elif change == "duplicate":
                    value[field][-1] = value[field][0]
                else:
                    value[field][0]["mode"] = "system"
                with (
                    self.subTest(field=field, change=change),
                    self.assertRaises(owner.Rejected),
                ):
                    self.validate(value)
        value = copy.deepcopy(self.value)
        value["layouts"][0]["overflow"] = True
        with self.assertRaises(owner.Rejected):
            self.validate(value)

    def test_critical_serious_or_malformed_accessibility_cannot_be_summarized_as_pass(
        self,
    ):
        for impact in ["critical", "serious", "unknown"]:
            value = copy.deepcopy(self.value)
            value["accessibility"][0]["violations"] = [
                {"id": "synthetic-failure", "impact": impact, "nodes": []}
            ]
            with self.subTest(impact=impact), self.assertRaises(owner.Rejected):
                self.validate(value)

    def test_changed_content_identity_or_learning_progress_is_refused(self):
        for field in [
            "architecture",
            "chapters",
            "learning_days",
            "application_navigation",
            "icons",
            "api_reference",
        ]:
            value = copy.deepcopy(self.value)
            value[field].pop()
            with self.subTest(field=field), self.assertRaises(owner.Rejected):
                self.validate(value)
        for field, replacement in [
            ("existing_progress_preserved", False),
            ("progress_mutations", 1),
            ("manuals", 21),
            ("javascript_errors", ["synthetic error"]),
            ("assistant", {"available": True, "form_count": 1, "network_mutations": 0}),
        ]:
            value = copy.deepcopy(self.value)
            value[field] = replacement
            with self.subTest(field=field), self.assertRaises(owner.Rejected):
                self.validate(value)

    def test_any_publicly_cacheable_indexable_or_missing_asset_blocks_acceptance(self):
        for field, replacement in [
            ("cache_control", "public, max-age=3600"),
            ("robots", "index"),
            ("nosniff", ""),
        ]:
            value = copy.deepcopy(self.value)
            value["asset_security"][0][field] = replacement
            with self.subTest(field=field), self.assertRaises(owner.Rejected):
                self.validate(value)
        value = copy.deepcopy(self.value)
        value["asset_security"].pop()
        with self.assertRaises(owner.Rejected):
            self.validate(value)

    def test_every_asset_and_alias_must_deny_anonymous_access_without_redirect_following(
        self,
    ):
        for field, replacement in [
            ("http_status", 200),
            ("http_status", 404),
            ("http_status", True),
            ("followed_redirect", True),
            ("redirect_origin", "https://attacker.example.invalid"),
            ("origin", "https://other.example.invalid"),
            ("route", "/unbound"),
        ]:
            value = copy.deepcopy(self.value)
            value["anonymous_denials"][0][field] = replacement
            with self.subTest(field=field), self.assertRaises(owner.Rejected):
                self.validate(value)
        for mutate in [lambda v: v.pop(), lambda v: v.append(v[0])]:
            value = copy.deepcopy(self.value)
            mutate(value["anonymous_denials"])
            with self.assertRaises(owner.Rejected):
                self.validate(value)
        for status in [401, 403]:
            value = copy.deepcopy(self.value)
            value["anonymous_denials"][0].update(
                http_status=status, redirect_origin=None
            )
            self.validate(value)


if __name__ == "__main__":
    unittest.main()
