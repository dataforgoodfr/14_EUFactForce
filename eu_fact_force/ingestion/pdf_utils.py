import re

import fitz


def extract_text_by_blocks(pdf_bytes: bytes) -> str:
    """Extract text from the first 3 pages of a PDF, sorted by visual reading order."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = ""
    for page in doc[:3]:
        blocks = page.get_text("blocks")
        blocks.sort(key=lambda b: (round(b[1] / 20), b[0]))
        for block in blocks:
            text += block[4] + "\n"
    return text


def extract_doi_from_pdf(text: str) -> str | None:
    """Extract a DOI from PDF text. Returns the DOI string or None."""
    match = re.search(r'(?:doi[:\s]+)?(?:https?://)?(?:dx\.)?doi\.org/(10\.\S+)', text, re.IGNORECASE)
    if match:
        return match.group(1).rstrip(".,;)")

    match = re.search(r'10\.\d{4,}/\S+', text)
    if match:
        return match.group(0).rstrip(".,;)")

    return None


def extract_title_from_pdf(text: str) -> str | None:
    """Extract the title from the first few lines of the PDF."""
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if not lines:
        return None

    for line in lines[:10]:
        if any(kw in line.lower() for kw in ["journal", "doi:", "http", "vol.", "issn", "received:", "accepted:", "copyright"]):
            continue
        if 3 <= len(line.split()) <= 40 and len(line) < 450:
            return line
    return None


def extract_abstract_from_pdf(text: str) -> str | None:
    """Extract abstract section from PDF text."""
    abstract_pattern = r'(?:abstract|summary)\s*[:]*\s*(.+?)(?=(?:introduction|keywords|1\.\s|methods|methodology|related work|background)|\Z)'
    match = re.search(abstract_pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        abstract_text = re.sub(r'\s+', ' ', match.group(1).strip())[:500]
        return abstract_text if len(abstract_text) > 20 else None
    return None


def extract_authors_from_pdf(text: str) -> list[dict]:
    """Extract author names from the typical author line in scientific papers."""
    authors = []

    def clean_name(name: str) -> str:
        return re.sub(r'[\d\*†‡§]+', '', name).strip()

    lines = text.split('\n')[:50]

    for line in lines:
        line = line.strip()
        if len(line) > 150 or len(line) < 5:
            continue
        if not re.search(r'\band\b|,', line):
            continue
        if not re.match(r'^[A-Z]', line):
            continue
        skip_words = ['abstract', 'keywords', 'introduction', 'figure',
                      'table', 'doi', 'http', 'university', 'institute',
                      'open access', 'copyright', 'license', 'received']
        if any(w in line.lower() for w in skip_words):
            continue
        test_line = clean_name(line)
        words = [w for w in re.split(r'[\s,]+', test_line) if w]
        if not words:
            continue
        capitalized = sum(1 for w in words if re.match(r'^[A-Z]', w) or w.lower() == 'and')
        if capitalized / len(words) < 0.8:
            continue

        raw_names = re.split(r',\s*|\s+and\s+', line)
        for raw in raw_names:
            name = clean_name(raw).strip()
            if not name or len(name) < 3:
                continue
            parts = name.split()
            if len(parts) >= 2:
                authors.append({
                    "name": " ".join(parts[:-1]),
                    "surname": parts[-1],
                    "email": ""
                })

    corr_match = re.search(
        r'\*Correspondence[:\s]+([A-Z][a-z]+(?:[\s\-][A-Za-z\-]+)+)\s+([\w.\-]+@[\w.\-]+\.\w+)',
        text
    )
    if corr_match and authors:
        corr_name = re.sub(r'[\d\*†‡§]+', '', corr_match.group(1)).strip()
        corr_email = corr_match.group(2)
        for author in authors:
            full = f"{author['name']} {author['surname']}"
            if corr_name in full or full in corr_name:
                author['email'] = corr_email

    return authors[:10]


def extract_date_from_pdf(text: str) -> str | None:
    """Extract publication year from PDF text."""
    match = re.search(r'\b((?:19|20)\d{2})[-/.](?:0[1-9]|1[012])[-/.](?:0[1-9]|[12][0-9]|3[01])\b', text)
    if match:
        return match.group(1)

    match = re.search(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+((?:19|20)\d{2})\b', text, re.IGNORECASE)
    if match:
        return match.group(1)

    match = re.search(r'\b(19\d{2}|20\d{2})\b', text)
    if match:
        return match.group(1)

    return None


def extract_journal_from_pdf(text: str) -> str | None:
    """Extract journal name from PDF text."""
    journal_patterns = [
        r'Published in\s*[:]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
        r'Journal of\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\s+Journal)',
        r'Source\s*[:]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
    ]
    for pattern in journal_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()

    for line in text.split('\n')[:15]:
        line = line.strip()
        if any(kw in line for kw in ["Journal", "Review", "Nature", "Science", "Lancet", "Medicine"]):
            if len(line.split()) < 10:
                return line
    return None


def extract_link_from_pdf(text: str, doi: str | None = None) -> str | None:
    """Extract article URL from PDF text, or construct from DOI."""
    if doi:
        return f"https://doi.org/{doi}"

    links = re.findall(r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-z]{2,6}\b(?:[-a-zA-Z0-9@:%_\+.~#?&//=]*)', text)
    trusted = ['sciencedirect', 'springer', 'wiley', 'nature.com', 'thelancet', 'bmj',
               'frontiersin', 'plos', 'pubmed.ncbi.nlm.nih.gov', 'who.int', 'cdc.gov',
               'acpjournals', 'nejm.org', 'jama.jamanetwork.com']
    for link in links:
        if any(domain in link for domain in trusted):
            return link
    return links[0] if links else None
