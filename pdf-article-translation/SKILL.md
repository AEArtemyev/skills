---
name: pdf-article-translation
description: Turn PDF articles into faithful Markdown and Russian translations with figures, record reproducible crops, revise image edges, and build PDFs using Pandoc with a built-in or custom LaTeX header.
---

# PDF article translation

Produce `article.md`, `article.ru.md`, shared `images/figure-NN.png` files,
and `image-extraction.md`. Preserve content, reading order, equations,
tables, captions, footnotes, and references. Preserve logical structure;
PDF pagination and typography can differ.

Use `scripts/article.py` for repeatable operations. Dependencies: Python 3.11+
and Poppler tools; Pandoc for checks, pdflatex for builds, Tesseract for OCR.
Read subcommand `--help` for options. In examples, `tool` is the absolute path
to this script. Reconstruction and translation are the agent's responsibility.

## Extract and reconstruct

1. Run `python3 "$tool" prepare input.pdf output-directory`. The directory
   must be new. This copies the PDF and extracts evidence into `raw/`.
   Raw extraction is not finished Markdown.
2. Run `python3 "$tool" page output-directory --page 1` and inspect the
   generated page image. Compare extracted text with rendered pages. Repeat
   for every page used for reconstruction. Page numbers start at 1 and refer
   to physical PDF pages, independent of printed numbering.
3. For scans or unusable text, run `python3 "$tool" ocr output-directory
--lang eng` for all pages, or add `--page N`. Select appropriate installed
   OCR languages. Correct columns, formulas, subscripts, and references
   against the page images; OCR text alone is insufficient evidence.
4. Write `article.md` in the original language using Pandoc Markdown and
   LaTeX math. Reconstruct headings, paragraphs, tables, footnotes, captions,
   and references. Compare every page's content with the Markdown. Mark
   illegible passages explicitly and report them instead of inventing text.
5. Select each figure's rectangle on the full page at the workspace DPI:

   ```bash
   python3 "$tool" figure output-directory --id figure-01 --page 1 \
     --box 1344 2340 895 680 --note 'Initial crop'
   ```

   Coordinates are `x y width height` in pixels from the page top left,
   at 300 DPI by default. Account for viewer scaling using the actual page
   image dimensions. Crops capture vector drawings and figures inside scans.
   Inspect every crop for clipped labels, missing panels, excess margins,
   and neighboring prose. Keep captions in Markdown and drawing labels in
   the image. For figures spanning pages, register separate crops per part.

6. Use relative links: `![Fig. 1. Caption.](images/figure-01.png)`.
   Use one caption per figure rather than duplicating it as a paragraph.

`figures.json` records coordinates. The generated `image-extraction.md`
contains current exact commands, previews, and crop history. Keep both with
source.pdf and the article. Update them through the script. Always recrop
from the source; preserve drawing content rather than painting over it.

## Translate to Russian

Create `article.ru.md` from the complete original Markdown. Translate title,
headings, prose, and captions. Keep terminology consistent. Preserve author
names, references, identifiers, URLs, equations, and image paths. Translate
bibliographic entries only when asked. Write the translation in UTF-8 Russian;
ASCII-only repository rules apply to skill sources, not these output artifacts.

Run `python3 "$tool" check output-directory`. It checks local images,
registered crops, heading levels, image order, table counts, and math equality
using Pandoc. Separately verify completeness, translation accuracy, table
contents, and references against the PDF; structural checks cannot prove these.

## Correct figure edges

Map user feedback to a figure ID. Inspect its original page and current crop,
choose a measured change, then inspect the new result:

```bash
python3 "$tool" adjust output-directory --id figure-01 --left 40 --top -20 \
  --note 'Restore left edge; reduce top margin'
```

Positive values expand an edge, negative values contract it. This moves the
left edge 40 pixels left and top edge 20 pixels down, leaving right and bottom
fixed. `--right` and `--bottom` follow the same rule. Rerun `figure` with the
same ID to replace the rectangle or page. Both Markdown files reuse the same
image filename. Rebuild PDFs after corrections.

## Build PDFs

The script includes a default pdflatex preamble with Cyrillic support.
On build it creates `header.tex` in the workspace if absent, and uses an
existing workspace header unchanged. The user can edit that file for later
builds. Inspect the active header before diagnosing failures. Resolve
unsupported Unicode deliberately without silently losing content.

```bash
python3 "$tool" build output-directory
```

To use another preamble, add `--header /absolute/path/header.tex`. This uses
that file directly without creating or replacing the workspace header.

Build only when requested. This checks both Markdown files and compiles
`article.pdf` and `article.ru.pdf` using `--pdf-engine=pdflatex`. Images resolve
relative to the workspace; relative dependencies inside the header must also
resolve there. Existing generated PDFs are replaced only after each successful
build. Inspect both PDFs for figures, math, missing text, and Cyrillic.

Report output paths, checks actually passed, and unresolved transcription,
translation, and crop issues. Do not claim fidelity based on exit codes alone.
