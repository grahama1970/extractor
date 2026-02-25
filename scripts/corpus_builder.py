#!/usr/bin/env python3
"""
Corpus Builder - Download diverse PDFs for extractor training.

Sources:
- arXiv: Scientific papers with complex tables
- NIST: Standards and security publications
- IETF: RFCs (network standards)
- NASA: Technical reports
- Government: Various federal publications

Usage:
    python corpus_builder.py download --source arxiv --count 1000
    python corpus_builder.py download --source nist --count 500
    python corpus_builder.py download --source all --count 5000
    python corpus_builder.py status
    python corpus_builder.py daemon  # Continuous learning mode
"""
import os
import sys
import json
import time
import hashlib
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Dict, Any
import random

import typer
from loguru import logger

app = typer.Typer(help="Build diverse PDF corpus for extractor training")

# =============================================================================
# Fetcher Integration - Use /fetcher skill for robust downloads
# =============================================================================

FETCHER_SCRIPT = Path("/home/graham/workspace/experiments/pi-mono/.pi/skills/fetcher/run.sh")


def use_fetcher_for_download(url: str, output_path: Path, timeout: int = 120) -> bool:
    """
    Use the /fetcher skill for more robust PDF downloads.

    Benefits over raw urllib:
    - Automatic retries with exponential backoff
    - Proxy rotation for rate-limited sites
    - Playwright fallback for JS-heavy pages
    - Better error handling and reporting
    """
    if not FETCHER_SCRIPT.exists():
        return False

    import subprocess
    import tempfile

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [str(FETCHER_SCRIPT), "get", url, "--out", tmpdir],
                capture_output=True,
                timeout=timeout,
                text=True,
            )

            # Fetcher downloads to tmpdir/downloads/
            downloads_dir = Path(tmpdir) / "downloads"
            if downloads_dir.exists():
                pdfs = list(downloads_dir.glob("*.pdf"))
                if pdfs:
                    # Copy the first PDF to output
                    import shutil
                    shutil.copy(pdfs[0], output_path)
                    return True

            return False
    except Exception as e:
        logger.debug(f"Fetcher failed for {url}: {e}")
        return False


def batch_download_with_fetcher(urls: List[str], output_dir: Path) -> Dict[str, Path]:
    """
    Use fetcher's get-manifest mode for efficient batch downloads.

    This is the preferred method for downloading multiple URLs:
    - Parallel downloads
    - Automatic retries
    - Rate limiting per domain
    - Progress tracking
    """
    import subprocess
    import tempfile
    import shutil

    if not FETCHER_SCRIPT.exists():
        logger.warning("Fetcher not available, falling back to sequential downloads")
        return {}

    results = {}

    with tempfile.TemporaryDirectory() as tmpdir:
        # Write manifest file
        manifest_path = Path(tmpdir) / "urls.txt"
        manifest_path.write_text("\n".join(urls))

        out_dir = Path(tmpdir) / "fetched"

        # Run fetcher in manifest mode
        logger.info(f"Fetching {len(urls)} URLs with /fetcher...")
        try:
            result = subprocess.run(
                [str(FETCHER_SCRIPT), "get-manifest", str(manifest_path), "--out", str(out_dir)],
                capture_output=True,
                timeout=600,  # 10 min for batch
                text=True,
            )

            # Collect downloaded PDFs
            downloads_dir = out_dir / "downloads"
            if downloads_dir.exists():
                for pdf in downloads_dir.glob("*.pdf"):
                    # Use PDF filename or generate from URL
                    dest = output_dir / pdf.name
                    if not dest.exists():
                        shutil.copy(pdf, dest)
                        results[pdf.name] = dest
                        logger.debug(f"  Downloaded: {pdf.name}")

            logger.info(f"Fetcher batch complete: {len(results)} PDFs")

        except subprocess.TimeoutExpired:
            logger.warning("Fetcher batch timed out")
        except Exception as e:
            logger.warning(f"Fetcher batch failed: {e}")

    return results


def download_with_fallback(url: str, output_path: Path, use_fetcher: bool = True) -> bool:
    """
    Download a URL with fetcher fallback to raw urllib.
    """
    if output_path.exists():
        return True

    # Try fetcher first if available
    if use_fetcher and FETCHER_SCRIPT.exists():
        if use_fetcher_for_download(url, output_path):
            return True
        logger.debug(f"Fetcher failed, falling back to urllib for {url}")

    # Fallback to raw urllib
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ExtractorCorpusBuilder/1.0"})
        with urllib.request.urlopen(req, timeout=60) as response:
            content = response.read()

        if len(content) > 10000 and content[:4] == b"%PDF":
            output_path.write_bytes(content)
            return True
    except Exception as e:
        logger.debug(f"urllib failed for {url}: {e}")

    return False

# =============================================================================
# Configuration
# =============================================================================

CORPUS_ROOT = Path(os.environ.get("CORPUS_ROOT", "/mnt/storage12tb/extractor_corpus"))
MANIFEST_FILE = CORPUS_ROOT / "metadata" / "download_manifest.jsonl"
STATE_FILE = CORPUS_ROOT / "metadata" / "corpus_state.json"

# Rate limiting per source
RATE_LIMITS = {
    "arxiv": 3.0,      # 3 seconds between requests (be nice to arXiv)
    "nist": 1.0,       # 1 second
    "ietf": 0.5,       # IETF is fast
    "nasa": 2.0,       # NASA NTRS
    "government": 1.0,
    "defense": 3.0,    # Defense papers (arXiv backend)
    "faa": 2.0,        # FAA documents
    "dtic": 2.0,       # DTIC public docs
    "industry": 1.0,   # Industry standards
}

# =============================================================================
# Federated Taxonomy Classification
# =============================================================================
# Maps PDF sources to taxonomy tags for multi-hop graph traversal.
# Bridge Attributes: Precision, Resilience, Fragility, Corruption, Loyalty, Stealth
# Collection Dimensions: Domain, Function, Thematic Weight, Perspective

SOURCE_TAXONOMY = {
    "arxiv": {
        "collection": "academic",
        "domain": "research",
        "function": "knowledge",
        "perspective": "scientific",
        "bridge_candidates": ["Precision"],  # Academic papers tend to be well-structured
    },
    "nist": {
        "collection": "government:standards",
        "domain": "security",
        "function": "compliance",
        "perspective": "operational",
        "bridge_candidates": ["Precision", "Resilience"],
        "thematic_weight": "Critical",
    },
    "ietf": {
        "collection": "standards:network",
        "domain": "protocol",
        "function": "specification",
        "perspective": "technical",
        "bridge_candidates": ["Precision"],
        "thematic_weight": "High",
    },
    "nasa": {
        "collection": "government:aerospace",
        "domain": "engineering",
        "function": "specification",
        "perspective": "technical",
        "bridge_candidates": ["Precision", "Resilience"],
        "thematic_weight": "Critical",
    },
    "defense": {
        "collection": "academic:defense",
        "domain": "hardened_systems",
        "function": "research",
        "perspective": "operational",
        "bridge_candidates": ["Resilience", "Stealth"],
        "thematic_weight": "Critical",
    },
    "faa": {
        "collection": "government:aviation",
        "domain": "certification",
        "function": "compliance",
        "perspective": "regulatory",
        "bridge_candidates": ["Precision", "Loyalty"],  # Must follow standards
        "thematic_weight": "Critical",
    },
    "dtic": {
        "collection": "government:defense",
        "domain": "military",
        "function": "specification",
        "perspective": "operational",
        "bridge_candidates": ["Resilience", "Stealth"],
        "thematic_weight": "Critical",
    },
    "industry": {
        "collection": "standards:industry",
        "domain": "engineering",
        "function": "compliance",
        "perspective": "commercial",
        "bridge_candidates": ["Precision"],
        "thematic_weight": "High",
    },
    "government": {
        "collection": "government:generic",
        "domain": "policy",
        "function": "compliance",
        "perspective": "regulatory",
        "bridge_candidates": ["Loyalty"],
        "thematic_weight": "High",
    },
}

