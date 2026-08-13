"""Parse every PDF in input/, dump extracted text to output/, and run
ATS-compliance heuristics on each one so you can compare a Canva-made
resume against a plain-text/Word/LaTeX control resume.

Usage:
    python parse_resume.py
"""

import sys
from pathlib import Path

import pdfplumber
from pypdf import PdfReader

import ats_checks

INPUT_DIR = Path(__file__).parent / "input"
OUTPUT_DIR = Path(__file__).parent / "output"


def extract_naive_text(pdf_path):
    reader = PdfReader(str(pdf_path))
    pages_text = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages_text)


def extract_pdfplumber_text(pdf):
    pages_text = [page.extract_text() or "" for page in pdf.pages]
    return "\n".join(pages_text)


def process_pdf(pdf_path):
    print(f"Processing {pdf_path.name} ...")

    naive_text = extract_naive_text(pdf_path)
    txt_out = OUTPUT_DIR / f"{pdf_path.stem}_extracted.txt"
    txt_out.write_text(naive_text, encoding="utf-8")
    print(f"  -> extracted text saved to {txt_out.relative_to(Path(__file__).parent)}")

    with pdfplumber.open(str(pdf_path)) as pdf:
        pdfplumber_text = extract_pdfplumber_text(pdf)
        results = ats_checks.run_all_checks(naive_text, pdf, pdfplumber_text)

    report = ats_checks.format_report(pdf_path.name, results)
    report_out = OUTPUT_DIR / f"{pdf_path.stem}_ats_report.txt"
    report_out.write_text(report, encoding="utf-8")
    print(f"  -> ATS report saved to {report_out.relative_to(Path(__file__).parent)}")
    print(f"  -> Score: {results['score']}/100 ({results['verdict']})")

    return pdf_path.name, results["score"], results["verdict"]


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    pdf_files = sorted(INPUT_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in {INPUT_DIR}. Place resume PDFs there and re-run.")
        sys.exit(1)

    summary_rows = []
    for pdf_path in pdf_files:
        summary_rows.append(process_pdf(pdf_path))

    if len(summary_rows) > 1:
        summary_lines = ["ATS Compliance Summary", "=" * 23, ""]
        for name, score, verdict in sorted(summary_rows, key=lambda r: -r[1]):
            summary_lines.append(f"{name:<40} {score:>5}/100   {verdict}")
        summary_path = OUTPUT_DIR / "summary.txt"
        summary_path.write_text("\n".join(summary_lines), encoding="utf-8")
        print(f"\nComparison summary saved to {summary_path.relative_to(Path(__file__).parent)}")


if __name__ == "__main__":
    main()
