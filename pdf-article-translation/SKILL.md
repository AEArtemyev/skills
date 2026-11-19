---
name: pdf-article-translation
description: Turn PDF articles into faithful Markdown and Russian translations with figures, record reproducible crops, revise image edges, and build PDFs using Pandoc with a built-in or custom LaTeX header.
---

# PDF article translation

Produce `article.md`, `article.ru.md`, shared `images/figure-NN.png` files,
`image-extraction.md`, a Russian `README.md` with an English article title,
and both compiled PDFs. Build both PDFs as part of the normal workflow;
skip compilation only if the user explicitly asks for Markdown only.
Preserve content, reading order, equations,
tables, captions, footnotes, and references. Preserve logical structure;
PDF pagination and typography can differ.

Use `scripts/article.py` for repeatable operations. Dependencies: Python 3.11+
and Poppler tools; Pandoc for checks, pdflatex for builds, Tesseract for OCR.
Read subcommand `--help` for options. In examples, `tool` is the absolute path
to this script. Reconstruction and translation are the agent's responsibility.

## Extract and reconstruct

1. Work in the current directory unless the user selects another output
   directory. The normal setup is an existing directory containing the input
   PDF. Run `python3 "$tool" prepare input.pdf` there. The script keeps that
   PDF under its existing name and records it in `figures.json`; it does not
   create a `source.pdf` copy. Existing article outputs cause preparation to
   fail rather than overwrite them; resume an existing workspace from its
   manifest instead of preparing it again.
   An explicit output directory remains supported:
   `python3 "$tool" prepare input.pdf output-directory`. If the input is
   outside it, the script copies it there as `source.pdf`.
   Preparation creates extraction evidence in `raw/`, `.gitignore` with
   `*.pdf`, `/raw/`, and `/pages/`, and `.gitattributes` with
   `* text=auto eol=lf`. Keep PDFs and intermediate files out of Git.
   Raw extraction is not finished Markdown.
2. Run `python3 "$tool" page . --page 1` and inspect the
   generated page image. Compare extracted text with rendered pages. Repeat
   for every page used for reconstruction. Page numbers start at 1 and refer
   to physical PDF pages, independent of printed numbering.
3. For scans or unusable text, run `python3 "$tool" ocr .
   --lang eng` for all pages, or add `--page N`. Select appropriate installed
   OCR languages. Correct columns, formulas, subscripts, and references
   against the page images; OCR text alone is insufficient evidence.
4. Write `article.md` in the original language using Pandoc Markdown and
   LaTeX math. Reconstruct headings, paragraphs, tables, footnotes, captions,
   and references. Compare every page's content with the Markdown. Mark
   illegible passages explicitly and report them instead of inventing text.
5. Inspect `raw/pdfimages.txt` for embedded image objects. For a candidate,
   inspect that page's objects with `pdfimages -f N -l N -list input.pdf`
   from the workspace, using the source filename recorded in `figures.json`.
   The `num` column then gives page-local indices.
   Extract the candidate with:

   ```bash
   python3 "$tool" embedded . --id figure-01 --page 1 \
     --index 0 --note 'Embedded image candidate'
   ```

   Match `--id` to the figure's printed number; the embedded image index is
   unrelated to article figure numbering.
   Open the candidate and compare it with the figure on the rendered PDF
   page. Verify all panels, labels, orientation, colors, transparency, and
   boundaries. An embedded object may be a mask, a full-page scan, or only
   part of a figure; vector labels or clipping may change its appearance.
   Use it only if it matches the complete displayed figure. Record the
   comparison in the extraction note when accepting the candidate.
   If it does not match, replace it with a page crop using the same ID:

   ```bash
   python3 "$tool" figure . --id figure-01 --page 1 \
     --box 1344 2340 895 680 --note 'Initial crop'
   ```

   Coordinates are `x y width height` in pixels from the page top left,
   at 300 DPI by default. Account for viewer scaling using the actual page
   image dimensions. Crops capture vector drawings and figures inside scans.
   Inspect every crop against the PDF for clipped labels, missing panels, excess margins,
   and neighboring prose. Keep captions in Markdown and drawing labels in
   the image. For figures spanning pages, register separate crops per part.

6. Use relative links: `![Fig. 1. Caption.](images/figure-01.png)`.
   Use one caption per figure rather than duplicating it as a paragraph.

