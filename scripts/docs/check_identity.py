"""Validate the single approved Docs browser icon and retained compatibility assets."""
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path


class Icons(HTMLParser):
    def __init__(self):
        super().__init__()
        self.icons = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "link" and attributes.get("rel") == "icon":
            self.icons.append(attributes)


def verify(app: Path):
    parser = Icons()
    parser.feed((app / "build-public/index.html").read_text())
    assert len(parser.icons) == 1, "Exactly one browser icon is required"
    icon = parser.icons[0]
    assert icon.get("href") == "/brand/icons/v1/onesa-docs.svg"
    assert icon.get("type") == "image/svg+xml" and icon.get("sizes") == "any"
    manifest = json.loads((app / "static/brand/icons/v1/sources.json").read_text())
    expected = {item["name"]: item for item in manifest["products"][0]["files"]}
    for name, relative in [("onesa-docs.svg", "brand/icons/v1/onesa-docs.svg"),
                           ("onesa-docs.ico", "favicon.ico"),
                           ("onesa-docs-180.png", "brand/icons/v1/onesa-docs-180.png")]:
        data = (app / "build-public" / relative).read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected[name]["sha256"], relative
        assert data == (app / "static" / relative).read_bytes(), relative
        if name.endswith(".ico"):
            assert data[:4] == b"\x00\x00\x01\x00", "Invalid ICO header"


if __name__ == "__main__":
    verify(Path(__file__).resolve().parents[2] / "onesa-ai-platform-frontend/apps/docs")
    print("Single typed Docs icon and all approved identity bytes verified.")
