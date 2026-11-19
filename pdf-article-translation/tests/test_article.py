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
    # A searchable page containing a vector rectangle and an embedded RGB image.
    content = b"0 0 0 rg 30 40 50 60 re f\nBT /F1 12 Tf 10 120 Td (Test article) Tj ET\n"
    content += b"q 20 0 0 20 100 10 cm /Im1 Do Q\n"
    pixels = bytes([255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 255])
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 144 144] "
        b"/Resources << /Font << /F1 4 0 R >> /XObject << /Im1 6 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"endstream",
        b"<< /Type /XObject /Subtype /Image /Width 2 /Height 2 "
        b"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Length 12 >>\nstream\n"
        + pixels + b"\nendstream",
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
                         ("pdftoppm", "pdftotext", "pdfinfo", "pdfimages", "pandoc")),
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

    @unittest.skipUnless(shutil.which("git"), "Git is required")
    def test_git_rules_ignore_only_workspace_pdfs_and_normalize_text(self):
        article.run(["git", "init", "--quiet", self.workspace])
        for name in ("source.pdf", "article.pdf", "article.ru.pdf"):
            self.assertEqual(article.run(["git", "check-ignore", name],
                                         cwd=self.workspace).strip(), name)
        result = subprocess.run(["git", "check-ignore", "other.pdf", "article.md",
                                 "images/figure-01.png", "nested/source.pdf"],
                                cwd=self.workspace, capture_output=True)
        self.assertEqual(result.returncode, 1)
        text = self.workspace / "notes.md"
        text.write_bytes(b"First\r\nSecond\r\n")
        normalized = subprocess.run(["git", "hash-object", "--stdin"],
                                    input=b"First\nSecond\n", cwd=self.workspace,
                                    capture_output=True, check=True).stdout.decode().strip()
        self.assertEqual(article.run(["git", "hash-object", "--path=notes.md", text],
                                     cwd=self.workspace).strip(), normalized)
        image = self.workspace / "images/figure-01.png"
        self.assertEqual(article.run(["git", "hash-object", "--path=images/figure-01.png", image],
                                     cwd=self.workspace),
                         article.run(["git", "hash-object", image], cwd=self.workspace))

    def test_git_files_preserve_edits_and_recreate_missing_file(self):
        ignore = self.workspace / ".gitignore"
        edited = ignore.read_bytes() + b"/local-notes.txt\n"
        ignore.write_bytes(edited)
        attributes = self.workspace / ".gitattributes"
        attributes.unlink()
        article.create_git_files(self.workspace)
        self.assertEqual(ignore.read_bytes(), edited)
        self.assertTrue(attributes.exists())
        attributes.write_bytes(b"*.txt text eol=lf\n")
        article.create_git_files(self.workspace)
        self.assertEqual(attributes.read_bytes(), b"*.txt text eol=lf\n")

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

    def test_article_character_limits(self):
        english = "# Article\n\nText $\\alpha$.\n\n![Diagram](images/figure-01.png)\n"
        russian_letters = "".join(map(chr, range(0x0410, 0x0450))) + "\u0401\u0451"
        translated = english.replace("Text", russian_letters)
        source = self.workspace / "article.md"
        target = self.workspace / "article.ru.md"
        source.write_text(english, encoding="utf-8")
        target.write_text(translated, encoding="utf-8")
        self.call("check", self.workspace)
        source.write_text(english.replace("Text", "Text \u00e9"), encoding="utf-8")
        result = self.call("check", self.workspace, success=False)
        self.assertIn("article.md:3:6:", result.stderr)
        self.assertIn("U+00E9", result.stderr)
        source.write_text(english, encoding="utf-8")
        for character in ("\u0456", "\u03b1", "\u2014", "\u00a0"):
            with self.subTest(character=character):
                target.write_text(translated.replace(russian_letters, character), encoding="utf-8")
                result = self.call("check", self.workspace, success=False)
                self.assertIn("article.ru.md:3:1:", result.stderr)
                self.assertIn(f"U+{ord(character):04X}", result.stderr)

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
        self.assertFalse((self.workspace / "README.ru.md").exists())
        self.assertIn("\u0421\u0431\u043e\u0440\u043a\u0430 PDF", content)
        inventory = content.split("```text\n", 1)[1].split("```", 1)[0]
        rows = [line.split(maxsplit=1) for line in inventory.strip().splitlines()]
        self.assertEqual({row[0] for row in rows}, {
            ".gitignore", ".gitattributes", "source.pdf", "article.md", "article.ru.md",
            "README.md", "images/figure-01.png", "figures.json", "image-extraction.md",
            "raw/", "pages/", "header.tex", "article.pdf", "article.ru.pdf",
        })
        for filename, description in rows:
            self.assertTrue(any(0x0410 <= ord(c) <= 0x044F for c in description), filename)
        install = next(shlex.split(line) for line in content.splitlines()
                       if line.startswith("sudo apt install "))
        self.assertTrue({"pandoc", "texlive-latex-extra", "texlive-lang-cyrillic"}
                        .issubset(install))
        (self.workspace / "README.md").write_text(content + "Local notes.\n", encoding="utf-8")
        self.call("readme", self.workspace, "--header", custom)
        self.assertEqual((self.workspace / "README.md").read_text(), content + "Local notes.\n")

    def test_embedded_extraction_replay_and_page_crop_fallback(self):
        self.call("embedded", self.workspace, "--id", "figure-02", "--page", 1,
                  "--index", 0, "--note", "Embedded candidate")
        image = self.workspace / "images/figure-02.png"
        self.assertEqual(article.png_size(image), (2, 2))
        original = image.read_bytes()
        journal = (self.workspace / "image-extraction.md").read_text()
        section = journal.split("## figure-02\n", 1)[1]
        commands = section.split("```bash\n", 1)[1].split("```", 1)[0]
        image.unlink()
        for command in commands.strip().splitlines():
            article.run(shlex.split(command), cwd=self.workspace)
        self.assertEqual(image.read_bytes(), original)
        result = self.call("adjust", self.workspace, "--id", "figure-02", "--left", 1,
                           "--note", "Needs page crop", success=False)
        self.assertIn("page crop", result.stderr)
        self.assertEqual(image.read_bytes(), original)
        self.call("embedded", self.workspace, "--id", "figure-02", "--page", 1,
                  "--index", 99, "--note", "Missing object", success=False)
        self.assertEqual(image.read_bytes(), original)
        self.call("figure", self.workspace, "--id", "figure-02", "--page", 1,
                  "--box", 95, 109, 30, 30, "--note", "Use full-page rendering")
        self.assertEqual(article.png_size(image), (30, 30))
        self.call("adjust", self.workspace, "--id", "figure-02", "--left", 2,
                  "--note", "Expand page crop")
        self.assertEqual(article.png_size(image), (32, 30))
        history = article.load(self.workspace)["figures"]["figure-02"]["history"]
        self.assertEqual(len(history), 3)


if __name__ == "__main__":
    unittest.main()
