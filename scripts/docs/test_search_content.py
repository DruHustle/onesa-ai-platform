import unittest

from search_content import api_entry, entry


class SearchContentTests(unittest.TestCase):
    def test_markdown_mermaid_and_html_are_readable_without_losing_search_terms(self):
        source = """# Authentication
Use **protected sessions** with [Onesa](/login).

```mermaid
flowchart LR
  SecretNode[Session] --> LoginNode
```

> Keep `csrf` enabled.
<script>not executable</script>
"""
        result = entry("Authentication", "/docs/auth", source)
        self.assertEqual(result["url"], "/docs/auth")
        self.assertIn("protected sessions with Onesa", result["preview"])
        for syntax in ["#", "**", "flowchart", "-->", "<script>", "```"]:
            self.assertNotIn(syntax, result["preview"])
        self.assertIn("SecretNode", result["keywords"])
        self.assertIn("csrf", result["text"])

    def test_preview_is_bounded_while_ranking_terms_are_preserved(self):
        result = entry("Long", "/docs/long", "word " * 100 + "uniqueEnding")
        self.assertLessEqual(len(result["preview"]), 241)
        self.assertIn("uniqueEnding", result["keywords"])

    def test_api_preview_is_prose_instead_of_serialized_schema(self):
        result = api_entry(
            "/api/v1/auth/login",
            "post",
            {
                "summary": "Create a session",
                "description": "Use **email** and password.",
                "parameters": [{"name": "remember"}],
                "responses": {"200": {"description": "Session created", "content": {}}},
            },
        )
        self.assertEqual(result["title"], "POST /api/v1/auth/login")
        self.assertEqual(result["url"], "/api-explorer")
        self.assertIn("200 Session created", result["preview"])
        self.assertNotIn("{", result["preview"])
