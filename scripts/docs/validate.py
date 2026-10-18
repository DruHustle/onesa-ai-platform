"""Validate source drift, classified assets, real PDFs and public exposure boundaries."""

import argparse
import hashlib
import json
from pathlib import Path

from pdf_links import validate_manual_source_links
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]


def validate(staged=False, assets_only=False):
    from ecosystem import validate as validate_ecosystem

    validate_ecosystem()
    from documentation_identity import validate_identity

    documentation_version = validate_identity()
    policy = json.loads((ROOT / "docs/documentation-policy.json").read_text())
    from visual_policy import validate_navigation

    validate_navigation(
        ROOT, json.loads((ROOT / "docs/diagrams/catalog.json").read_text())
    )
    approved = set(policy["public_sources"])
    for scope in ["public", "internal"]:
        generated = (
            ROOT
            / f"onesa-ai-platform-frontend/apps/docs/.generated/{scope}/static/generated"
        )
        provenance = json.loads((generated / "provenance.json").read_text())
        if scope == "internal":
            assert (
                provenance["navigation_sha256"]
                == hashlib.sha256(
                    (ROOT / "docs/ecosystem/visual-navigation.json").read_bytes()
                ).hexdigest()
            ), "Engineering navigation drift"
            assert (
                json.loads((generated / "engineering-navigation.json").read_text())[
                    "classification"
                ]
                == "internal"
            )
        else:
            assert not (generated / "engineering-navigation.json").exists()
        for source, digest in provenance["sources"].items():
            assert hashlib.sha256((ROOT / source).read_bytes()).hexdigest() == digest, (
                f"Source drift: {source}"
            )
            if scope == "public":
                assert source in approved, f"Unapproved source: {source}"
        for source, digest in provenance.get("code_sources", {}).items():
            assert hashlib.sha256((ROOT / source).read_bytes()).hexdigest() == digest, (
                f"Code/schema drift: {source}"
            )
        current_code = hashlib.sha256(
            b"".join(
                p.read_bytes()
                for p in sorted((ROOT / "onesa-ai-platform-backend/app").glob("*.py"))
                + sorted(
                    (ROOT / "onesa-ai-platform-backend/migrations/versions").glob(
                        "*.py"
                    )
                )
            )
        ).hexdigest()
        assert provenance["code_sha256"] == current_code, (
            "API/ORM/migration drift; regenerate documentation"
        )
        docs = ROOT / f"onesa-ai-platform-frontend/apps/docs/.generated/{scope}/docs"
        if scope == "public":
            assert {
                "docs/" + p.relative_to(docs).as_posix() for p in docs.rglob("*.md")
            } == approved
            assert not (
                ROOT / "onesa-ai-platform-frontend/apps/docs/build-public/database.html"
            ).exists()
        retrieval = json.loads((generated / "retrieval.json").read_text())
        assert retrieval["classification"] == scope
        assert set(retrieval["approved_sources"]) == set(provenance["sources"])
        for chunk in retrieval["chunks"]:
            assert chunk["classification"] == scope
            assert chunk["source"] in retrieval["approved_sources"]
        schema = json.loads((generated / "openapi.json").read_text())
        assert all(path.startswith("/api/v1/") for path in schema["paths"])
        assert not any(
            word in str(schema)
            for word in ["host.docker.internal", "11434", "ONESA_METRICS_TOKEN"]
        )
        for product in ["portal", "robot"]:
            contract = json.loads((generated / f"openapi-{product}.json").read_text())
            assert contract["paths"] and not contract.get("servers")
            if scope == "public" and product == "portal":
                assert all(p.startswith("/api/v1/public/") for p in contract["paths"])
        diagrams = json.loads((generated / "diagrams.json").read_text())
        if scope == "public":
            assert {d["id"] for d in diagrams} == set(policy["public_diagrams"])
            assert "/api/v1/documentation/access" not in schema["paths"]
            assert all(
                not e["url"].startswith(
                    (
                        "/database",
                        "/docs/security/",
                        "/docs/operations/",
                        "/docs/development/",
                    )
                )
                for e in json.loads((generated / "search.json").read_text())
            )
        if scope == "public":
            allowed = {
                "openapi.json",
                "openapi-portal.json",
                "openapi-robot.json",
                "search.json",
                "diagrams.json",
                "retrieval.json",
                "provenance.json",
                "manuals.json",
                "screenshots.json",
            }
            allowed.update(
                f"diagrams/{name}.{ext}"
                for name in policy["public_diagrams"]
                for ext in ["svg", "png", "mmd", "pdf"]
            )
            if (generated / "manuals.json").exists():
                allowed.update(
                    "manuals/" + entry["file"]
                    for entry in json.loads((generated / "manuals.json").read_text())
                    if entry["classification"] == "public"
                    and entry["category"] in policy["public_pdfs"]
                )
            allowed.update(
                f"screenshots/{name}.png" for name in policy["public_screenshots"]
            )
            for asset in generated.rglob("*"):
                if asset.is_file():
                    assert asset.relative_to(generated).as_posix() in allowed, (
                        f"Unclassified public asset: {asset}"
                    )
        if staged:
            continue
        for d in diagrams:
            for extension in ["svg", "png", "mmd", "pdf"]:
                asset = generated / "diagrams" / f"{d['id']}.{extension}"
                assert asset.is_file(), f"Missing diagram: {asset}"
            assert (ROOT / d["source"]).read_bytes() == (
                generated / "diagrams" / f"{d['id']}.mmd"
            ).read_bytes(), f"Diagram drift: {d['id']}"
            assert (
                d["source_sha256"]
                == hashlib.sha256((ROOT / d["source"]).read_bytes()).hexdigest()
            )
            assert PdfReader(generated / "diagrams" / f"{d['id']}.pdf").pages, (
                "Empty diagram PDF"
            )
        manuals = json.loads((generated / "manuals.json").read_text())
        if scope == "public":
            assert {m["category"] for m in manuals} == set(policy["public_pdfs"])
        if scope == "internal":
            assert set(policy["required_ecosystem_manuals"]).issubset(
                {m["category"] for m in manuals}
            ), "Missing mandatory ecosystem manuals"
        for manual in manuals:
            path = generated / "manuals" / manual["file"]
            assert path.read_bytes().startswith(b"%PDF-")
            assert hashlib.sha256(path.read_bytes()).hexdigest() == manual["sha256"]
            for source, digest in manual.get("source_hashes", {}).items():
                assert (
                    hashlib.sha256((ROOT / source).read_bytes()).hexdigest() == digest
                ), f"PDF source drift: {source}"
            assert manual["version"] == documentation_version, "PDF version drift"
            document = PdfReader(path)
            cover = " ".join((document.pages[0].extract_text() or "").split())
            assert "Version " + documentation_version in cover, (
                "PDF cover version drift"
            )
            assert len(document.pages) >= 3
            text = "\n".join(page.extract_text() for page in document.pages)
            assert documentation_version in text and scope in text.lower()
            assert document.outline, f"Missing PDF bookmarks: {path}"
            links = {
                str(action["/URI"])
                for page in document.pages
                for ref in page.get("/Annots", [])
                if (action := ref.get_object().get("/A")) and action.get("/URI")
            }
            validate_manual_source_links(links, manual.get("source_hashes", {}), scope)
            if scope == "public":
                assert not any(
                    word in text
                    for word in [
                        "host.docker.internal",
                        "INTERNAL_CANARY",
                        "server.pid",
                        "ONESA_METRICS_TOKEN",
                    ]
                )
            manual["pages"] = len(document.pages)
        (generated / "manuals.json").write_text(json.dumps(manuals, indent=2) + "\n")
        (ROOT / f"docs/generated/{scope}/manuals.json").write_text(
            json.dumps(manuals, indent=2) + "\n"
        )
    if not staged and not assets_only:
        public = ROOT / "onesa-ai-platform-frontend/apps/docs/build-public"
        forbidden = [
            b"host.docker.internal",
            b"INTERNAL_CANARY",
            b"documentation_engineering_user_ids",
            b"ONESA_METRICS_TOKEN",
            b"3800291082",
            b"608f3f79f76e",
        ]
        for artifact in public.rglob("*"):
            if artifact.is_file() and artifact.suffix in [
                ".html",
                ".js",
                ".json",
                ".svg",
                ".map",
                ".txt",
            ]:
                data = artifact.read_bytes()
                assert not any(value in data for value in forbidden), (
                    f"Restricted content in {artifact}"
                )
        for directory in [
            "docs/architecture",
            "docs/database",
            "docs/security",
            "docs/development",
            "docs/operations",
            "docs/onboarding",
        ]:
            assert not (public / directory).exists(), (
                f"Internal pages exposed: {directory}"
            )
        assert not (public / "generated/database.json").exists()
    print(
        "Documentation provenance, classification, assets and PDFs validated."
        if not staged
        else "Classified staging allowlists validated."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--assets", action="store_true")
    parser.add_argument("--negative-test", action="store_true")
    args = parser.parse_args()
    if args.negative_test:
        validate()
        canary = (
            ROOT
            / "onesa-ai-platform-frontend/apps/docs/build-public/internal-exposure-canary.txt"
        )
        canary.write_text("INTERNAL_CANARY")
        try:
            try:
                validate()
            except AssertionError as error:
                assert "Restricted content" in str(
                    error
                ) and "internal-exposure-canary" in str(error), (
                    "Negative test failed for an unrelated reason"
                )
                print("Negative exposure test: rejected restricted public artifact.")
            else:
                raise RuntimeError("Exposure validator failed to reject canary")
        finally:
            canary.unlink()
    else:
        validate(args.staged, args.assets)
