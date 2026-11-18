"""Behavioral checks using an actual PDF and installed Poppler/Pandoc."""

import importlib.util
from pathlib import Path
import shutil
import shlex
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

    @unittest.skipUnless(shutil.which("pdflatex"), "pdflatex is required")
    def test_build_default_header_and_preserve_local_edits(self):
        for filename, title in (("article.md", "Article"),
                                ("article.ru.md", "\u041f\u0440\u0438\u0432\u0435\u0442")):
            (self.workspace / filename).write_text(
                f"# {title}\n\nText $x^2$.\n\n![Diagram](images/figure-01.png)\n",
                encoding="utf-8",
            )
        self.call("build", self.workspace)
        header = self.workspace / "header.tex"
        self.assertTrue(header.is_file())
        for filename in ("article.pdf", "article.ru.pdf"):
            self.assertTrue((self.workspace / filename).read_bytes().startswith(b"%PDF-"))
        extracted = article.run(["pdftotext", self.workspace / "article.ru.pdf", "-"])
        self.assertIn("\u041f\u0440\u0438\u0432\u0435\u0442", extracted)
        readme = self.workspace / "README.md"
        instructions = readme.read_text(encoding="utf-8")
        self.assertTrue(instructions.startswith("# Article\n"))
        # Published commands must work directly, without the skill script.
        for line in instructions.splitlines():
            if line.startswith("pandoc "):
                article.run(shlex.split(line), cwd=self.workspace)
        readme.write_text(instructions + "\nLocal notes.\n", encoding="utf-8")

        edited = header.read_text() + "\n% User formatting change\n"
        header.write_text(edited, encoding="utf-8")
        self.call("build", self.workspace)
        self.assertEqual(header.read_text(), edited)
        self.assertEqual(readme.read_text(), instructions + "\nLocal notes.\n")

        # An explicit header takes precedence even if the local one is invalid.
        custom = self.workspace.parent / "custom header.tex"
        custom.write_text(edited, encoding="utf-8")
        header.write_text("\\undefinedLocalCommand\n", encoding="utf-8")
        self.call("build", self.workspace, "--header", custom)
        self.assertEqual(header.read_text(), "\\undefinedLocalCommand\n")
        self.assertEqual(custom.read_text(), edited)

    def test_readme_without_build_and_custom_header(self):
        (self.workspace / "article.md").write_text("# An article about C#\n\nText.\n")
        russian_title = "\u0421\u0442\u0430\u0442\u044c\u044f \u043e C#"
        (self.workspace / "article.ru.md").write_text(
            f"# {russian_title}\n\nText.\n", encoding="utf-8")
        custom = self.workspace.parent / "custom header.tex"
        custom.write_text(article.DEFAULT_HEADER)
        self.call("readme", self.workspace, "--header", custom)
        self.assertFalse((self.workspace / "header.tex").exists())
        self.assertFalse((self.workspace / "article.pdf").exists())
        content = (self.workspace / "README.md").read_text()
        self.assertTrue(content.startswith("# An article about C#\n"))
        commands = [shlex.split(line) for line in content.splitlines()
                    if line.startswith("pandoc ")]
        self.assertEqual(len(commands), 2)
        for command in commands:
            self.assertEqual(command[command.index("-H") + 1], str(custom))
        russian_readme = self.workspace / "README.ru.md"
        russian = russian_readme.read_text(encoding="utf-8")
        self.assertTrue(russian.startswith(f"# {russian_title}\n"))
        self.assertIn("\u0421\u0431\u043e\u0440\u043a\u0430 PDF", russian)
        self.assertEqual(commands, [shlex.split(line) for line in russian.splitlines()
                                    if line.startswith("pandoc ")])
        russian_readme.write_text(russian + "Local notes.\n", encoding="utf-8")
        self.call("readme", self.workspace, "--header", custom)
        self.assertEqual(russian_readme.read_text(encoding="utf-8"), russian + "Local notes.\n")
        # A preexisting English README must not prevent Russian generation.
        russian_readme.unlink()
        self.call("readme", self.workspace, "--header", custom)
        self.assertEqual(russian_readme.read_text(encoding="utf-8"), russian)
        self.assertEqual((self.workspace / "README.md").read_text(), content)


if __name__ == "__main__":
    unittest.main()
