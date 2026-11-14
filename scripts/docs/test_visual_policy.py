import copy
import json
import tempfile
import unittest
from pathlib import Path

from visual_policy import validate_navigation

ROOT = Path(__file__).resolve().parents[2]


class VisualPolicyTests(unittest.TestCase):
    def fixture(self, directory):
        root = Path(directory)
        navigation = json.loads(
            (ROOT / "docs/ecosystem/visual-navigation.json").read_text()
        )
        catalog = json.loads((ROOT / "docs/diagrams/catalog.json").read_text())
        paths = {d["source"] for d in catalog}
        paths.update(
            entry["url"].lstrip("/") + ".md"
            for entry in navigation["architecture"]
            + navigation["chapters"]
            + navigation["days"]
        )
        paths.update(
            ref["url"].lstrip("/") + ".md"
            for day in navigation["days"]
            for ref in day["references"]
        )
        for path in paths:
            file = root / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("Synthetic maintained source")
        policy = root / "docs/ecosystem/visual-navigation.json"
        policy.parent.mkdir(parents=True, exist_ok=True)
        policy.write_text(json.dumps(navigation))
        return root, navigation, catalog, policy

    def test_current_references_exist(self):
        catalog = json.loads((ROOT / "docs/diagrams/catalog.json").read_text())
        self.assertEqual(
            validate_navigation(ROOT, catalog)["classification"], "internal"
        )

    def test_removed_reference_unknown_diagram_and_public_classification_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root, navigation, catalog, policy = self.fixture(directory)
            for mutate in [
                lambda n: n.update(classification="public"),
                lambda n: n["days"][0].update(diagram="missing"),
                lambda n: n["chapters"][0].update(url="/docs/missing"),
                lambda n: n["days"][0].update(checkpoints=[]),
            ]:
                invalid = copy.deepcopy(navigation)
                mutate(invalid)
                policy.write_text(json.dumps(invalid))
                with self.assertRaises(ValueError):
                    validate_navigation(root, catalog)

    def test_missing_and_symlinked_diagram_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _, catalog, _ = self.fixture(directory)
            source = root / catalog[0]["source"]
            source.unlink()
            with self.assertRaises(ValueError):
                validate_navigation(root, catalog)
            outside = root / "private-definition"
            outside.write_text("Synthetic private data")
            source.symlink_to(outside)
            with self.assertRaises(ValueError):
                validate_navigation(root, catalog)
