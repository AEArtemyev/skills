# PDF article translation

Convert PDF articles to Markdown with figures and a Russian translation.
Build PDFs using Pandoc and pdflatex.

See the [repository README](../README.md) for installation and
[SKILL.md](SKILL.md) for agent instructions.

## Usage

```text
Use $pdf-article-translation with /path/to/input.pdf.
Save the results to /path/to/output.
```

Main outputs:

- `article.md` and `article.ru.md`: original article and Russian translation.
- `images/`: shared figures.
- `image-extraction.md`: extraction commands, previews, and crop history.
- `README.md` and `README.ru.md`: article title and PDF build instructions.

To correct a figure, describe the affected edge:

```text
Figure-03 is clipped on the left. Figure-07 has excess space below it.
```

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

The output directory's READMEs also contain direct Pandoc build commands.

## Tests

From the repository root:

```bash
python3 -m unittest discover -s pdf-article-translation/tests -v
```
