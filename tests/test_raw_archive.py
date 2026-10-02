"""The downloadable ZIP and unpacked coordinate release must not drift."""
import importlib.util
from pathlib import Path
import tempfile
import subprocess
import sys
import json
import unittest
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("raw_audit", ROOT / "scripts/audit_raw_to_analysis.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class RawArchiveTests(unittest.TestCase):
    def test_zip_to_all_native_analysis_inputs(self):
        (ROOT / 'build').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='test-raw-audit-', dir=ROOT / 'build') as directory:
            result = subprocess.run([sys.executable, 'scripts/audit_raw_to_analysis.py', '--output', directory],
                                    cwd=ROOT, capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads((Path(directory) / 'RAW_TO_ANALYSIS_AUDIT.json').read_text())
            self.assertEqual(report['status'], 'pass')
            self.assertEqual(report['figure7_prepared_points'], 80399)
            self.assertEqual(report['template_native_inputs'], dict(curves=2267, points=51928))

    def test_released_archive_matches_every_file(self):
        self.assertEqual(set(audit.check_archive()), audit.NAMES)

    def test_detects_coordinate_and_document_drift(self):
        contents = audit.check_archive()
        with tempfile.TemporaryDirectory() as directory:
            for name in ("curve_points_long.csv", "README.md"):
                path = Path(directory) / "modified.zip"
                with ZipFile(path, "w", ZIP_DEFLATED) as zipped:
                    for member, raw in contents.items():
                        zipped.writestr(member, raw + b"\n" if member == name else raw)
                with self.assertRaisesRegex(ValueError, "ZIP/folder mismatch"):
                    audit.check_archive(path)

    def test_rejects_unexpected_archive_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "modified.zip"
            with ZipFile(path, "w") as zipped:
                zipped.writestr("../curve_points_long.csv", b"bad")
            with self.assertRaisesRegex(ValueError, "Unexpected or duplicate"):
                audit.check_archive(path)


if __name__ == "__main__":
    unittest.main()
