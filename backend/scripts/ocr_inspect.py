"""Run the reader on any pdf or image and print its tokens.

    python scripts/ocr_inspect.py <path>              # auto: text layer or OCR
    python scripts/ocr_inspect.py <path> --force-ocr  # force OCR

Prints the method and every token with confidence, source, and box.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from realdoor.extraction.readers import extract_document  # noqa: E402


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit("usage: python scripts/ocr_inspect.py <path> [--force-ocr]")
    path = Path(args[0])
    if not path.exists():
        sys.exit(f"file not found: {path}")
    force = "ocr" if "--force-ocr" in sys.argv else None

    doc = extract_document(path, force_method=force)
    print(f"file:   {path.name}")
    print(f"method: {doc.method}   page_size_pts: {doc.page_size_points}   tokens: {len(doc.tokens)}")
    if doc.tokens:
        confs = [t.confidence for t in doc.tokens]
        print(f"confidence: min={min(confs):.2f}  mean={sum(confs) / len(confs):.2f}  max={max(confs):.2f}")
    print("-" * 72)
    print(f"{'conf':>5}  {'source':<10} {'bbox (x0,y0,x1,y1)':<30} text")
    for t in doc.tokens:
        box = "(" + ", ".join(f"{v:.0f}" for v in t.bbox) + ")"
        print(f"{t.confidence:>5.2f}  {t.source:<10} {box:<30} {t.text}")


if __name__ == "__main__":
    main()
