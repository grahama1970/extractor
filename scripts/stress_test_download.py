#!/usr/bin/env python3
"""Download challenging PDFs from arXiv for stress testing.

Focuses on papers likely to have complex tables:
- Benchmark papers (ML, CV, NLP)
- Survey papers
- Papers with "table", "benchmark", "comprehensive" in abstract
"""
import os
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
import hashlib
import json

# Categories likely to have complex tables
CATEGORIES = [
    "cs.LG",  # Machine Learning
    "cs.CV",  # Computer Vision
    "cs.CL",  # Computational Linguistics
    "cs.AI",  # Artificial Intelligence
    "stat.ML",  # Statistics ML
]

# Search queries for complex papers
SEARCH_QUERIES = [
    "benchmark AND table",
    "survey AND comparison",
    "comprehensive AND evaluation",
    "ablation AND study",
    "state-of-the-art AND results",
    "experimental AND analysis",
]

OUTPUT_DIR = Path("/mnt/storage12tb/extractor_corpus/stress_test_pdfs")
METADATA_FILE = OUTPUT_DIR / "download_manifest.jsonl"

def search_arxiv(query: str, category: str, max_results: int = 100) -> list:
    """Search arXiv API for papers."""
    base_url = "http://export.arxiv.org/api/query"
    search_query = f"cat:{category} AND ({query})"
    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }

    url = f"{base_url}?{urllib.parse.urlencode(params)}"

    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            content = response.read()

        root = ET.fromstring(content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        papers = []
        for entry in root.findall("atom:entry", ns):
            paper_id = entry.find("atom:id", ns).text.split("/")[-1]
            title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
            abstract = entry.find("atom:summary", ns).text.strip()[:500]

            # Get PDF link
            pdf_link = None
            for link in entry.findall("atom:link", ns):
                if link.get("title") == "pdf":
                    pdf_link = link.get("href")
                    break

            if pdf_link:
                papers.append({
                    "id": paper_id,
                    "title": title,
                    "abstract": abstract,
                    "pdf_url": pdf_link,
                    "category": category,
                    "query": query,
                })

        return papers
    except Exception as e:
        print(f"Error searching {category}/{query}: {e}")
        return []


def download_pdf(paper: dict, output_dir: Path) -> bool:
    """Download a single PDF."""
    paper_id = paper["id"].replace("/", "_").replace(".", "_")
    filename = f"arxiv_{paper_id}.pdf"
    filepath = output_dir / filename

    if filepath.exists():
        return True  # Already downloaded

    try:
        pdf_url = paper["pdf_url"]
        if not pdf_url.endswith(".pdf"):
            pdf_url += ".pdf"

        urllib.request.urlretrieve(pdf_url, filepath)

        # Verify it's a valid PDF
        with open(filepath, "rb") as f:
            header = f.read(5)
        if header != b"%PDF-":
            filepath.unlink()
            return False

        return True
    except Exception as e:
        print(f"Error downloading {paper['id']}: {e}")
        if filepath.exists():
            filepath.unlink()
        return False


def main():
    """Search arXiv for challenging papers and save their data."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_papers = []
    seen_ids = set()

    print("Searching arXiv for challenging papers...")
    for category in CATEGORIES:
        for query in SEARCH_QUERIES:
            print(f"  Searching {category} for '{query}'...")
            papers = search_arxiv(query, category, max_results=50)
            for p in papers:
                if p["id"] not in seen_ids:
                    all_papers.append(p)
                    seen_ids.add(p["id"])
            time.sleep(3)  # Rate limit

    print(f"\nFound {len(all_papers)} unique papers")

    # Download PDFs
    downloaded = 0
    failed = 0
    target = min(1000, len(all_papers))

    with open(METADATA_FILE, "a") as f:
        for i, paper in enumerate(all_papers[:target]):
            print(f"[{i+1}/{target}] Downloading {paper['id'][:20]}...", end=" ")
            if download_pdf(paper, OUTPUT_DIR):
                print("OK")
                downloaded += 1
                paper["downloaded_at"] = datetime.now().isoformat()
                f.write(json.dumps(paper) + "\n")
            else:
                print("FAILED")
                failed += 1

            if (i + 1) % 10 == 0:
                print(f"  Progress: {downloaded} downloaded, {failed} failed")

            time.sleep(1)  # Rate limit

    print(f"\n=== Download Complete ===")
    print(f"Downloaded: {downloaded}")
    print(f"Failed: {failed}")
    print(f"Output dir: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
