#!/usr/bin/env python3
import argparse
import sys
import time
import shutil
import subprocess
from pathlib import Path
import platform

os = platform.system()

if os == "Darwin":  # macOS
    DOWNLOADS = Path("/Users/gerard/Downloads")
    DEST = Path("/Users/gerard/Downloads/papers_mess")
elif os == "Linux":
    DOWNLOADS = Path("/home/gerard/Downloads")
    DEST = Path("/home/gerard/Downloads/papers_mess")
else:
    raise NotImplementedError("Unsupported operating system")

HOURS = 3


def _run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    return result.stdout.strip()


def get_pdf_title(path: Path) -> str:
    # 1. Spotlight metadata (fastest, no extra deps)
    try:
        title = _run(["mdls", "-name", "kMDItemTitle", "-raw", str(path)])
        if title and title != "(null)":
            return title
    except Exception:
        pass

    # 2. PDF internal /Title field via pypdf (pip install pypdf)
    try:
        from pypdf import PdfReader
        meta = PdfReader(str(path)).metadata
        title = (meta.title or "").strip() if meta else ""
        if title:
            return title
    except Exception:
        pass

    # 3. PDF internal /Title field via pdfinfo (brew install poppler)
    try:
        for line in _run(["pdfinfo", str(path)]).splitlines():
            if line.startswith("Title:"):
                title = line.split(":", 1)[1].strip()
                if title:
                    return title
    except Exception:
        pass

    # 4. First non-empty text line via pdftotext (brew install poppler)
    try:
        text = _run(["pdftotext", str(path), "-", "-l", "1"])
        for line in text.splitlines():
            line = line.strip()
            if len(line) > 4:
                return line
    except Exception:
        pass

    return path.stem


def is_scientific_paper(path: Path) -> bool:
    # Extract text from first 2 pages and look for academic paper signals
    try:
        text = _run(["pdftotext", str(path), "-", "-l", "2"]).lower()
    except Exception:
        return False

    signals = [
        "abstract",
        "introduction",
        "doi",
        "arxiv",
        "references",
        "keywords",
        "university",
        "institute",
        "department",
        "et al",
        "journal",
        "proceedings",
        "preprint",
        "correspondence",
    ]
    # Require at least 3 distinct signals to reduce false positives
    hits = sum(1 for s in signals if s in text)
    return hits >= 3


parser = argparse.ArgumentParser(description="Find and move scientific PDFs from Downloads.")
parser.add_argument("--all", action="store_true", help="Scan all PDFs regardless of age (no time window)")
args = parser.parse_args()

cutoff = None if args.all else time.time() - HOURS * 3600

all_pdfs: list[tuple[float, Path]] = []
for f in DOWNLOADS.iterdir():
    if f.suffix.lower() == ".pdf" and f.is_file():
        stat = f.stat()
        added = getattr(stat, "st_birthtime", stat.st_mtime)
        if cutoff is None or added >= cutoff:
            all_pdfs.append((added, f))

all_pdfs.sort(reverse=True)

if not all_pdfs:
    if args.all:
        print("No PDFs found in Downloads.")
    else:
        print(f"No PDFs added in the last {HOURS} hours.")
    sys.exit(0)

recent_pdfs = all_pdfs

scope = "all" if args.all else f"last {HOURS}h"
print(f"Scanning {len(recent_pdfs)} PDF(s) ({scope}) for scientific papers...", flush=True)
recent_pdfs = [(ts, p) for ts, p in recent_pdfs if is_scientific_paper(p)]

if not recent_pdfs:
    print("None of the recent PDFs look like scientific papers.")
    sys.exit(0)

print(f"Found {len(recent_pdfs)} scientific paper(s):\n")
for _, pdf in recent_pdfs:
    title = get_pdf_title(pdf)
    if title != pdf.stem:
        print(f"  • {title}")
        print(f"    ({pdf.name})")
    else:
        print(f"  • {pdf.name}")

print(f"\nMove all to {DEST}? [y/N] ", end="", flush=True)
try:
    answer = input().strip().lower()
except (EOFError, KeyboardInterrupt):
    print("\nAborted.")
    sys.exit(0)

if answer != "y":
    print("No files moved.")
    sys.exit(0)

DEST.mkdir(exist_ok=True)
for _, pdf in recent_pdfs:
    dest_path = DEST / pdf.name
    if dest_path.exists():
        print(f"  Skipped (already exists): {pdf.name}")
    else:
        shutil.move(str(pdf), str(dest_path))
        print(f"  Moved: {pdf.name}")

print("Done.")
