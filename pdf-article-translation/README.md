# PDF article translation

Convert PDF articles to Markdown with figures and a Russian translation.
Build PDFs using Pandoc and pdflatex.
Both PDFs are built by default; request Markdown only to skip compilation.

See the [repository README](../README.md) for installation and
[SKILL.md](SKILL.md) for agent instructions.

## Usage

```text
Use $pdf-article-translation with ./input.pdf.
Work in the current directory.
```

The result contains:

```text
.gitignore              Ignore PDFs and intermediate files
.gitattributes          Normalize text files to LF
article.md              Reconstructed original article
article.ru.md           Russian translation
README.md               Russian file inventory and build instructions; English title
images/figure-01.png    Shared figure files
figures.json            Extraction methods, parameters, and revision history
image-extraction.md     Commands and figure previews
header.tex              Default preamble created by readme/build if absent
article.pdf             Compiled original article
article.ru.pdf          Compiled Russian translation
```

To correct a figure, describe the affected edge:

```text
Figure-03 is clipped on the left. Figure-07 has excess space below it.
```

Start Codex in a directory containing the input PDF. Results are written
there by default, and the input is reused under its existing name. An
explicit separate output directory is also supported.
The generated `.gitignore` excludes `*.pdf`, `/raw/`, and `/pages/`.
Figures can be extracted with `pdfimages` or cropped from a page; the agent
must visually compare each result with the PDF before accepting it.
English Markdown uses ASCII only. Russian Markdown allows ASCII and Russian
letters, including Yo. Math symbols use LaTeX commands.

## Dependencies

- Python 3.11+, Poppler, and Pandoc.
- Tesseract with the source language's OCR data for scanned articles.
- pdflatex and the header's LaTeX packages, including Cyrillic support.

## Build PDFs

From the repository root:

```bash
python3 pdf-article-translation/scripts/article.py build /path/to/output
```

This creates `article.pdf` and `article.ru.pdf`. A default `header.tex` is
created if absent; existing headers are preserved. To use another header,
add `--header /path/to/header.tex`.
The original PDF and intermediate files are not needed to build the Markdown.
Restore the original PDF locally before changing figure crops after cloning.

The output directory's Russian README contains Ubuntu/Debian dependency
installation commands and direct Pandoc build commands.

## Tests

From the repository root:

```bash
python3 -m unittest discover -s pdf-article-translation/tests -v
```
