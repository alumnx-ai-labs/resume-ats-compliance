"""Heuristic checks that approximate how a real ATS text-extraction engine
would treat a resume PDF. None of this calls out to an actual ATS product —
it re-creates the same class of naive, linear PDF-to-text extraction that
most ATS parsers use, then flags the layout patterns known to break it.
"""

import re
from collections import Counter

SECTION_HEADERS = [
    "experience", "work experience", "professional experience",
    "education", "skills", "technical skills", "summary",
    "objective", "projects", "certifications", "certificates",
    "achievements", "awards", "publications", "references",
    "contact", "languages", "profile",
]

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(\+?\d{1,3}[\s.-]?)?(\(?\d{2,4}\)?[\s.-]?){2,4}\d{3,4}")


def check_contact_info(naive_text):
    email_found = bool(EMAIL_RE.search(naive_text))
    phone_found = bool(PHONE_RE.search(naive_text))
    return {
        "email_found": email_found,
        "phone_found": phone_found,
        "pass": email_found and phone_found,
    }


def check_section_headers(naive_text):
    lines = [l.strip().lower() for l in naive_text.splitlines() if l.strip()]
    found = sorted({h for h in SECTION_HEADERS if any(h == l or h in l and len(l) < len(h) + 15 for l in lines)})
    return {
        "headers_found": found,
        "count": len(found),
        "pass": len(found) >= 3,
    }


def check_glued_words(naive_text):
    words = re.findall(r"[A-Za-z]+", naive_text)
    if not words:
        return {"avg_word_length": 0, "suspicious_long_words": 0,
                 "single_char_word_pct": 0, "pass": False}
    long_words = [w for w in words if len(w) >= 18]
    single_char_words = [w for w in words if len(w) == 1]
    avg_len = sum(len(w) for w in words) / len(words)
    single_char_pct = len(single_char_words) / len(words)

    is_glued = len(long_words) >= 3 or avg_len >= 9
    is_fragmented = single_char_pct > 0.3

    return {
        "avg_word_length": round(avg_len, 2),
        "suspicious_long_words": len(long_words),
        "sample_long_words": long_words[:5],
        "single_char_word_pct": round(single_char_pct, 2),
        "is_fragmented": is_fragmented,
        "pass": not is_glued and not is_fragmented,
    }


def check_multi_column_layout(page_words, page_width):
    if not page_words or page_width == 0 or len(page_words) < 2:
        return {"is_multi_column": False, "left_cluster_pct": None, "right_cluster_pct": None}

    xs = sorted(w["x0"] for w in page_words)
    gaps = [(xs[i + 1] - xs[i], xs[i]) for i in range(len(xs) - 1)]
    largest_gap, boundary = max(gaps, key=lambda g: g[0])

    total = len(page_words)
    if largest_gap < page_width * 0.08:
        return {"is_multi_column": False, "left_cluster_pct": None, "right_cluster_pct": None}

    left_count = sum(1 for x in xs if x <= boundary)
    right_count = total - left_count
    left_pct = left_count / total
    right_pct = right_count / total

    is_multi_column = left_pct > 0.15 and right_pct > 0.15
    return {
        "is_multi_column": is_multi_column,
        "left_cluster_pct": round(left_pct, 2),
        "right_cluster_pct": round(right_pct, 2),
    }


def check_embedded_images(pdf):
    per_page_counts = [len(page.images) for page in pdf.pages]
    total = sum(per_page_counts)
    return {
        "total_images": total,
        "per_page": per_page_counts,
        "pass": total == 0,
    }


def check_extraction_consistency(naive_text, pdfplumber_text):
    naive_count = len(re.sub(r"\s+", "", naive_text))
    plumber_count = len(re.sub(r"\s+", "", pdfplumber_text))
    if plumber_count == 0:
        ratio = 0.0
    else:
        ratio = naive_count / plumber_count
    return {
        "naive_char_count": naive_count,
        "pdfplumber_char_count": plumber_count,
        "ratio": round(ratio, 2),
        "pass": 0.85 <= ratio <= 1.15,
    }


