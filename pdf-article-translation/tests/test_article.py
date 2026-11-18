"""Behavioral checks using an actual PDF and installed Poppler/Pandoc."""

import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / "scripts/article.py"
spec = importlib.util.spec_from_file_location("article", TOOL)
article = importlib.util.module_from_spec(spec)
spec.loader.exec_module(article)


def make_pdf(path):
    # A minimal, searchable one-page PDF with a vector rectangle.
    content = b"0 0 0 rg 30 40 50 60 re f\nBT /F1 12 Tf 10 120 Td (Test article) Tj ET\n"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 144 144] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"endstream",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    start = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
                f"startxref\n{start}\n%%EOF\n".encode())
    path.write_bytes(data)


@unittest.skipUnless(all(shutil.which(tool) for tool in
                         ("pdftoppm", "pdftotext", "pdfinfo", "pandoc")),
                     "Poppler and Pandoc are required")
class ArticleTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="article test ")
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.source = root / "original input.pdf"
        self.workspace = root / "workspace with spaces"
        make_pdf(self.source)
        self.original = self.source.read_bytes()
        self.call("prepare", self.source, self.workspace, "--dpi", 72)
        self.call("figure", self.workspace, "--id", "figure-01", "--page", 1,
                  "--box", 30, 44, 50, 60, "--note", "Initial")

    def call(self, *args, success=True):
        result = subprocess.run([sys.executable, str(TOOL), *map(str, args)],
                                capture_output=True, text=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def test_adjust_and_journal_replay(self):
        self.call("adjust", self.workspace, "--id", "figure-01", "--left", 10,
                  "--top", -5, "--right", -3, "--bottom", 7, "--note", "Revision")
        data = article.load(self.workspace)
        figure = data["figures"]["figure-01"]
        self.assertEqual(figure["box"], [20, 49, 57, 62])
        self.assertEqual(len(figure["history"]), 2)
        image = self.workspace / "images/figure-01.png"
        self.assertEqual(article.png_size(image), (57, 62))
        command = article.crop_command(data, "figure-01", figure)
        article.run(command[:-1] + ["images/replayed"], cwd=self.workspace)
        self.assertEqual(image.read_bytes(), (self.workspace / "images/replayed.png").read_bytes())
        self.assertIn("-x 20 -y 49 -W 57 -H 62", (self.workspace / "image-extraction.md").read_text())
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_invalid_adjustment_preserves_existing_artifacts(self):
        before = {name: (self.workspace / name).read_bytes() for name in
                  ("figures.json", "image-extraction.md", "images/figure-01.png")}
        result = self.call("adjust", self.workspace, "--id", "figure-01", "--left", 100,
                           "--note", "Outside page", success=False)
        self.assertIn("outside page", result.stderr)
        for name, content in before.items():
            self.assertEqual((self.workspace / name).read_bytes(), content)

    def test_reprepare_refuses_to_overwrite_workspace(self):
        self.call("prepare", self.source, self.workspace, success=False)
        self.assertEqual(article.png_size(self.workspace / "images/figure-01.png"), (50, 60))

    def test_changed_source_is_rejected(self):
        with (self.workspace / "source.pdf").open("ab") as stream:
            stream.write(b"\n% Changed\n")
        result = self.call("page", self.workspace, "--page", 1, success=False)
        self.assertIn("source.pdf changed", result.stderr)

    def test_translation_math_and_images(self):
        original = "# Article\n\nText $x^2$.\n\n![Figure](images/figure-01.png)\n"
        translated = "# Translation\n\nOther text $x^2$.\n\n![Caption](images/figure-01.png)\n"
        (self.workspace / "article.md").write_text(original)
        target = self.workspace / "article.ru.md"
        target.write_text(translated)
        self.call("check", self.workspace)
        target.write_text(translated.replace("x^2", "x^3"))
        self.assertIn("math", self.call("check", self.workspace, success=False).stderr)
        target.write_text(translated.replace("figure-01.png", "missing.png"))
        self.assertIn("existing local", self.call("check", self.workspace, success=False).stderr)
        target.write_text("")
        self.assertIn("article is empty", self.call("check", self.workspace, success=False).stderr)


if __name__ == "__main__":
    unittest.main()
