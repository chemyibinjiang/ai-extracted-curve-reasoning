"""Check exploration links and boundaries without opening large archives."""
import ast
import csv
from html.parser import HTMLParser
from pathlib import Path
import re
import subprocess
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT / "exploration/agent_conversation_records"


class Images(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sources = []

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            self.sources.append(dict(attrs)["src"])


class RepositoryLayoutTests(unittest.TestCase):
    def test_exploration_documentation_links(self):
        self.assertFalse((ROOT / "agent_conversation_records").exists())
        for path in [ROOT / name for name in ("README.md", "CODE_ORGANIZATION.md", "REPRODUCIBILITY.md",
                     "exploration/README.md", "exploration/agent_conversation_records/README.md")]:
            for link in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                parts = urlsplit(link)
                if parts.scheme or not parts.path:
                    continue
                target = (path.parent / unquote(parts.path)).resolve()
                self.assertTrue(target.is_relative_to(ROOT), (path, link))
                self.assertTrue(target.exists(), (path, link))

    def test_transcript_and_image_paths(self):
        with (RECORDS / "export_manifest.csv").open(encoding="utf-8-sig", newline="") as stream:
            records = list(csv.DictReader(stream))
        self.assertEqual(len(records), 2)
        for record in records:
            for key in ("html_transcript", "markdown_transcript"):
                path = RECORDS / record[key].replace("\\", "/")
                self.assertTrue(path.is_file(), path)
            html = RECORDS / record["html_transcript"].replace("\\", "/")
            parser = Images()
            parser.feed(html.read_text(encoding="utf-8"))
            self.assertTrue(parser.sources)
            for source in parser.sources:
                parts = urlsplit(source)
                if parts.scheme:
                    continue
                target = (html.parent / unquote(parts.path)).resolve()
                self.assertTrue(target.is_relative_to(RECORDS))
                self.assertTrue(target.is_file(), target)
        with (RECORDS / "image_manifest.csv").open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                if row["output_path"]:
                    self.assertTrue((RECORDS / row["output_path"].replace("\\", "/")).is_file(), row["output_path"])

    def test_renderer_uses_repository_root_after_move(self):
        source = (RECORDS / "tools/render_codex_session_html.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        names = {"path_variants", "public_path_replacements"}
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        namespace = dict(Path=Path, OUT_ROOT=RECORDS)
        # Path handling can be checked without Pillow or regenerating transcripts.
        exec(compile(ast.Module(body=functions, type_ignores=[]), "renderer-path-functions", "exec"), namespace)
        replacements = namespace["public_path_replacements"]()
        self.assertIn((str(ROOT), "[PUBLIC_REPO]"), replacements)
        self.assertNotIn((str(ROOT / "exploration"), "[PUBLIC_REPO]"), replacements)

    def test_local_only_archive_remains_ignored(self):
        for path, ignored in [
            ("exploration/agent_conversation_records/0-LSV_agent_analysis_raw_data.zip", True),
            ("exploration/agent_conversation_records/export.local.json", True),
            ("exploration/README.md", False),
            ("exploration/agent_conversation_records/raw_codex_session_jsonl.zip", False),
        ]:
            result = subprocess.run(["git", "check-ignore", "--no-index", "-q", "--", path], cwd=ROOT)
            self.assertEqual(result.returncode, 0 if ignored else 1, path)


if __name__ == "__main__":
    unittest.main()