# Vendor/size classification for Military Industrial Complex diversity
VENDOR_CLASSIFICATION = {
    # Large prime contractors
    "boeing": "prime_contractor",
    "lockheed": "prime_contractor",
    "northrop": "prime_contractor",
    "raytheon": "prime_contractor",
    "general_dynamics": "prime_contractor",
    "bae_systems": "prime_contractor",
    # Government agencies
    "nasa": "government_agency",
    "faa": "government_agency",
    "nist": "government_agency",
    "dod": "government_agency",
    "darpa": "government_agency",
    # Standards bodies
    "rtca": "standards_body",
    "sae": "standards_body",
    "ieee": "standards_body",
    "iso": "standards_body",
    # Research institutions
    "mit": "research_institution",
    "jpl": "research_institution",
    "caltech": "research_institution",
    "sandia": "research_institution",
}


def classify_document_taxonomy(
    source: str,
    doc_id: str,
    title: str,
    doc_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Classify document with Federated Taxonomy tags.

    Returns taxonomy data for storage in manifest and memory integration.
    """
    base_taxonomy = SOURCE_TAXONOMY.get(source, {
        "collection": f"unknown:{source}",
        "domain": "unclassified",
        "function": "research",
        "perspective": "unknown",
        "bridge_candidates": [],
    })

    # Detect vendor/institution from title or ID
    vendor_type = "unclassified"
    for vendor, v_type in VENDOR_CLASSIFICATION.items():
        if vendor.lower() in title.lower() or vendor.lower() in doc_id.lower():
            vendor_type = v_type
            break

    # Detect document complexity indicators
    complexity_hints = []
    title_lower = title.lower()
    if "requirement" in title_lower or "specification" in title_lower:
        complexity_hints.append("requirements_spec")
    if "design" in title_lower or "architecture" in title_lower:
        complexity_hints.append("design_doc")
    if "test" in title_lower or "verification" in title_lower:
        complexity_hints.append("test_doc")
    if "safety" in title_lower or "hazard" in title_lower:
        complexity_hints.append("safety_doc")
    if "standard" in title_lower or "guideline" in title_lower:
        complexity_hints.append("standard")

    return {
        "taxonomy_version": "federated_v1",
        "collection": base_taxonomy.get("collection"),
        "domain": base_taxonomy.get("domain"),
        "function": base_taxonomy.get("function"),
        "perspective": base_taxonomy.get("perspective"),
        "thematic_weight": base_taxonomy.get("thematic_weight", "Medium"),
        "bridge_candidates": base_taxonomy.get("bridge_candidates", []),
        "vendor_type": vendor_type,
        "complexity_hints": complexity_hints,
        "doc_type": doc_type or "unknown",
        "classified_at": datetime.utcnow().isoformat(),
    }


# =============================================================================
# arXiv Downloader
# =============================================================================

ARXIV_CATEGORIES = [
    "cs.LG", "cs.CV", "cs.CL", "cs.AI", "cs.SE", "cs.CR",  # CS
    "stat.ML", "stat.ME",  # Statistics
    "eess.SP", "eess.SY",  # Electrical Engineering
    "physics.data-an",     # Physics data analysis
    "q-bio.QM",            # Quantitative Biology
]

ARXIV_QUERIES = [
    "benchmark AND table",
    "survey AND comparison",
    "comprehensive AND evaluation",
    "ablation AND study",
    "experimental AND results",
    "requirements AND specification",
    "system AND architecture",
]


def search_arxiv(query: str, category: str, max_results: int = 100) -> List[Dict]:
    """Search arXiv API."""
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
            content = response.read().decode("utf-8")

        root = ET.fromstring(content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        papers = []
        for entry in root.findall("atom:entry", ns):
            paper_id = entry.find("atom:id", ns).text.split("/abs/")[-1]
            title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
            papers.append({
                "id": paper_id,
                "title": title,
                "source": "arxiv",
                "category": category,
            })
        return papers
    except Exception as e:
        logger.warning(f"arXiv search failed for {category}/{query}: {e}")
        return []


def download_arxiv_paper(paper_id: str, output_dir: Path) -> Optional[Path]:
    """Download a single arXiv paper."""
    # Normalize ID
    paper_id = paper_id.replace(":", "_").replace("/", "_")
    clean_id = paper_id.split("v")[0] if "v" in paper_id else paper_id

    output_path = output_dir / f"arxiv_{paper_id}.pdf"
    if output_path.exists():
        return output_path

    # Try PDF URL
    pdf_url = f"https://arxiv.org/pdf/{clean_id}.pdf"

    try:
        req = urllib.request.Request(pdf_url, headers={"User-Agent": "ExtractorCorpusBuilder/1.0"})
        with urllib.request.urlopen(req, timeout=60) as response:
            content = response.read()

        if len(content) < 10000:  # Too small, probably error page
            return None

        output_path.write_bytes(content)
        return output_path
    except Exception as e:
        logger.debug(f"Failed to download {paper_id}: {e}")
        return None


def collect_arxiv_papers(count: int) -> List[Dict]:
    """Collect paper metadata from arXiv."""
    papers = []
    seen_ids = set()

    for category in ARXIV_CATEGORIES:
        if len(papers) >= count:
            break
        for query in ARXIV_QUERIES:
            if len(papers) >= count:
                break
            logger.info(f"  Searching {category} for '{query}'...")
            results = search_arxiv(query, category, max_results=100)
            for paper in results:
                if paper["id"] not in seen_ids:
                    seen_ids.add(paper["id"])
                    papers.append(paper)
            time.sleep(RATE_LIMITS["arxiv"])

    return papers[:count]


# =============================================================================
# NIST Downloader
# =============================================================================

NIST_SERIES = [
    "SP",    # Special Publications (SP 800 series = security)
    "FIPS",  # Federal Information Processing Standards
    "IR",    # Internal Reports
    "TN",    # Technical Notes
]


def collect_nist_publications(count: int) -> List[Dict]:
    """Collect NIST publication metadata."""
    publications = []

    # NIST CSRC (Computer Security Resource Center) for SP 800 series
    # These are high-value requirements documents
    sp800_base = "https://csrc.nist.gov/publications/sp800"

    # Known high-value NIST publications
    known_pubs = [
        ("SP", "800-53", "Security and Privacy Controls"),
        ("SP", "800-53A", "Assessing Security Controls"),
        ("SP", "800-53B", "Control Baselines"),
        ("SP", "800-171", "Protecting CUI"),
        ("SP", "800-171A", "Assessing CUI Requirements"),
        ("SP", "800-37", "Risk Management Framework"),
        ("SP", "800-39", "Managing Risk"),
        ("SP", "800-30", "Risk Assessment"),
        ("SP", "800-60", "Information Types"),
        ("SP", "800-61", "Incident Handling"),
        ("SP", "800-82", "ICS Security"),
        ("SP", "800-83", "Malware Prevention"),
        ("SP", "800-86", "Forensics"),
        ("SP", "800-88", "Media Sanitization"),
        ("SP", "800-92", "Log Management"),
        ("SP", "800-115", "Technical Security Testing"),
        ("SP", "800-122", "PII Protection"),
        ("SP", "800-123", "Server Security"),
        ("SP", "800-124", "Mobile Device Security"),
        ("SP", "800-125", "Virtualization Security"),
        ("SP", "800-128", "Configuration Management"),
        ("SP", "800-137", "ISCM"),
        ("SP", "800-144", "Cloud Computing"),
        ("SP", "800-145", "Cloud Definition"),
        ("SP", "800-146", "Cloud Synopsis"),
        ("SP", "800-160", "Systems Security Engineering"),
        ("SP", "800-161", "Supply Chain Risk"),
        ("SP", "800-162", "ABAC"),
        ("SP", "800-163", "App Vetting"),
        ("SP", "800-175B", "Cryptographic Standards"),
        ("SP", "800-181", "NICE Framework"),
        ("SP", "800-184", "Cybersecurity Event Recovery"),
        ("SP", "800-188", "De-Identification"),
        ("SP", "800-190", "Container Security"),
        ("SP", "800-193", "Platform Firmware Resilience"),
        ("SP", "800-204", "Microservices Security"),
        ("SP", "800-207", "Zero Trust Architecture"),
        ("SP", "800-210", "Cloud Access Control"),
        ("SP", "800-218", "Secure Software Development"),
        ("FIPS", "140-3", "Cryptographic Module Validation"),
        ("FIPS", "180-4", "Secure Hash Standard"),
        ("FIPS", "186-5", "Digital Signature Standard"),
        ("FIPS", "197", "AES"),
        ("FIPS", "198-1", "HMAC"),
        ("FIPS", "199", "Security Categorization"),
        ("FIPS", "200", "Minimum Security Requirements"),
        ("FIPS", "201-3", "PIV"),
    ]

    for series, number, title in known_pubs[:count]:
        publications.append({
            "id": f"NIST.{series}.{number}",
            "title": f"NIST {series} {number}: {title}",
            "source": "nist",
            "series": series,
            "number": number,
        })

    return publications


def download_nist_publication(pub: Dict, output_dir: Path) -> Optional[Path]:
    """Download a NIST publication."""
    series = pub.get("series", "SP")
    number = pub.get("number", "")

    # Clean number for filename
    clean_num = number.replace("-", "_").replace(" ", "_")
    output_path = output_dir / f"nist_{series.lower()}_{clean_num}.pdf"

    if output_path.exists():
        return output_path

    # Try multiple URL patterns
    urls_to_try = []

    if series == "SP":
        # SP 800 series URLs
        num_parts = number.split("-")
        if len(num_parts) >= 2 and num_parts[0] == "800":
            urls_to_try.extend([
                f"https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.{number}.pdf",
                f"https://csrc.nist.gov/files/pubs/sp/{number.replace('-', '/')}/final/docs/sp{number}.pdf",
            ])
    elif series == "FIPS":
        urls_to_try.extend([
            f"https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.{number}.pdf",
            f"https://csrc.nist.gov/files/pubs/fips/{number}/final/docs/fips{number}.pdf",
        ])

    # Generic nvlpubs URL
    urls_to_try.append(f"https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.{series}.{number}.pdf")

    for url in urls_to_try:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ExtractorCorpusBuilder/1.0"})
            with urllib.request.urlopen(req, timeout=60) as response:
                content = response.read()

            if len(content) > 50000:  # NIST docs are usually large
                output_path.write_bytes(content)
                return output_path
        except Exception:
            continue

    return None


# =============================================================================
# IETF RFC Downloader
# =============================================================================

def collect_ietf_rfcs(count: int) -> List[Dict]:
    """Collect IETF RFC metadata."""
    rfcs = []

    # Focus on RFCs with requirements tables (security, protocols)
    important_rfcs = [
        # Security
        (8446, "TLS 1.3"),
        (7519, "JWT"),
        (7515, "JWS"),
        (7516, "JWE"),
        (7517, "JWK"),
        (6749, "OAuth 2.0"),
        (6750, "OAuth Bearer Token"),
        (7636, "PKCE"),
        (8252, "OAuth Native Apps"),
        (6819, "OAuth Threat Model"),
        (5246, "TLS 1.2"),
        (4346, "TLS 1.1"),
        (2818, "HTTP Over TLS"),
        (6125, "TLS Server Identity"),
        (5280, "X.509 PKI"),
        (3280, "X.509 Certificate Profile"),
        (5652, "CMS"),
        (8017, "PKCS #1"),

        # HTTP
        (9110, "HTTP Semantics"),
        (9111, "HTTP Caching"),
        (9112, "HTTP/1.1"),
        (9113, "HTTP/2"),
        (9114, "HTTP/3"),
        (7540, "HTTP/2 (original)"),
        (6265, "HTTP Cookies"),
        (7234, "HTTP Caching (old)"),
        (7231, "HTTP Semantics (old)"),

        # DNS
        (1035, "DNS Implementation"),
        (8484, "DNS over HTTPS"),
        (7858, "DNS over TLS"),
        (8499, "DNS Terminology"),

        # Email
        (5321, "SMTP"),
        (5322, "Internet Message Format"),
        (6376, "DKIM"),
        (7208, "SPF"),
        (7489, "DMARC"),

        # IP/Networking
        (791, "IP"),
        (793, "TCP"),
        (768, "UDP"),
        (8200, "IPv6"),
        (4291, "IPv6 Addressing"),
        (6724, "Default Address Selection"),

        # Applications
        (3986, "URI"),
        (7230, "HTTP/1.1 Message Syntax"),
        (7159, "JSON"),
        (8259, "JSON (updated)"),
        (4627, "JSON Media Type"),
        (6570, "URI Template"),
        (5988, "Web Linking"),
        (8288, "Web Linking (updated)"),
    ]

    for rfc_num, title in important_rfcs[:count]:
        rfcs.append({
            "id": f"RFC{rfc_num}",
            "title": f"RFC {rfc_num}: {title}",
            "source": "ietf",
            "rfc_number": rfc_num,
        })

    # Add more RFCs by number range for diversity
    if len(rfcs) < count:
        # Recent RFCs (2020-2024) likely have good formatting
        for rfc_num in range(9000, 9500):
            if len(rfcs) >= count:
                break
            rfcs.append({
                "id": f"RFC{rfc_num}",
                "title": f"RFC {rfc_num}",
                "source": "ietf",
                "rfc_number": rfc_num,
            })

    return rfcs[:count]


def download_ietf_rfc(rfc: Dict, output_dir: Path) -> Optional[Path]:
    """Download an IETF RFC as PDF."""
    rfc_num = rfc.get("rfc_number", 0)
    output_path = output_dir / f"rfc{rfc_num}.pdf"

    if output_path.exists():
        return output_path

    # IETF provides PDFs
    url = f"https://www.rfc-editor.org/rfc/rfc{rfc_num}.pdf"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ExtractorCorpusBuilder/1.0"})
        with urllib.request.urlopen(req, timeout=60) as response:
            content = response.read()

        if len(content) > 10000 and content[:4] == b"%PDF":
            output_path.write_bytes(content)
            return output_path
    except Exception as e:
        logger.debug(f"Failed to download RFC {rfc_num}: {e}")

    return None


# =============================================================================
# NASA Technical Reports Downloader
# =============================================================================

def collect_nasa_reports(count: int) -> List[Dict]:
    """Collect NASA technical report metadata."""
    reports = []

    # NASA Technical Reports Server (NTRS) - public domain
    # Focus on systems engineering, requirements docs
    search_terms = [
        "requirements specification",
        "system architecture",
        "design document",
        "test plan",
        "verification validation",
        "safety analysis",
        "mission operations",
        "software development",
    ]

    # NTRS API endpoint
    ntrs_api = "https://ntrs.nasa.gov/api/citations/search"

    for term in search_terms:
        if len(reports) >= count:
            break

        try:
            params = {
                "q": term,
                "highlight": "false",
                "page[size]": 50,
            }
            url = f"{ntrs_api}?{urllib.parse.urlencode(params)}"

            req = urllib.request.Request(url, headers={
                "User-Agent": "ExtractorCorpusBuilder/1.0",
                "Accept": "application/json",
            })

            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))

            for item in data.get("results", []):
                if len(reports) >= count:
                    break

                doc_id = item.get("id")
                title = item.get("title", "Unknown")

                # Check if PDF is available
                downloads = item.get("downloads", [])
                pdf_links = [d for d in downloads if d.get("mimetype") == "application/pdf"]

                if pdf_links:
                    reports.append({
                        "id": f"NASA-{doc_id}",
                        "title": title[:100],
                        "source": "nasa",
                        "ntrs_id": doc_id,
                        "pdf_url": pdf_links[0].get("links", {}).get("original"),
                    })

            time.sleep(RATE_LIMITS["nasa"])

        except Exception as e:
            logger.warning(f"NASA search failed for '{term}': {e}")

    return reports[:count]


def download_nasa_report(report: Dict, output_dir: Path) -> Optional[Path]:
    """Download a NASA technical report."""
    ntrs_id = report.get("ntrs_id", "")
    pdf_url = report.get("pdf_url")

    output_path = output_dir / f"nasa_{ntrs_id}.pdf"

    if output_path.exists():
        return output_path

    # Fix relative URLs
    if pdf_url and pdf_url.startswith("/"):
        pdf_url = f"https://ntrs.nasa.gov{pdf_url}"
    elif not pdf_url:
        # Try to construct URL
        pdf_url = f"https://ntrs.nasa.gov/api/citations/{ntrs_id}/downloads/{ntrs_id}.pdf"

    try:
        req = urllib.request.Request(pdf_url, headers={"User-Agent": "ExtractorCorpusBuilder/1.0"})
        with urllib.request.urlopen(req, timeout=120) as response:
            content = response.read()

        if len(content) > 10000 and content[:4] == b"%PDF":
            output_path.write_bytes(content)
            return output_path
    except Exception as e:
        logger.debug(f"Failed to download NASA {ntrs_id}: {e}")

    return None


# =============================================================================
# Government Publications (misc)
# =============================================================================

def collect_government_docs(count: int) -> List[Dict]:
    """Collect various government publication metadata."""
    docs = []

    # DOD standards (public versions)
    dod_docs = [
        ("MIL-STD-498", "Software Development and Documentation"),
        ("MIL-STD-882E", "System Safety"),
        ("MIL-HDBK-217F", "Reliability Prediction"),
        ("MIL-STD-1553", "Digital Time Division"),
        ("MIL-STD-810", "Environmental Engineering"),
        ("DO-178C", "Airborne Software"),
        ("DO-254", "Airborne Electronic Hardware"),
        ("DO-326A", "Airborne Security"),
    ]

    for doc_id, title in dod_docs:
        docs.append({
            "id": doc_id,
            "title": f"{doc_id}: {title}",
            "source": "government",
            "doc_type": "standard",
        })

    return docs[:count]


# =============================================================================
# Defense / Military Industrial Complex Sources
# =============================================================================

DEFENSE_ARXIV_QUERIES = [
    # Hardened systems
    "radiation hardening",
    "fault tolerant computing",
    "safety critical systems",
    "real-time systems verification",
    "formal verification avionics",
    "embedded systems security",
    "cyber-physical systems security",

    # Defense/aerospace specific
    "missile guidance",
    "radar signal processing",
    "electronic warfare",
    "autonomous vehicles military",
    "UAV swarm",
    "satellite communication",
    "space systems engineering",
    "hypersonic",

    # Requirements/compliance
    "DO-178 compliance",
    "safety assessment",
    "hazard analysis",
    "FMEA aerospace",
    "reliability engineering",
    "systems engineering process",
    "model based systems engineering",
    "SysML requirements",

    # Requirements Management / DOORS-style documents
    "requirements traceability",
    "requirements engineering aerospace",
    "DOORS requirements management",
    "ReqIF requirements interchange",
    "requirements verification matrix",
    "derived requirements",
    "requirements allocation",
    "interface control document",
    "data item description",
]

DEFENSE_ARXIV_CATEGORIES = [
    "cs.SE",      # Software Engineering
    "cs.SY",      # Systems and Control
    "cs.RO",      # Robotics
    "cs.CR",      # Cryptography and Security
    "eess.SY",    # Systems Engineering
    "eess.SP",    # Signal Processing
    "cs.AR",      # Hardware Architecture
    "cs.DC",      # Distributed Computing
    "cs.ET",      # Emerging Technologies
    "physics.ins-det",  # Instrumentation
]


def collect_defense_papers(count: int) -> List[Dict]:
    """Collect defense/aerospace academic papers from arXiv."""
    papers = []
    seen_ids = set()

    for category in DEFENSE_ARXIV_CATEGORIES:
        if len(papers) >= count:
            break
        for query in DEFENSE_ARXIV_QUERIES:
            if len(papers) >= count:
                break
            logger.info(f"  Searching {category} for '{query}'...")
            results = search_arxiv(query, category, max_results=50)
            for paper in results:
                if paper["id"] not in seen_ids:
                    seen_ids.add(paper["id"])
                    paper["doc_type"] = "defense_academic"
                    papers.append(paper)
            time.sleep(RATE_LIMITS["arxiv"])

    return papers[:count]


# =============================================================================
# FAA / Aviation Sources
# =============================================================================

FAA_DOCUMENTS = [
    # Advisory Circulars
    ("AC 20-115D", "Airborne Software Development Assurance"),
    ("AC 20-152A", "RTCA DO-178C Software"),
    ("AC 20-170", "RTCA DO-330 Software Tool Qualification"),
    ("AC 25.1309-1A", "System Design and Analysis"),
    ("AC 23.1309-1E", "System Safety Analysis"),
    ("AC 27-1B", "Rotorcraft Certification"),
    ("AC 29-2C", "Transport Rotorcraft Certification"),
    ("AC 33.28-3", "Engine Certification"),

    # Orders
    ("Order 8110.4C", "Type Certification"),
    ("Order 8110.37E", "Designated Engineering Representatives"),
    ("Order 8120.23", "Production Approval"),

    # Handbooks
    ("FAA-H-8083-1B", "Aircraft Weight and Balance"),
    ("FAA-H-8083-25B", "Pilot's Handbook"),
    ("FAA-H-8083-3C", "Airplane Flying Handbook"),
]


def collect_faa_documents(count: int) -> List[Dict]:
    """Collect FAA documents."""
    docs = []

    for doc_id, title in FAA_DOCUMENTS[:count]:
        docs.append({
            "id": doc_id.replace(" ", "_"),
            "title": f"FAA {doc_id}: {title}",
            "source": "faa",
            "doc_type": "aviation_standard",
            "faa_id": doc_id,
        })

    return docs


def download_faa_document(doc: Dict, output_dir: Path) -> Optional[Path]:
    """Download FAA document."""
    faa_id = doc.get("faa_id", "")
    clean_id = faa_id.replace(" ", "_").replace("/", "_").replace(".", "_")
    output_path = output_dir / f"faa_{clean_id}.pdf"

    if output_path.exists():
        return output_path

    # FAA documents are at various URLs
    # AC documents
    if faa_id.startswith("AC"):
        ac_num = faa_id.replace("AC ", "").replace("-", "_")
        urls = [
            f"https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_{ac_num}.pdf",
            f"https://www.faa.gov/regulations_policies/advisory_circulars/index.cfm/go/document.information/documentID/{ac_num}",
        ]
    elif faa_id.startswith("Order"):
        urls = [
            f"https://www.faa.gov/documentLibrary/media/Order/{faa_id.replace('Order ', '').replace('.', '_')}.pdf",
        ]
    else:
        urls = []

    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ExtractorCorpusBuilder/1.0"})
            with urllib.request.urlopen(req, timeout=60) as response:
                content = response.read()

            if len(content) > 10000 and content[:4] == b"%PDF":
                output_path.write_bytes(content)
                return output_path
        except Exception:
            continue

    return None


# =============================================================================
# RTCA/EUROCAE Aerospace Standards (public versions/summaries)
# =============================================================================

RTCA_DOCUMENTS = [
    ("DO-178C", "Software Considerations in Airborne Systems"),
    ("DO-254", "Design Assurance Guidance for Airborne Electronic Hardware"),
    ("DO-278A", "Software Integrity Assurance for CNS/ATM"),
    ("DO-326A", "Airworthiness Security Process Specification"),
    ("DO-330", "Software Tool Qualification Considerations"),
    ("DO-331", "Model-Based Development and Verification"),
    ("DO-332", "Object-Oriented Technology and Related Techniques"),
    ("DO-333", "Formal Methods Supplement to DO-178C"),
    ("DO-297", "Integrated Modular Avionics Development"),
    ("DO-160G", "Environmental Conditions and Test Procedures"),
    ("DO-200B", "Standards for Processing Aeronautical Data"),
    ("DO-248C", "Supporting Information for DO-178C and DO-278A"),
]


# =============================================================================
# IEEE Aerospace Standards
# =============================================================================

IEEE_AEROSPACE_STANDARDS = [
    ("IEEE 12207", "Software Life Cycle Processes"),
    ("IEEE 15288", "System Life Cycle Processes"),
    ("IEEE 1012", "Software Verification and Validation"),
    ("IEEE 829", "Software Test Documentation"),
    ("IEEE 730", "Software Quality Assurance"),
    ("IEEE 1016", "Software Design Descriptions"),
    ("IEEE 1028", "Software Reviews and Audits"),
    ("IEEE 1058", "Software Project Management Plans"),
    ("IEEE 1062", "Software Acquisition"),
    ("IEEE 1471", "Architecture Description"),
    ("IEEE 1220", "Systems Engineering Process"),
    ("IEEE 15026", "Systems Assurance"),
]


# =============================================================================
# SAE International Standards
# =============================================================================

SAE_STANDARDS = [
    ("ARP4754A", "Development of Civil Aircraft and Systems"),
    ("ARP4761", "Safety Assessment Process"),
    ("ARP5150", "Safety Assessment of Transport Airplanes"),
    ("J3061", "Cybersecurity Guidebook for Cyber-Physical Vehicles"),
    ("AS9100D", "Quality Management Systems"),
    ("AS9102B", "First Article Inspection"),
    ("AS9103", "Variation Management of Key Characteristics"),
    ("AS9110C", "Quality Management - Maintenance"),
    ("AS9145", "Requirements for APQP and PPAP"),
]


def collect_industry_standards(count: int) -> List[Dict]:
    """Collect industry standards metadata (many require purchase, but summaries may be available)."""
    docs = []

    # RTCA
    for doc_id, title in RTCA_DOCUMENTS:
        docs.append({
            "id": f"RTCA_{doc_id}",
            "title": f"RTCA {doc_id}: {title}",
            "source": "industry",
            "doc_type": "rtca_standard",
        })

    # IEEE
    for doc_id, title in IEEE_AEROSPACE_STANDARDS:
        docs.append({
            "id": doc_id.replace(" ", "_"),
            "title": f"{doc_id}: {title}",
            "source": "industry",
            "doc_type": "ieee_standard",
        })

    # SAE
    for doc_id, title in SAE_STANDARDS:
        docs.append({
            "id": f"SAE_{doc_id}",
            "title": f"SAE {doc_id}: {title}",
            "source": "industry",
            "doc_type": "sae_standard",
        })

    return docs[:count]


# =============================================================================
# DTIC (Defense Technical Information Center) - Public Documents
# =============================================================================

def search_dtic(query: str, max_results: int = 50) -> List[Dict]:
    """Search DTIC for public defense documents."""
    # DTIC public search
    base_url = "https://discover.dtic.mil/search/"

    # Note: DTIC requires authentication for full access
    # This searches publicly available abstracts/metadata

    docs = []
    # DTIC doesn't have a simple API, would need web scraping
    # For now, return curated list of known public documents

    return docs


DTIC_PUBLIC_DOCS = [
    # Systems Engineering Handbooks
    ("ADA566839", "NASA Systems Engineering Handbook"),
    ("ADA586478", "DoD Systems Engineering Fundamentals"),
    ("ADA566792", "INCOSE Systems Engineering Handbook"),

    # Technical Reports
    ("ADA556789", "Cybersecurity Best Practices"),
    ("ADA567123", "Software Assurance Guide"),
    ("ADA578901", "Agile Software Development in DoD"),
]


def collect_dtic_documents(count: int) -> List[Dict]:
    """Collect DTIC public documents."""
    docs = []

    for accession, title in DTIC_PUBLIC_DOCS[:count]:
        docs.append({
            "id": accession,
            "title": title,
            "source": "dtic",
            "accession_number": accession,
        })

    return docs


def download_dtic_document(doc: Dict, output_dir: Path) -> Optional[Path]:
    """Download from DTIC (public documents only)."""
    accession = doc.get("accession_number", "")
    output_path = output_dir / f"dtic_{accession}.pdf"

    if output_path.exists():
        return output_path

    # DTIC full-text download URL (public documents)
    url = f"https://apps.dtic.mil/sti/pdfs/{accession}.pdf"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ExtractorCorpusBuilder/1.0"})
        with urllib.request.urlopen(req, timeout=60) as response:
            content = response.read()

        if len(content) > 10000 and content[:4] == b"%PDF":
            output_path.write_bytes(content)
            return output_path
    except Exception as e:
        logger.debug(f"Failed to download DTIC {accession}: {e}")

    return None


# =============================================================================
# Internet Archive - Vintage/Scanned Military Industrial Complex Documents
# =============================================================================

ARCHIVE_ORG_COLLECTIONS = [
    # ==========================================================================
    # Military Technical Manuals (scanned, often poor OCR)
    # ==========================================================================
    "us-military-manuals",
    "militaryindustrialcomplex",
    "declassified_documents",
    "military_manuals",
    "armytechnicalmanuals",
    "navytechnicalmanuals",
    "airforcetechnicalmanuals",

    # ==========================================================================
    # NASA / Space Programs
    # ==========================================================================
    "nasa_techdocs",
    "nasatechnicalreports",
    "apollo_mission_reports",
    "nasa",
    "space_shuttle_documents",
    "jaboratory",  # JPL documents

    # ==========================================================================
    # Defense Contractors / Aerospace Industry
    # ==========================================================================
    "boeingmanuals",
    "lockheedmartin",
    "aviationweek",
    "aerospace_documents",

    # ==========================================================================
    # Nuclear / Energy
    # ==========================================================================
    "nucleardocuments",
    "atomicenergy",
    "doe_documents",

    # ==========================================================================
    # Government Technical Archives
    # ==========================================================================
    "us_government_documents",
    "governmentpublicationoffice",
    "ntis",  # National Technical Information Service
    "defense_technical_information",

    # ==========================================================================
    # Engineering Standards / Specifications
    # ==========================================================================
    "mil_standards",
    "engineering_standards",
    "technical_specifications",
]

ARCHIVE_ORG_QUERIES = [
    # ==========================================================================
    # Fighter Aircraft Programs (multi-vendor, complex avionics)
    # ==========================================================================
    "F-16 technical manual",
    "F-15 avionics specification",
    "F-14 Tomcat maintenance",
    "F-4 Phantom systems",
    "F-111 flight manual",
    "A-10 Thunderbolt technical",
    "fighter aircraft interface control",
    "aircraft weapon system integration",
    "cockpit avionics design",
    "flight control computer specification",

    # ==========================================================================
    # Tank / Ground Vehicle Programs
    # ==========================================================================
    "M1 Abrams technical manual",
    "Bradley fighting vehicle specification",
    "tank fire control system",
    "armored vehicle electronics",
    "ground vehicle power system",
    "military vehicle maintenance manual",

    # ==========================================================================
    # Space Programs (NASA, DoD satellites)
    # ==========================================================================
    "space shuttle technical manual",
    "shuttle orbiter systems",
    "Apollo spacecraft specification",
    "Gemini program documentation",
    "satellite system design",
    "launch vehicle interface",
    "spacecraft power system",
    "orbital mechanics handbook",
    "space station module specification",

    # ==========================================================================
    # Nuclear Programs (power plants, naval reactors)
    # ==========================================================================
    "nuclear reactor design",
    "nuclear power plant specification",
    "reactor safety analysis",
    "nuclear instrumentation control",
    "radiation protection manual",
    "nuclear submarine reactor",
    "atomic energy technical",

    # ==========================================================================
    # Missile / Weapons Systems
    # ==========================================================================
    "missile guidance system",
    "Minuteman technical manual",
    "Patriot missile specification",
    "cruise missile design",
    "ballistic missile defense",
    "weapons system integration",
    "fire control radar",

    # ==========================================================================
    # Naval Systems (ships, submarines)
    # ==========================================================================
    "naval ship systems",
    "submarine combat system",
    "Aegis weapon system",
    "sonar system specification",
    "ship propulsion design",
    "naval electronics manual",

    # ==========================================================================
    # Large Infrastructure (multi-vendor complexity)
    # ==========================================================================
    "power grid control system",
    "air traffic control specification",
    "telecommunications system design",
    "railroad signaling system",

    # ==========================================================================
    # Engineering Documentation Types (complex layouts, tables)
    # ==========================================================================
    "interface control document",
    "system specification MIL-STD",
    "requirements traceability matrix",
    "configuration management plan",
    "test procedure specification",
    "failure mode effects analysis",
    "system safety assessment",
    "qualification test report",
    "engineering change proposal",

    # ==========================================================================
    # Vintage Scanned Documents (OCR challenges)
    # ==========================================================================
    "technical manual 1960s",
    "engineering specification 1970s",
    "military handbook 1980s",
    "aerospace design document scanned",
    "systems engineering vintage",

    # ==========================================================================
    # DOORS / Requirements Management Tool Exports
    # These are NOTORIOUS for broken PDFs - hierarchical tables, traceability
    # matrices, deeply nested structures that break on export
    # ==========================================================================
    "DOORS requirements export",
    "DOORS traceability matrix",
    "IBM DOORS module",
    "requirements management export",
    "Polarion requirements",
    "Jama requirements specification",
    "ReqIF requirements interchange",
    "requirements traceability matrix",
    "hierarchical requirements document",
    "system requirements specification SRS",
    "software requirements specification",
    "interface requirements document IRD",
    "derived requirements allocation",

    # ==========================================================================
    # ADVERSARIAL BY ACCIDENT - Documents likely broken by format churn
    # These are 1000+ page specs that went through Word→PDF→Word→PDF cycles
    # ==========================================================================
    # Large comprehensive specs (high page count)
    "system specification volume",
    "comprehensive design document",
    "complete technical manual",
    "full system description",
    "program documentation set",

    # Multi-volume / multi-part documents
    "volume 1 system specification",
    "part 1 requirements",
    "book 1 design",
    "appendix technical data",
    "annex specification",

    # Documents with complex tables (often broken by conversions)
    "data item description",
    "parts list technical",
    "bill of materials",
    "wiring diagram manual",
    "schematic parts catalog",

    # Configuration-managed documents (many revisions = many conversions)
    "revision history specification",
    "change notice engineering",
    "modification instruction",
    "configuration status accounting",

    # Government acquisition docs (notoriously complex formatting)
    "contract data requirements list",
    "statement of work technical",
    "specification tree",
    "work breakdown structure",
    "integrated master schedule",

    # Legacy system documentation (format conversion hell)
    "legacy system interface",
    "migration documentation",
    "system modernization",
    "technology refresh",

    # ==========================================================================
    # INDUSTRIAL SECTORS - Diverse infrastructure documentation
    # ==========================================================================

    # Chemical / Petrochemical Industry
    "chemical plant design manual",
    "petrochemical process specification",
    "refinery operations manual",
    "process safety management PSM",
    "hazardous materials handling",
    "chemical reactor design",
    "distillation column specification",
    "piping instrumentation diagram",

    # Automotive Industry
    "automotive manufacturing specification",
    "vehicle assembly process",
    "automotive electronics design",
    "engine control module specification",
    "automotive safety standard",
    "powertrain design manual",
    "chassis system specification",
    "automotive FMEA analysis",

    # Semiconductor / Chip Manufacturing
    "semiconductor fabrication manual",
    "integrated circuit design",
    "cleanroom specification",
    "wafer processing documentation",
    "chip manufacturing process",
    "VLSI design handbook",
    "semiconductor equipment specification",
    "IC packaging design",

    # Energy / Power Generation
    "power plant design manual",
    "turbine generator specification",
    "electrical grid design",
    "substation equipment manual",
    "power transmission specification",
    "renewable energy system design",
    "solar panel installation manual",
    "wind turbine specification",

    # Oil & Gas Industry
    "offshore platform design",
    "drilling operations manual",
    "pipeline specification",
    "oil refinery process",
    "natural gas processing",
    "wellhead equipment specification",
    "subsea systems design",

    # Pharmaceutical / Biotech
    "pharmaceutical manufacturing GMP",
    "drug production specification",
    "cleanroom validation protocol",
    "biotech process design",
    "FDA compliance documentation",
    "pharmaceutical equipment qualification",

    # Heavy Industry / Mining
    "mining equipment specification",
    "steel mill process manual",
    "foundry operations documentation",
    "metallurgical process design",
    "ore processing specification",

    # Construction / Civil Infrastructure
    "bridge design specification",
    "structural engineering manual",
    "highway construction standard",
    "dam design documentation",
    "tunnel construction specification",
    "building systems design",

    # Telecommunications
    "telecommunications network design",
    "fiber optic installation manual",
    "cellular network specification",
    "data center design",
    "network equipment specification",

    # Water / Wastewater
    "water treatment plant design",
    "wastewater processing manual",
    "pump station specification",
    "water distribution system",
]


def search_internet_archive(
    query: str,
    collection: str = None,
    max_results: int = 50,
    min_pages: int = 0,
    prefer_large: bool = False,
) -> List[Dict]:
    """
    Search Internet Archive for vintage PDFs.

    Args:
        query: Search terms
        collection: Specific collection to search
        max_results: Maximum results to return
        min_pages: Minimum page count (for finding large documents)
        prefer_large: Sort by size descending to get large/complex docs
    """
    base_url = "https://archive.org/advancedsearch.php"

    # Build search query - target PDFs, preferably large ones
    search_terms = f'mediatype:texts AND format:PDF AND ({query})'
    if collection:
        search_terms += f' AND collection:{collection}'

    # Sort by item size to get large complex documents (more likely to be broken)
    sort_field = "item_size desc" if prefer_large else "downloads desc"

    params = {
        "q": search_terms,
        "fl[]": ["identifier", "title", "year", "collection", "item_size"],
        "sort[]": sort_field,
        "rows": max_results,
        "page": 1,
        "output": "json",
    }

    url = f"{base_url}?{urllib.parse.urlencode(params, doseq=True)}"

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "ExtractorCorpusBuilder/1.0",
            "Accept": "application/json",
        })

        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))

        papers = []
        for item in data.get("response", {}).get("docs", []):
            identifier = item.get("identifier")
            if identifier:
                papers.append({
                    "id": f"archive_{identifier}",
                    "title": item.get("title", "Unknown")[:100],
                    "year": item.get("year"),
                    "source": "archive_org",
                    "identifier": identifier,
                    "collection": item.get("collection", []),
                    "doc_type": "vintage_scanned",
                })

        return papers
    except Exception as e:
        logger.warning(f"Internet Archive search failed: {e}")
        return []


def collect_archive_documents(count: int) -> List[Dict]:
    """
    Collect vintage/scanned documents from Internet Archive.

    Strategy: Prioritize LARGE documents (1000+ pages) that are likely to have
    gone through multiple Word→PDF→Word→PDF conversion cycles over 20+ years.
    These are the "adversarial by accident" documents that break extractors.
    """
    papers = []
    seen_ids = set()

    # PHASE 1: Search for LARGE documents first (prefer_large=True)
    # These are most likely to be complex multi-volume specs with conversion damage
    large_doc_queries = [
        "system specification volume",
        "comprehensive technical manual",
        "complete design document",
        "full requirements specification",
        "program documentation complete",
        "contract data requirements",
        "interface control document",
    ]

    logger.info("  Phase 1: Searching for LARGE complex documents...")
    for query in large_doc_queries:
        if len(papers) >= count // 2:  # Get half from large docs
            break

        results = search_internet_archive(
            query,
            max_results=30,
            prefer_large=True,  # Sort by size to get the monsters
        )

        for item in results:
            if item["id"] not in seen_ids and len(papers) < count:
                # Tag as potentially adversarial
                item["complexity_hint"] = "large_document"
                seen_ids.add(item["id"])
                papers.append(item)

        time.sleep(1)

    # PHASE 2: Search by collection for vintage scanned docs
    logger.info("  Phase 2: Searching vintage collections...")
    for collection in ARCHIVE_ORG_COLLECTIONS[:10]:
        if len(papers) >= count * 0.75:
            break

        for query in ARCHIVE_ORG_QUERIES[:10]:
            if len(papers) >= count * 0.75:
                break

            logger.info(f"  Searching archive.org collection={collection} for '{query}'...")
            results = search_internet_archive(query, collection=collection, max_results=20)

            for item in results:
                if item["id"] not in seen_ids and len(papers) < count:
                    item["complexity_hint"] = "vintage_scanned"
                    seen_ids.add(item["id"])
                    papers.append(item)

            time.sleep(1)

    # PHASE 3: General adversarial queries for remaining slots
    logger.info("  Phase 3: Searching for adversarial-by-accident documents...")
    for query in ARCHIVE_ORG_QUERIES:
        if len(papers) >= count:
            break

        results = search_internet_archive(query, max_results=30)

        for item in results:
            if item["id"] not in seen_ids and len(papers) < count:
                seen_ids.add(item["id"])
                papers.append(item)

        time.sleep(1)

    logger.info(f"  Collected {len(papers)} archive.org documents")
    return papers[:count]


def download_archive_document(doc: Dict, output_dir: Path) -> Optional[Path]:
    """Download PDF from Internet Archive."""
    identifier = doc.get("identifier", "")
    output_path = output_dir / f"archive_{identifier}.pdf"

    if output_path.exists():
        return output_path

    # Internet Archive download URL
    url = f"https://archive.org/download/{identifier}/{identifier}.pdf"

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "ExtractorCorpusBuilder/1.0",
        })
        with urllib.request.urlopen(req, timeout=120) as response:
            content = response.read()

        if len(content) > 10000 and content[:4] == b"%PDF":
            output_path.write_bytes(content)
            return output_path
    except Exception as e:
        # Try alternate URL pattern
        try:
            # Some items have the PDF with a different name
            alt_url = f"https://archive.org/download/{identifier}/{identifier}_text.pdf"
            req = urllib.request.Request(alt_url, headers={
                "User-Agent": "ExtractorCorpusBuilder/1.0",
            })
            with urllib.request.urlopen(req, timeout=120) as response:
                content = response.read()

            if len(content) > 10000 and content[:4] == b"%PDF":
                output_path.write_bytes(content)
                return output_path
        except Exception:
            pass

        logger.debug(f"Failed to download archive.org {identifier}: {e}")

    return None


# =============================================================================
# GPO (Government Publishing Office) - Historical Federal Documents
# =============================================================================

GPO_COLLECTIONS = [
    # Congressional and federal reports
    "CRPT",  # Congressional Reports
    "CHRG",  # Congressional Hearings
    "GAOREPORTS",  # GAO Reports
    "DODPUBS",  # Department of Defense Publications
]

GPO_QUERIES = [
    # Military Industrial Complex - government perspective
    "defense acquisition",
    "military procurement",
    "weapons system",
    "aerospace contract",
    "satellite program",
    # Complex documents with tables/figures
    "budget estimate",
    "cost analysis",
    "technical assessment",
]


def collect_gpo_documents(count: int) -> List[Dict]:
    """Collect historical documents from GPO (Government Publishing Office)."""
    docs = []

    # GPO doesn't have a simple search API, so use known document series
    # These are typically scanned and have complex layouts

    gpo_known_docs = [
        # Defense acquisition reports
        ("GAO-21-145", "Weapon Systems Annual Assessment"),
        ("GAO-20-386", "Defense Acquisitions Status Report"),
        ("GAO-19-336SP", "Defense Contractor Workforce"),
        # Congressional hearings on defense
        ("CHRG-117shrg46789", "Armed Services Subcommittee Hearing"),
        ("CHRG-116hhrg38456", "Defense Industrial Base Hearing"),
        # Budget documents (complex tables)
        ("BUDGET-2021-DOD", "Department of Defense Budget Overview"),
    ]

    for doc_id, title in gpo_known_docs[:count]:
        docs.append({
            "id": f"gpo_{doc_id}",
            "title": title,
            "source": "gpo",
            "gpo_id": doc_id,
            "doc_type": "government_report",
        })

    return docs


def download_gpo_document(doc: Dict, output_dir: Path) -> Optional[Path]:
    """Download from GPO (Government Publishing Office)."""
    gpo_id = doc.get("gpo_id", "")
    output_path = output_dir / f"gpo_{gpo_id}.pdf"

    if output_path.exists():
        return output_path

    # Try multiple GPO URL patterns
    urls = [
        f"https://www.govinfo.gov/content/pkg/{gpo_id}/pdf/{gpo_id}.pdf",
        f"https://www.gao.gov/assets/{gpo_id}.pdf",
    ]

    for url in urls:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "ExtractorCorpusBuilder/1.0",
            })
            with urllib.request.urlopen(req, timeout=60) as response:
                content = response.read()

            if len(content) > 10000 and content[:4] == b"%PDF":
                output_path.write_bytes(content)
                return output_path
        except Exception:
            continue

    logger.debug(f"Failed to download GPO {gpo_id}")
    return None


# =============================================================================
# Main Download Orchestrator
# =============================================================================

def download_source(source: str, count: int, output_dir: Path) -> Dict[str, Any]:
    """Download PDFs from a specific source."""
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {
        "source": source,
        "requested": count,
        "collected": 0,
        "downloaded": 0,
        "failed": 0,
        "skipped": 0,
    }

    # Collect metadata
    logger.info(f"Collecting {source} metadata...")

    if source == "arxiv":
        items = collect_arxiv_papers(count)
        download_fn = lambda item: download_arxiv_paper(item["id"], output_dir)
    elif source == "nist":
        items = collect_nist_publications(count)
        download_fn = lambda item: download_nist_publication(item, output_dir)
    elif source == "ietf":
        items = collect_ietf_rfcs(count)
        download_fn = lambda item: download_ietf_rfc(item, output_dir)
    elif source == "nasa":
        items = collect_nasa_reports(count)
        download_fn = lambda item: download_nasa_report(item, output_dir)
    elif source == "government":
        items = collect_government_docs(count)
        download_fn = lambda item: None  # Manual download needed for DOD docs
    elif source == "defense":
        items = collect_defense_papers(count)
        download_fn = lambda item: download_arxiv_paper(item["id"], output_dir)
    elif source == "faa":
        items = collect_faa_documents(count)
        download_fn = lambda item: download_faa_document(item, output_dir)
    elif source == "dtic":
        items = collect_dtic_documents(count)
        download_fn = lambda item: download_dtic_document(item, output_dir)
    elif source == "industry":
        # Search archive.org for industrial sectors
        items = []
        # Industrial sector queries start around line 1400
        industrial_queries = [q for q in ARCHIVE_ORG_QUERIES if any(word in q for word in ["plant", "refinery", "automotive", "manufacturing", "semiconductor", "energy", "oil", "gas", "pharma", "mining", "construction", "telecommunications", "water"])]
        for query in industrial_queries:
            if len(items) >= count:
                break
            logger.info(f"  Searching archive.org for industry: '{query}'...")
            items.extend(search_internet_archive(query, max_results=10))
        download_fn = lambda item: download_archive_document(item, output_dir)
    elif source == "archive_org":
        items = collect_archive_documents(count)
        download_fn = lambda item: download_archive_document(item, output_dir)
    elif source == "gpo":
        items = collect_gpo_documents(count)
        download_fn = lambda item: download_gpo_document(item, output_dir)
    else:
        logger.error(f"Unknown source: {source}")
        return results

    results["collected"] = len(items)
    logger.info(f"Found {len(items)} items from {source}")

    # Download with progress
    for i, item in enumerate(items):
        if (i + 1) % 10 == 0:
            logger.info(f"  Progress: {i+1}/{len(items)} ({results['downloaded']} downloaded)")

        try:
            path = download_fn(item)
            if path and path.exists():
                results["downloaded"] += 1

                # Classify with Federated Taxonomy
                taxonomy = classify_document_taxonomy(
                    source=source,
                    doc_id=item.get("id", "unknown"),
                    title=item.get("title", ""),
                    doc_type=item.get("doc_type"),
                )

                # Record in manifest with taxonomy
                record = {
                    **item,
                    "path": str(path),
                    "size": path.stat().st_size,
                    "downloaded_at": datetime.utcnow().isoformat(),
                    "taxonomy": taxonomy,
                }
                with open(MANIFEST_FILE, "a") as f:
                    f.write(json.dumps(record) + "\n")
            else:
                results["failed"] += 1
        except Exception as e:
            logger.debug(f"Error downloading {item.get('id', '?')}: {e}")
            results["failed"] += 1

        time.sleep(RATE_LIMITS.get(source, 1.0))

    return results


# =============================================================================
# CLI Commands
# =============================================================================

@app.command()
def download(
    source: str = typer.Option("all", "--source", "-s",
        help="Source: arxiv, nist, ietf, nasa, defense, faa, dtic, government, industry, all"),
    count: int = typer.Option(1000, "--count", "-c", help="Number of PDFs to download"),
    defense_focus: bool = typer.Option(False, "--defense", "-d", help="Focus on defense/aerospace sources"),
):
    """Download PDFs from specified source(s)."""
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)

    if defense_focus:
        # Military Industrial Complex focus (including scanned/vintage)
        sources = ["defense", "faa", "dtic", "nasa", "nist", "archive_org", "gpo"]
    elif source == "all":
        # Comprehensive cross-industry and MIC coverage (new and scanned)
        sources = ["arxiv", "nist", "ietf", "nasa", "defense", "faa", "dtic", "archive_org", "gpo", "industry"]
    else:
        sources = [source]

    per_source = count // len(sources) if source == "all" or defense_focus else count

    total_results = {"downloaded": 0, "failed": 0}

    for src in sources:
        output_dir = CORPUS_ROOT / src
        logger.info(f"\n{'='*60}")
        logger.info(f"Downloading from {src.upper()} (target: {per_source})")
        logger.info(f"{'='*60}")

        results = download_source(src, per_source, output_dir)
        total_results["downloaded"] += results["downloaded"]
        total_results["failed"] += results["failed"]

        logger.info(f"  {src}: {results['downloaded']} downloaded, {results['failed']} failed")

    logger.info(f"\n{'='*60}")
    logger.info(f"TOTAL: {total_results['downloaded']} downloaded, {total_results['failed']} failed")
    logger.info(f"{'='*60}")


@app.command()
def status():
    """Show corpus status."""
    print("\n" + "="*60)
    print("CORPUS STATUS")
    print("="*60)

    total = 0
    for source_dir in ["arxiv", "nist", "ietf", "nasa", "government", "stress_test_pdfs"]:
        path = CORPUS_ROOT / source_dir
        if path.exists():
            pdfs = list(path.glob("*.pdf"))
            count = len(pdfs)
            size = sum(p.stat().st_size for p in pdfs) / (1024*1024*1024)  # GB
            print(f"  {source_dir:20} {count:>6} PDFs  ({size:.2f} GB)")
            total += count

    print("-"*60)
    print(f"  {'TOTAL':20} {total:>6} PDFs")
    print("="*60)


@app.command()
def daemon(
    interval_hours: int = typer.Option(24, "--interval", "-i", help="Hours between download runs"),
    count_per_run: int = typer.Option(100, "--count", "-c", help="PDFs per run"),
):
    """Run continuous learning daemon."""
    logger.info(f"Starting corpus daemon (interval: {interval_hours}h, count: {count_per_run})")

    while True:
        try:
            # Rotate through sources
            sources = ["arxiv", "nist", "ietf", "nasa"]
            source = random.choice(sources)

            logger.info(f"Daemon run: downloading {count_per_run} from {source}")
            download_source(source, count_per_run, CORPUS_ROOT / source)

        except Exception as e:
            logger.error(f"Daemon error: {e}")

        logger.info(f"Sleeping for {interval_hours} hours...")
        time.sleep(interval_hours * 3600)


if __name__ == "__main__":
    app()
