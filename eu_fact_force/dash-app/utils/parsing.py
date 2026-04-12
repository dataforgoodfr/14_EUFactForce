import base64
from typing import Optional
import re
import fitz  # PyMuPDF

def load_png_as_data_uri(png_path: str) -> Optional[str]:
    """Return a data URI for an PNG file, or None if not found."""
    try:
        with open(png_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/png+xml;base64,{b64}"
    except FileNotFoundError:
        return None

def extract_doi_from_pdf(text: str) -> Optional[str]:
    """Extract DOI from PDF text using regex pattern."""
    # Pattern for DOI: 10.xxxx/xxxxx
    match = re.search(r'(?:doi[:\s]+)?(?:https?://)?(?:dx\.)?doi\.org/(10\.\S+)', text, re.IGNORECASE)
    if match:
        return match.group(1) if match.group(1).startswith('10.') else match.group(0)

    # Alternative pattern
    match = re.search(r'10\.\d{4,}/\S+', text)
    if match:
        return match.group(0)
    return None


def extract_abstract_from_pdf(text: str) -> Optional[str]:
    """Extract abstract from PDF text."""
    # Look for "Abstract" section
    abstract_pattern = r'(?:abstract|summary)\s*[:]*\s*(.+?)(?=(?:introduction|keywords|1\.\s|methods|methodology|introduction|related work|background)|\Z)'
    match = re.search(abstract_pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        abstract_text = match.group(1).strip()
        # Clean up and limit to reasonable length
        abstract_text = re.sub(r'\s+', ' ', abstract_text)[:500]
        return abstract_text if len(abstract_text) > 20 else None
    return None


def extract_authors_from_pdf(text: str) -> list[dict]:
    """Extract authors by finding the typical author line in scientific papers."""
    authors = []

    def clean_name(name: str) -> str:
        # Supprime chiffres, *, †, § collés au nom
        return re.sub(r'[\d\*†‡§]+', '', name).strip()

    lines = text.split('\n')[:50]

    for line in lines:
        line = line.strip()

        # Une ligne d'auteurs contient typiquement "and" ou une virgule
        # et ressemble à des noms propres (Majuscule, pas trop longue)
        if len(line) > 150 or len(line) < 5:
            continue
        if not re.search(r'\band\b|,', line):
            continue
        # Doit commencer par une majuscule
        if not re.match(r'^[A-Z]', line):
            continue
        # Ne doit pas contenir de mots typiques de non-auteurs
        skip_words = ['abstract', 'keywords', 'introduction', 'figure',
                      'table', 'doi', 'http', 'university', 'institute',
                      'open access', 'copyright', 'license', 'received']
        if any(w in line.lower() for w in skip_words):
            continue
        # Tous les "mots" (après nettoyage) doivent ressembler à des noms propres
        # càd commencer par une majuscule ou être un chiffre/symbole
        test_line = clean_name(line)
        words = [w for w in re.split(r'[\s,]+', test_line) if w]
        if not words:
            continue
        # Au moins 80% des mots doivent commencer par une majuscule
        capitalized = sum(1 for w in words if re.match(r'^[A-Z]', w) or w.lower() == 'and')
        if capitalized / len(words) < 0.8:
            continue

        # C'est probablement une ligne d'auteurs — on parse
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

    # Rattache l'email du corresponding author
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

def extract_date_from_pdf(text: str) -> Optional[str]:
    """Extract publication date (year only) from PDF text."""
    # YYYY-MM-DD or YYYY/MM/DD
    match = re.search(r'\b((?:19|20)\d{2})[-/.](?:0[1-9]|1[012])[-/.](?:0[1-9]|[12][0-9]|3[01])\b', text)
    if match:
        return match.group(1)

    # DD-MM-YYYY or DD/MM/YYYY
    match = re.search(r'\b(?:0[1-9]|[12][0-9]|3[01])[-/.](?:0[1-9]|1[012])[-/.]((?:19|20)\d{2})\b', text)

    # Pattern: Month Year (e.g., "January 2023")
    match = re.search(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+((?:19|20)\d{2})\b', text, re.IGNORECASE)
    if match:
        return match.group(1)

    # We look for years typically appearing in headers or near "Copyright" or "Received"
    # Just a year (between 1900 and 2099)
    match = re.search(r'\b(19\d{2}|20\d{2})\b', text)
    if match:
        return match.group(1)

    return None

def extract_journal_from_pdf(text: str) -> Optional[str]:
    """Extract journal name from PDF text."""
    journal_patterns = [
        r'Published in\s*[:]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
        r'Journal of\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\s+Journal)',
        r'Source\s*[:]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)'
    ]
    for pattern in journal_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()

    # Try to find it in the first few lines if not found by pattern
    lines = text.split('\n')[:15]
    for line in lines:
        line = line.strip()
        if any(kw in line for kw in ["Journal", "Review", "Nature", "Science", "Lancet", "Medicine"]):
            if len(line.split()) < 10: # Avoid long sentences
                return line
    return None

def extract_link_from_pdf(text: str, doi: Optional[str] = None) -> Optional[str]:
    """Extract article link from PDF text or DOI."""
    if doi:
        return f"https://doi.org/{doi}"

    # Look for https links that might be the editor's link
    links = re.findall(r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-z]{2,6}\b(?:[-a-zA-Z0-9@:%_\+.~#?&//=]*)', text)
    for link in links:
        if any(domain in link for domain in ['sciencedirect', 'springer', 'wiley', 'nature.com', 'thelancet', 'bmj', 'frontiersin', 'plos', 'pubmed.ncbi.nlm.nih.gov'\
            , 'who.int', 'cdc.gov', 'acpjournals', 'nejm.org', 'jama.jamanetwork.com']):
            return link
    return links[0] if links else None

def extract_text_by_blocks(uploaded_file_bytes) -> str:
    doc = fitz.open(stream=uploaded_file_bytes, filetype="pdf")
    full_text = ""
    for page in doc[:3]:
        # Trie les blocs par position verticale puis horizontale
        blocks = page.get_text("blocks")
        blocks.sort(key=lambda b: (round(b[1] / 20), b[0]))
        for block in blocks:
            full_text += block[4] + "\n"
    return full_text

def extract_title_from_pdf(text: str) -> Optional[str]:
    """Try to extract the title from the first few lines of the PDF."""
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if not lines:
        return None

    # Typically the title is in the first few lines, is not too long,
    # and doesn't contain certain keywords.
    for line in lines[:10]:
        # Skip lines that are likely not titles (e.g., journal names, DOI, authors)
        if any(kw in line.lower() for kw in ["journal", "doi:", "http", "vol.", "issn", "received:", "accepted:", "copyright"]):
            continue
        # Titles are usually at least 3 words and not excessively long (e.g. < 250 chars)
        if 3 <= len(line.split()) <= 40 and len(line) < 450:
            return line
    return None

def extract_pdf_metadata(uploaded_file) -> dict:
    """Extract metadata from PDF file."""
    metadata = {
        "title": None,
        "doi": None,
        "abstract": None,
        "publication_date": None,
        "journal": None,
        "article_link": None,
        "authors": []
    }
    try:
        # Extract text from PDF
        pdf_text = extract_text_by_blocks(uploaded_file.read())

        # Extract metadata
        metadata["title"] = extract_title_from_pdf(pdf_text)
        metadata["doi"] = extract_doi_from_pdf(pdf_text)
        metadata["abstract"] = extract_abstract_from_pdf(pdf_text)
        metadata["authors"] = extract_authors_from_pdf(pdf_text)
        metadata["publication_date"] = extract_date_from_pdf(pdf_text)
        metadata["journal"] = extract_journal_from_pdf(pdf_text)
        metadata["article_link"] = extract_link_from_pdf(pdf_text, metadata["doi"])

    except Exception as e:
        print(f"Error processing PDF: {e}")
    return metadata
