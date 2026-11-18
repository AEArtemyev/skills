# PDF article translation

Extract a PDF article into Markdown with figures, translate it into Russian,
and optionally build both PDFs using Pandoc, pdflatex, and a built-in or
custom LaTeX header.
The agent reconstructs and translates the article; the helper script performs
repeatable extraction, cropping, validation, and build operations. The script
does not call an LLM API.

See the [repository README](../README.md) for installation. Agent instructions
are in [SKILL.md](SKILL.md).

## First use

Invoke `$pdf-article-translation` and provide the input PDF and a new output
directory. For example:

```text
Use $pdf-article-translation with ~/papers/input.pdf.
Write the original article and Russian translation to ~/translations/example.
Build both PDFs using the default header.
Record figure extraction commands and visually inspect the figures.
```

The result contains:

```text
example/
  .gitignore              Ignore source.pdf, article.pdf, and article.ru.pdf
  .gitattributes          Normalize text files to LF
  source.pdf              Copy of input; never edited
  article.md              Reconstructed original article
  article.ru.md           Russian translation
  README.md               Article title and PDF compilation instructions
  README.ru.md            Russian article title and compilation instructions
  images/figure-01.png    Shared figure files
  figures.json            Coordinates and revision history
  image-extraction.md     Commands and figure previews
  raw/                    Extracted text and OCR evidence
  pages/                  Full-page images for visual review
  header.tex              Default preamble created by readme/build if absent
  article.pdf             Built when requested
  article.ru.pdf          Built when requested
```

The script creates extraction evidence, figures, and the journal. The agent
writes the two article Markdown files after comparing the PDF with that
evidence. It cannot guarantee flawless OCR, transcription, or translation.

`prepare` creates `.gitignore` with the three root-level PDF paths and
`.gitattributes` with `* text=auto eol=lf`. Git detects text automatically
and uses LF line endings while leaving binary content unchanged. The `readme`
and `build` commands also create missing files in older workspaces. Existing
Git configuration files are preserved without modification. No Git repository
is initialized by the script.

For corrections, refer to stable IDs and edges in natural language:

```text
In figure-03 the left edge is clipped. Figure-07 has too much space below it.
Correct these crops, inspect the results, and rebuild both PDFs.
```

The agent chooses pixel adjustments using the source page. You can also give
exact amounts. From the repository root (`~/dev/skills`), a script-only correction looks like:

```bash
python3 pdf-article-translation/scripts/article.py adjust \
  /path/to/example --id figure-03 --left 40 --note 'Restore left labels'
```

Positive values expand an edge; negative values remove space at that edge.
The script rejects rectangles outside the page and always renders from the
original PDF. Commands in `image-extraction.md` can recreate the current
PNGs from the workspace root. Use the script to change coordinates so that
its JSON record and generated Markdown journal stay synchronized.

## Dependencies and validation

Use Python 3.11+, Poppler (`pdfinfo`, `pdftotext`, `pdftoppm`), and Pandoc.
Scans additionally need Tesseract and the original language's OCR data.
PDF builds use pdflatex and the packages required by the header, including
Cyrillic support. The built-in preamble uses T2A/UTF-8 encodings, Russian and
English Babel, cmap, geometry, amsmath, amssymb, mathtools, cancel, graphicx,
grffile, and float, matching the previously supplied header's settings.

From the repository root, build both Markdown files with:

```bash
python3 pdf-article-translation/scripts/article.py build /path/to/example
```

The build also creates workspace `README.md` and `README.ru.md` with English
and Russian instructions. Each contains the H1 title from the corresponding
article, build dependencies, and direct Pandoc commands for both PDFs.
Each existing README is preserved independently. To generate instructions without
compiling PDFs, use:

```bash
python3 pdf-article-translation/scripts/article.py readme /path/to/example
```

This also creates the default `header.tex` if needed. Both commands accept
`--header` for an external preamble. If you later change the header or title,
update the existing README to match.

If the workspace has no `header.tex`, the script creates it from the built-in
template. Existing headers are used unchanged, so local formatting edits
survive subsequent builds. To use an external header instead:

```bash
python3 pdf-article-translation/scripts/article.py build /path/to/example \
  --header /path/to/custom-header.tex
```

An explicit `--header` uses that file directly; it does not create or replace
the workspace header.

Pandoc builds are performed from the output directory. A header's relative
`input` paths must resolve from there; use absolute paths or copy its assets
into the workspace as appropriate. Rebuilt PDFs preserve content and logical
structure rather than the original page layout.

Run the behavior checks from the repository root (`~/dev/skills`):

```bash
python3 -m unittest discover -s pdf-article-translation/tests -v
```

They exercise actual Poppler/Pandoc commands, edge adjustments, replay of
crops, rejected out-of-bounds changes, source integrity, and formula drift.

Tool references: [Pandoc manual](https://pandoc.org/MANUAL.html) and
[pdftoppm options](https://manpages.debian.org/bookworm/poppler-utils/pdftoppm.1.en.html).