def run_all_checks(naive_text, pdf, pdfplumber_text):
    multi_column_pages = []
    for i, page in enumerate(pdf.pages):
        words = page.extract_words()
        result = check_multi_column_layout(words, page.width)
        if result["is_multi_column"]:
            multi_column_pages.append({"page": i + 1, **result})

    checks = {
        "contact_info": check_contact_info(naive_text),
        "section_headers": check_section_headers(naive_text),
        "glued_words": check_glued_words(naive_text),
        "embedded_images": check_embedded_images(pdf),
        "extraction_consistency": check_extraction_consistency(naive_text, pdfplumber_text),
        "multi_column_layout": {
            "pages_affected": multi_column_pages,
            "pass": len(multi_column_pages) == 0,
        },
    }

    weights = {
        "contact_info": 25,
        "section_headers": 20,
        "glued_words": 15,
        "embedded_images": 10,
        "extraction_consistency": 15,
        "multi_column_layout": 15,
    }

    score = sum(weights[k] for k, v in checks.items() if v.get("pass"))
    if score >= 85:
        verdict = "Likely ATS-friendly"
    elif score >= 55:
        verdict = "Potential ATS issues detected"
    else:
        verdict = "High ATS risk"

    return {"score": score, "verdict": verdict, "checks": checks}


def format_report(filename, results):
    lines = []
    lines.append(f"ATS Compliance Report: {filename}")
    lines.append("=" * (24 + len(filename)))
    lines.append(f"Score: {results['score']} / 100")
    lines.append(f"Verdict: {results['verdict']}")
    lines.append("")

    c = results["checks"]

    lines.append("[Contact Info Extraction]")
    lines.append(f"  Email found: {c['contact_info']['email_found']}")
    lines.append(f"  Phone found: {c['contact_info']['phone_found']}")
    if not c["contact_info"]["pass"]:
        lines.append("  -> Risk: contact details may be rendered as icons/images rather than "
                      "selectable text, which most ATS parsers cannot read.")
    lines.append("")

    lines.append("[Section Headers]")
    lines.append(f"  Found: {c['section_headers']['headers_found']}")
    if not c["section_headers"]["pass"]:
        lines.append("  -> Risk: fewer than 3 standard section headers detected. ATS parsers "
                      "often key on headers like 'Experience' / 'Education' / 'Skills' to bucket content.")
    lines.append("")

    lines.append("[Word Integrity]")
    lines.append(f"  Avg word length: {c['glued_words']['avg_word_length']}")
    lines.append(f"  Suspicious long/glued tokens: {c['glued_words']['suspicious_long_words']}")
    if c["glued_words"]["suspicious_long_words"]:
        lines.append(f"  Examples: {c['glued_words'].get('sample_long_words')}")
    lines.append(f"  Single-character tokens: {c['glued_words']['single_char_word_pct']*100:.0f}% of all words")
    if c["glued_words"].get("is_fragmented"):
        lines.append("  -> Risk: text is being extracted almost letter-by-letter (e.g. 's r i p a d a' "
                      "instead of 'sripada'). This happens when the PDF's embedded/subset font stores each "
                      "glyph with individual positioning that extractors misread as word-breaking spaces. "
                      "Exact keyword matches on skills/tech-stack terms will fail completely against this text.")
    elif not c["glued_words"]["pass"]:
        lines.append("  -> Risk: text columns/text-boxes are likely merging without spaces "
                      "when read linearly, corrupting words and keyword matching.")
    lines.append("")

    lines.append("[Embedded Images / Icons]")
    lines.append(f"  Total images detected: {c['embedded_images']['total_images']}")
    lines.append(f"  Per page: {c['embedded_images']['per_page']}")
    if not c["embedded_images"]["pass"]:
        lines.append("  -> Risk: icons/photos frequently used in Canva templates for contact "
                      "info or section markers carry no extractable text.")
    lines.append("")

    lines.append("[Extraction Consistency]")
    lines.append(f"  pypdf extractor char count: {c['extraction_consistency']['naive_char_count']}")
    lines.append(f"  pdfplumber extractor char count: {c['extraction_consistency']['pdfplumber_char_count']}")
    lines.append(f"  Ratio: {c['extraction_consistency']['ratio']}")
    if not c["extraction_consistency"]["pass"]:
        lines.append("  -> Risk: two different extraction engines disagree significantly on "
                      "content volume, meaning results will vary unpredictably across real ATS products.")
    lines.append("")

    lines.append("[Multi-column / Layout]")
    if c["multi_column_layout"]["pages_affected"]:
        for p in c["multi_column_layout"]["pages_affected"]:
            lines.append(f"  Page {p['page']}: left={p['left_cluster_pct']*100:.0f}% "
                          f"right={p['right_cluster_pct']*100:.0f}% of words")
        lines.append("  -> Risk: multi-column layout (common in Canva templates) causes most "
                      "linear text extractors to interleave lines from both columns, scrambling reading order.")
    else:
        lines.append("  No multi-column layout detected.")
    lines.append("")

    return "\n".join(lines)