`figures.json` records each extraction method and its parameters. The generated `image-extraction.md`
contains current exact commands, previews, and crop history. Keep both with
the article. Keep the source PDF locally for future recropping, outside Git.
Update the extraction records through the script. Always recrop
from the source; preserve drawing content rather than painting over it.

## Translate to Russian

Create `article.ru.md` from the complete original Markdown. Translate title,
headings, prose, and captions. Keep terminology consistent. Preserve author
names, references, identifiers, URLs, equations, and image paths. Translate
bibliographic entries only when asked, subject to the character rules below.

## Character rules

Write `article.md` using only ASCII characters (U+0000 through U+007F).
In `article.ru.md` and the generated Russian README, allow only ASCII plus
the Russian letters U+0410 through U+044F, U+0401, and U+0451 (including Yo).
This excludes Greek letters, other Cyrillic alphabets, typographic punctuation,
nonbreaking spaces, and accented Latin characters as literal Unicode.

Use ASCII LaTeX commands for mathematical symbols and accented names,
straight quotes, ordinary spaces, and `--` for a long dash. Preserve meaning
when changing representation. Keep formulas identical in both articles.
These rules apply to final Markdown, not raw extraction or OCR evidence.

Run `python3 "$tool" check .`. It checks local images,
registered crops, heading levels, image order, table counts, and math equality
using Pandoc. It rejects disallowed characters with their file, line, column,
and Unicode code point. Separately verify completeness, translation accuracy, table
contents, and references against the PDF; structural checks cannot prove these.

Continue with the PDF build below. It creates one Russian `README.md` with
the original article's English H1 title, Ubuntu/Debian dependency installation
commands, a file inventory with Russian descriptions, and direct Pandoc commands
for both PDFs. Omit `raw/` and `pages/` from the README inventory. If the source title is
not English, translate only the README heading into English. No separate
README.ru.md is generated. On an existing workspace, update old README
instructions to this format while preserving user notes.
For a Markdown-only request, run `python3 "$tool" readme .`
instead of building. Both commands create a default `header.tex` if absent
and accept `--header PATH`. Existing headers and Git configuration are preserved.
Checking Markdown and building PDFs do not require the original PDF or
intermediate files. Extraction and crop corrections require the source PDF
at its recorded path with the recorded SHA-256; page images are regenerated
when needed. After cloning, restore the source PDF locally before recropping.

## Correct figure edges

Map user feedback to a figure ID. Inspect its original page and current crop,
choose a measured change, then inspect the new result:

```bash
python3 "$tool" adjust . --id figure-01 --left 40 --top -20 \
  --note 'Restore left edge; reduce top margin'
```

Positive values expand an edge, negative values contract it. This moves the
left edge 40 pixels left and top edge 20 pixels down, leaving right and bottom
fixed. `--right` and `--bottom` follow the same rule. Rerun `figure` with the
same ID to replace the rectangle or page. Both Markdown files reuse the same
image filename. Rebuild PDFs after corrections.
For an embedded object, first switch to a page crop with `figure` using
the same ID; the `adjust` command requires page coordinates.

## Build PDFs

The script includes a default pdflatex preamble with Cyrillic support.
On build it creates `header.tex` in the workspace if absent, and uses an
existing workspace header unchanged. The user can edit that file for later
builds. Inspect the active header before diagnosing failures. Resolve
unsupported Unicode deliberately without silently losing content.

```bash
python3 "$tool" build .
```

To use another preamble, add `--header /absolute/path/header.tex`. This uses
that file directly without creating or replacing the workspace header.

Run the build without waiting for a separate compilation request. This
checks both Markdown files and compiles
`article.pdf` and `article.ru.pdf` using `--pdf-engine=pdflatex`. Images resolve
relative to the workspace; relative dependencies inside the header must also
resolve there. Existing generated PDFs are replaced only after each successful
build. Inspect both PDFs for figures, math, missing text, and Cyrillic.
If compilation fails or a dependency is missing, report the exact failure
and remaining work. A normal conversion is complete only when both PDFs
have been built and visually checked. Report a failed build as incomplete.

Report output paths, checks actually passed, and unresolved transcription,
translation, and crop issues. Do not claim fidelity based on exit codes alone.
