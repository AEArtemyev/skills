#!/usr/bin/env python3
"""Reproducible PDF article preparation and figure cropping."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit


DEFAULT_HEADER = r"""% Default preamble for Pandoc and pdflatex.
\usepackage[T2A]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[russian,english]{babel}
\usepackage{cmap}

\usepackage[a4paper,margin=25mm]{geometry}
\setlength{\parindent}{0pt}
\setlength{\parskip}{6pt}

\usepackage{amsmath,amssymb,mathtools,cancel}

\usepackage{graphicx}
\usepackage{grffile}
\usepackage{float}
"""


def run(command, cwd=None):
    result = subprocess.run(
        [str(item) for item in command], cwd=cwd, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "LC_ALL": "C"},
    )
    if result.returncode:
        raise ValueError(f"Command failed: {shlex.join(map(str, command))}\n"
                         f"{result.stderr or result.stdout}")
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    return result.stdout


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def create_git_files(root):
    for name, content in (
        (".gitignore", "/source.pdf\n/article.pdf\n/article.ru.pdf\n"),
        (".gitattributes", "* text=auto eol=lf\n"),
    ):
        try:
            with (root / name).open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
            print(f"Created {root / name}")
        except FileExistsError:
            print(f"Preserved {root / name}")


def crop_command(data, name, figure):
    x, y, width, height = figure["box"]
    return list(map(str, ["pdftoppm", "-f", figure["page"], "-l", figure["page"],
                         "-singlefile", "-r", data["dpi"], "-x", x, "-y", y,
                         "-W", width, "-H", height, "-png", "source.pdf",
                         f"images/{name}"]))


def embedded_commands(name, page, index):
    prefix = f"raw/embedded/page-{page:04d}/image"
    return [
        ["mkdir", "-p", str(Path(prefix).parent)],
        ["pdfimages", "-f", str(page), "-l", str(page), "-png", "source.pdf", prefix],
        ["cp", f"{prefix}-{index:03d}.png", f"images/{name}.png"],
    ]


def save(root, data):
    target = root / "figures.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    lines = ["# Image extraction", "",
             "Generated from figures.json. Run commands from this workspace directory.",
             "Coordinates: x y width height, in pixels from the page top left.",
             f"Resolution: {data['dpi']} DPI. Page numbering starts at 1.",
             f"Source SHA-256: {data['sha256']}", ""]
    for name, figure in sorted(data["figures"].items()):
        if figure.get("method") == "embedded":
            details = f"embedded index: {figure['index']} (page-local, starting at 0)"
            commands = embedded_commands(name, figure["page"], figure["index"])
        else:
            details = f"page crop: {figure['box']}"
            commands = [crop_command(data, name, figure)]
        lines += [f"## {name}", "", f"Page: {figure['page']}; {details}",
                  "", "```bash", *(shlex.join(command) for command in commands),
                  "```", "", f"![{name}](images/{name}.png)", "", "History:", ""]
        for event in figure["history"]:
            details = (f"embedded index {event['index']}" if event.get("method") == "embedded"
                       else f"page crop {event['box']}")
            lines.append(f"- {event['time']}: page {event['page']}, {details}; "
                         f"{json.dumps(event['note'], ensure_ascii=True)}")
        lines.append("")
    (root / "image-extraction.md").write_text("\n".join(lines), encoding="utf-8")


def load(root):
    data = json.loads((root / "figures.json").read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise ValueError("Unsupported figures.json version")
    if digest(root / "source.pdf") != data["sha256"]:
        raise ValueError("source.pdf changed; prepare a new workspace")
    return data


def png_size(path):
    with path.open("rb") as stream:
        header = stream.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Invalid PNG: {path}")
    return struct.unpack(">II", header[16:24])


def page_image(root, data, number):
    if not 1 <= number <= data["page_count"]:
        raise ValueError(f"Page must be between 1 and {data['page_count']}")
    prefix = Path("pages") / f"page-{number:04d}"
    image = root / prefix.with_suffix(".png")
    if not image.exists():
        run(["pdftoppm", "-f", number, "-l", number, "-singlefile", "-r",
             data["dpi"], "-png", "source.pdf", prefix], cwd=root)
    return image


def prepare(args):
    source = args.pdf.resolve(strict=True)
    if args.dpi <= 0:
        raise ValueError("DPI must be positive")
    info = run(["pdfinfo", source])
    match = re.search(r"^Pages:\s+(\d+)\s*$", info, re.MULTILINE)
    if not match:
        raise ValueError("Cannot determine page count from pdfinfo")
    root = args.workspace.resolve()
    root.mkdir(parents=True, exist_ok=False)
    for folder in ("raw", "pages", "images"):
        (root / folder).mkdir()
    create_git_files(root)
    shutil.copyfile(source, root / "source.pdf")
    (root / "raw/pdfinfo.txt").write_text(info, encoding="utf-8")
    data = dict(version=1, dpi=args.dpi, page_count=int(match[1]),
                sha256=digest(root / "source.pdf"), figures={})
    save(root, data)
    for mode in ("layout", "raw"):
        run(["pdftotext", f"-{mode}", "-enc", "UTF-8", "source.pdf",
             f"raw/{mode}.txt"], cwd=root)
    images = run(["pdfimages", "-list", "source.pdf"], cwd=root)
    (root / "raw/pdfimages.txt").write_text(images, encoding="utf-8")
    print(root)
    print("Raw text extracted. Compare with page images before reconstruction.")
    if not (root / "raw/layout.txt").read_text(encoding="utf-8").strip():
        print("No text extracted; OCR is required.", file=sys.stderr)


def extract_figure(root, data, name, page, box, note):
    if not re.fullmatch(r"figure-[0-9]{2,}", name):
        raise ValueError("Use a stable ID such as figure-01")
    width, height = png_size(page_image(root, data, page))
    x, y, w, h = box
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > width or y + h > height:
        raise ValueError(f"Box {box} lies outside page size {width} x {height}")
    figure = {"method": "crop", "page": page, "box": box}
    command = crop_command(data, name, figure)
    # A failed render leaves the previous image intact.
    with tempfile.TemporaryDirectory(dir=root / "images") as temporary:
        prefix = Path(temporary) / name
        run(command[:-1] + [prefix], cwd=root)
        generated = prefix.with_suffix(".png")
        if png_size(generated) != (w, h):
            raise ValueError("Rendered crop size differs from requested box")
        generated.replace(root / "images" / f"{name}.png")
    record_figure(root, data, name, figure, note)


def record_figure(root, data, name, figure, note):
    event = {**figure, "time": datetime.now(timezone.utc).isoformat(), "note": note}
    figure["history"] = data["figures"].get(name, {}).get("history", []) + [event]
    data["figures"][name] = figure
    save(root, data)
    print(root / "images" / f"{name}.png")


def extract_embedded(root, data, name, page, index, note):
    if not re.fullmatch(r"figure-[0-9]{2,}", name):
        raise ValueError("Use a stable ID such as figure-01")
    if not 1 <= page <= data["page_count"] or index < 0:
        raise ValueError("Use a valid page and a nonnegative page-local image index")
    commands = embedded_commands(name, page, index)
    (root / commands[0][-1]).mkdir(parents=True, exist_ok=True)
    run(commands[1], cwd=root)
    source = root / commands[2][1]
    if not source.is_file():
        raise ValueError(f"No embedded PNG at page {page}, index {index}; inspect raw/embedded")
    png_size(source)
    with tempfile.TemporaryDirectory(dir=root / "images") as temporary:
        target = Path(temporary) / f"{name}.png"
        shutil.copyfile(source, target)
        target.replace(root / "images" / f"{name}.png")
    record_figure(root, data, name,
                  {"method": "embedded", "page": page, "index": index}, note)
    print("Compare this object with the rendered PDF figure before using it.")


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def structure(root, filename):
    tree = json.loads(run(["pandoc", "--from=markdown", "--to=json", filename], cwd=root))
    if not tree["blocks"]:
        raise ValueError(f"{filename}: article is empty")
    nodes = list(walk(tree["blocks"]))
    images = [node["c"][2][0] for node in nodes if node.get("t") == "Image"]
    for target in images:
        parsed = urlsplit(target)
        relative = Path(unquote(parsed.path))
        path = (root / relative).resolve()
        if (parsed.scheme or parsed.netloc or relative.is_absolute()
                or not path.is_relative_to(root) or not path.is_file()):
            raise ValueError(f"{filename}: expected existing local relative image: {target}")
    return {
        "images": images,
        "math": [node["c"] for node in nodes if node.get("t") == "Math"],
        "headings": [node["c"][0] for node in nodes if node.get("t") == "Header"],
        "tables": sum(node.get("t") == "Table" for node in nodes),
    }


def validate_characters(text, filename, russian=False):
    for line_number, line in enumerate(text.split("\n"), 1):
        for column, character in enumerate(line, 1):
            code = ord(character)
            if code <= 0x7F:
                continue
            if russian and (0x0410 <= code <= 0x044F or code in (0x0401, 0x0451)):
                continue
            allowed = "ASCII and Russian letters" if russian else "ASCII"
            raise ValueError(f"{filename}:{line_number}:{column}: "
                             f"U+{code:04X} {character!r} is not allowed; use {allowed}")


def check(root, data):
    for filename, russian in (("article.md", False), ("article.ru.md", True),
                              ("README.md", True)):
        path = root / filename
        if filename == "README.md" and not path.exists():
            continue
        validate_characters(path.read_text(encoding="utf-8"), filename, russian)
    source = structure(root, "article.md")
    translated = structure(root, "article.ru.md")
    for key in source:
        if source[key] != translated[key]:
            raise ValueError(f"Original and translation differ in {key}")
    expected = {f"images/{name}.png" for name in data["figures"]}
    if set(source["images"]) != expected:
        raise ValueError("Article image paths must match all registered figures")
    print(f"Structural checks passed: {len(source['images'])} images, "
          f"{len(source['math'])} math expressions, {source['tables']} tables.")
    print("Completeness and translation accuracy require a separate visual review.")


def resolve_header(root, header=None):
    if header is None:
        header = root / "header.tex"
        try:
            with header.open("x", encoding="utf-8") as stream:
                stream.write(DEFAULT_HEADER)
            print(f"Created {header}")
        except FileExistsError:
            pass  # Preserve local edits and use the existing header.
    return header.resolve(strict=True)


def write_readme(root, header=None):
    create_git_files(root)
    target = root / "README.md"
    if target.exists():
        print(f"Preserved {target}")
        return
    text = (root / "article.md").read_text(encoding="utf-8")
    title = re.search(r"^#[ \t]+([^\n]+)$", text, re.MULTILINE)
    if not title:
        raise ValueError("article.md: expected an English H1 article title for README.md")
    validate_characters(title[1], "README.md title")
    header = resolve_header(root, header)
    if header.is_relative_to(root):
        header = header.relative_to(root)
    commands = [shlex.join(["pandoc", f"{name}.md", "--pdf-engine=pdflatex",
                            "-H", str(header), "-o", f"{name}.pdf"])
                for name in ("article", "article.ru")]
    template = Path(__file__).resolve().parents[1] / "assets/README.md.template"
    content = template.read_text(encoding="utf-8").format(
        title=title[1], commands="\n".join(commands))
    validate_characters(content, "README.md", russian=True)
    with target.open("x", encoding="utf-8") as stream:
        stream.write(content)
    print(f"Created {target}")


def build(root, data, header=None):
    check(root, data)
    header = resolve_header(root, header)
    write_readme(root, header)
    for filename in ("article", "article.ru"):
        with tempfile.TemporaryDirectory(dir=root) as temporary:
            output = Path(temporary) / f"{filename}.pdf"
            run(["pandoc", f"{filename}.md", "--from=markdown", "--standalone",
                 "--pdf-engine=pdflatex", "--include-in-header", header,
                 "--output", output], cwd=root)
            info = run(["pdfinfo", output])
            output.replace(root / f"{filename}.pdf")
        print(root / f"{filename}.pdf")
        print(next(line for line in info.splitlines() if line.startswith("Pages:")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("prepare", help="Create a new article workspace")
    command.add_argument("pdf", type=Path)
    command.add_argument("workspace", type=Path)
    command.add_argument("--dpi", type=int, default=300)
    for name, help_text in (("page", "Render a full page"),
                            ("ocr", "OCR selected or all pages"),
                            ("figure", "Extract or replace a figure rectangle"),
                            ("embedded", "Extract an embedded image candidate using pdfimages"),
                            ("adjust", "Expand (+) or contract (-) figure edges"),
                            ("check", "Compare Markdown structure and figure links"),
                            ("readme", "Create Russian README.md with PDF installation and build commands"),
                            ("build", "Build both PDFs with pdflatex")):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("workspace", type=Path)
        if name in ("page", "ocr", "figure", "embedded"):
            command.add_argument("--page", type=int, required=name != "ocr")
        if name == "ocr":
            command.add_argument("--lang", required=True, help="Tesseract language, e.g. eng")
        if name in ("figure", "adjust", "embedded"):
            command.add_argument("--id", required=True)
            command.add_argument("--note", required=True)
        if name == "figure":
            command.add_argument("--box", type=int, nargs=4, required=True,
                                 metavar=("X", "Y", "WIDTH", "HEIGHT"))
        if name == "embedded":
            command.add_argument("--index", type=int, required=True,
                                 help="Image index within the selected page, starting at 0")
        if name == "adjust":
            for edge in ("left", "top", "right", "bottom"):
                command.add_argument(f"--{edge}", type=int, default=0)
        if name in ("build", "readme"):
            command.add_argument("--header", type=Path,
                                 help="Custom preamble; default: workspace/header.tex "
                                      "(created from the built-in template if absent)")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            prepare(args)
            return
        root = args.workspace.resolve(strict=True)
        data = load(root)
        if args.command == "page":
            print(page_image(root, data, args.page))
        elif args.command == "ocr":
            pages = [args.page] if args.page is not None else range(1, data["page_count"] + 1)
            for number in pages:
                image = page_image(root, data, number)
                text = run(["tesseract", image, "stdout", "-l", args.lang, "--psm", "3"])
                target = root / "raw" / f"page-{number:04d}.ocr.txt"
                target.write_text(text, encoding="utf-8")
                print(target)
        elif args.command == "figure":
            extract_figure(root, data, args.id, args.page, args.box, args.note)
        elif args.command == "embedded":
            extract_embedded(root, data, args.id, args.page, args.index, args.note)
        elif args.command == "adjust":
            figure = data["figures"].get(args.id)
            if figure is None:
                raise ValueError(f"Unknown figure: {args.id}")
            if figure.get("method") == "embedded":
                raise ValueError("Embedded image has no page crop; use figure with the same ID, "
                                 "--page and --box to switch to a page crop")
            if not any((args.left, args.top, args.right, args.bottom)):
                raise ValueError("Specify a nonzero edge adjustment")
            x, y, w, h = figure["box"]
            box = [x - args.left, y - args.top,
                   w + args.left + args.right, h + args.top + args.bottom]
            extract_figure(root, data, args.id, figure["page"], box, args.note)
        elif args.command == "check":
            check(root, data)
        elif args.command == "readme":
            write_readme(root, args.header)
        elif args.command == "build":
            build(root, data, args.header)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
