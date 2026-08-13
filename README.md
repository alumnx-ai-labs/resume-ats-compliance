# Canva Resume ATS Checker

Parses resume PDFs and checks whether they are likely to survive an ATS
(Applicant Tracking System) text-extraction pass — the hypothesis being
tested is: **resumes designed in Canva are generally not ATS-compliant.**

## Setup

```
pip install -r requirements.txt
```

## Usage

1. Drop one or more resume PDFs into `input/`.
2. Run:
   ```
   python parse_resume.py
   ```
3. For each PDF, two files land in `output/`:
   - `<name>_extracted.txt` — the raw text an ATS would actually see
     (extracted with `pypdf`, the same kind of naive linear extractor
     many ATS products use under the hood).
   - `<name>_ats_report.txt` — a heuristic ATS-compliance report with a
     score out of 100 and a verdict.
4. If you process more than one PDF, `output/summary.txt` ranks them
   side by side.

## How to actually validate the hypothesis

A single Canva resume scoring low doesn't prove the hypothesis — you need
a comparison:

1. Export a resume made in Canva as PDF → drop into `input/`.
2. Export the *same content* from a plain, single-column tool (Word,
   Google Docs, LaTeX, or a plain-text-based template) → drop into `input/`.
3. Run the script. Compare the two reports and `summary.txt`.

If the Canva version consistently scores lower and the report calls out
things like multi-column layout, icon-based contact info, or glued words,
that's concrete evidence for the hypothesis — not just an assumption.

## What the report checks

- **Contact info extraction** — can an email/phone be found in the plain
  extracted text, or is it likely rendered as an icon/image?
- **Section headers** — are standard headers like "Experience",
  "Education", "Skills" present as real text an ATS can key off of?
- **Word integrity** — are words getting glued together (a symptom of
  text boxes/columns merging without spaces during linear extraction)?
- **Embedded images/icons** — Canva templates lean heavily on icon
  graphics (phone, email, LinkedIn icons) that carry zero extractable
  text.
- **Extraction consistency** — do a naive extractor (`pypdf`) and a
  layout-aware extractor (`pdfplumber`) roughly agree on how much text
  exists? Large disagreement means real-world ATS products (which use a
  patchwork of extraction engines) will behave inconsistently on this file.
- **Multi-column layout** — Canva templates commonly use a sidebar +
  main-content two-column design, which most ATS parsers read left-to-right
  per line, interleaving unrelated content from both columns.

## Notes

This is a heuristic approximation, not a certified ATS testing tool —
no two real ATS products (Workday, Greenhouse, Taleo, etc.) parse PDFs
identically. The checks here target the specific layout patterns Canva
templates are known for, so a low score is a strong signal, not a
guarantee, and a high score doesn't guarantee every real ATS will parse
the file perfectly either.
