import xml.etree.ElementTree as ET
from typing import Optional

import requests  # need install


def get_response_content(doi: str) -> Optional[ET.Element]:
    """Get the XML response from the HAL API URL for a specific DOI"""
    try:
        api_url = (
            f"https://api.archives-ouvertes.fr/search/?q=doiId_s:{doi}&wt=xml&fl=uri_s"
        )
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        response_content = ET.fromstring(response.content)
        return response_content
    except Exception as e:
        print(f"Error while fetching the API : {e}")
        return None


def get_pdf_url(uri: str) -> str:
    """Get the PDF URL from the URI"""
    return f"{uri}/document"


def set_output_file(doi: str, output_dir: str = "pdf") -> str:
    """Set the name and the path of the PDF output file"""
    doi_str = doi.replace(".", "_").replace("/", "_")
    return str(output_dir + "/" + doi_str + ".pdf")


def download_pdf_from_url(pdf_url: str, output_path: str) -> bool:
    """Download the PDF from the URL"""
    try:
        pdf_response = requests.get(pdf_url, timeout=30)
        pdf_response.raise_for_status()

        with open(output_path, "wb") as f:
            f.write(pdf_response.content)
        print(f" PDF downloaded : {output_path}")
        return True

    except Exception as e:
        print(f"Download fail: {e}")
        return False


def get_pdf_from_doi(doi: str) -> bool:
    """Download the article's PDF for a specified DOI"""
    # 1. Get the response from the API and check that the DOI is in HAL library
    response_content = get_response_content(doi)
    if response_content is None:
        return False

    numFound = int(response_content.find(".//result").get("numFound", "0"))
    if numFound == 0:
        print("No matching data for this DOI.")
        return False

    # 2. Get the URI
    uri = response_content.find(".//str[@name='uri_s']").text
    if not uri:
        print("No uri found for this DOI")
        return False

    # 3. Download the PDF from the URI
    pdf_url = get_pdf_url(uri)
    output_path = set_output_file(doi)
    return download_pdf_from_url(pdf_url, output_path)


if __name__ == "__main__":
    # get_pdf_from_doi("10.1016/j.pnpbp.2024.110948")
    get_pdf_from_doi("10.1038/s41467-019-10626-x")
