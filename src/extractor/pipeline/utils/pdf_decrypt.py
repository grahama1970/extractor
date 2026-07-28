"""
PDF Decryption Utilities
------------------------
Handle encrypted/password-protected PDFs with multiple strategies:
1. Common password dictionary (fast, always tried first)
2. Wordlist/dictionary attack (if wordlist file provided)
3. pikepdf direct (reliable, widely available)
4. pdferli library (fast parallel cracking)
5. PyMuPDF brute-force fallback (simple numeric passwords)
6. pdf2john hash extraction (for offline GPU cracking with hashcat)

Ported from fetcher project with extractor-specific enhancements.

Environment Variables:
    EXTRACTOR_PDF_DECRYPT_ENABLE: Enable advanced decryption attempts (default: 1)
    EXTRACTOR_PDF_DECRYPT_CHARSET: Characters for brute-force (default: 0123456789)
    EXTRACTOR_PDF_DECRYPT_MINLEN: Minimum password length (default: 4)
    EXTRACTOR_PDF_DECRYPT_MAXLEN: Maximum password length (default: 6)
    EXTRACTOR_PDF_DECRYPT_TIMEOUT: Timeout in seconds (default: 30)
    EXTRACTOR_PDF_DECRYPT_PROCESSES: CPU cores to use (default: half of available)
    EXTRACTOR_PDF_DECRYPT_WORDLIST: Path to wordlist file (optional)

Usage:
    from extractor.pipeline.utils.pdf_decrypt import decrypt_pdf, is_encrypted

    if is_encrypted(pdf_path):
        result = decrypt_pdf(pdf_path)
        if result["success"]:
            # Use result["decrypted_path"] or result["password"]
            pass
        else:
            # Handle failure - result["error"] has details
            # Can use result["hashcat_hash"] for GPU cracking
            pass
"""

import itertools
import multiprocessing
import os
import re
import struct
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from loguru import logger

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import pikepdf
except ImportError:
    pikepdf = None


# Common passwords to try first (fast check before brute-force)
# Expanded list based on common PDF password patterns
COMMON_PASSWORDS = [
    "",  # Empty password (owner-only encryption)
    "1234",
    "12345",
    "123456",
    "1234567",
    "12345678",
    "123456789",
    "password",
    "Password",
    "PASSWORD",
    "admin",
    "Admin",
    "ADMIN",
    "0000",
    "1111",
    "9999",
    "pass",
    "test",
    "guest",
    "user",
    "root",
    "qwerty",
    "abc123",
    "letmein",
    "welcome",
    "monkey",
    "dragon",
    "master",
    "login",
    "pdf",
    "PDF",
    "secret",
    "Secret",
    # Year-based passwords
    "2020",
    "2021",
    "2022",
    "2023",
    "2024",
    "2025",
    "2026",
]

# Default wordlist locations to check
DEFAULT_WORDLIST_PATHS = [
    "/usr/share/wordlists/rockyou.txt",
    "/usr/share/wordlists/rockyou-top1000.txt",
    "/usr/share/seclists/Passwords/Common-Credentials/10k-most-common.txt",
    Path.home() / ".local/share/wordlists/rockyou-top1000.txt",
    Path.home() / "wordlists/rockyou.txt",
]


def _get_settings() -> Dict[str, Any]:
    """Get decryption settings from environment variables."""

    def _bool(name: str, default: str = "0") -> bool:
        """Return a boolean indicating the environment variable's truthiness."""
        raw = os.getenv(name, default)
        return str(raw).strip().lower() not in {"0", "false", "no", "off", ""}

    def _int(name: str, default: int) -> int:
        """Return integer from environment variable, defaulting on error."""
        try:
            return int(os.getenv(name, str(default)))
        except Exception:
            return default

    charset = os.getenv("EXTRACTOR_PDF_DECRYPT_CHARSET", "0123456789")
    processes_default = max(1, (os.cpu_count() or 2) // 2)
    wordlist = os.getenv("EXTRACTOR_PDF_DECRYPT_WORDLIST", "")

    return {
        "enable": _bool("EXTRACTOR_PDF_DECRYPT_ENABLE", "1"),  # Enabled by default
        "charset": charset,
        "minlen": _int("EXTRACTOR_PDF_DECRYPT_MINLEN", 4),
        "maxlen": _int("EXTRACTOR_PDF_DECRYPT_MAXLEN", 6),
        "processes": max(1, _int("EXTRACTOR_PDF_DECRYPT_PROCESSES", processes_default)),
        "timeout": max(1, _int("EXTRACTOR_PDF_DECRYPT_TIMEOUT", 30)),
        "verbose": _bool("EXTRACTOR_PDF_DECRYPT_VERBOSE", "0"),
        "bruteforce_limit": max(0, _int("EXTRACTOR_PDF_BRUTE_LIMIT", 50000)),
        "wordlist": wordlist,
    }


def get_encryption_info(pdf_path: Union[str, Path]) -> Dict[str, Any]:
    """Get detailed encryption information about a PDF.

    Returns dict with:
        - needs_password: True if user password required to open
        - has_restrictions: True if owner password set (copy/print restrictions)
        - can_read: True if we can read the content
        - encryption_type: None, "user", "owner", or "both"

    Owner-restricted PDFs can be read without decryption - restrictions
    are just metadata flags that compliant readers honor.
    """
    info: Dict[str, Any] = {
        "needs_password": False,
        "has_restrictions": False,
        "can_read": False,
        "encryption_type": None,
        "permissions": {},
    }

    # Try pikepdf first (more detailed info)
    if pikepdf is not None:
        try:
            with pikepdf.open(str(pdf_path)) as pdf:
                info["can_read"] = True
                # Check if there are any encryption-related restrictions
                if pdf.is_encrypted:
                    # Opened without password but still encrypted = owner-only
                    info["has_restrictions"] = True
                    info["encryption_type"] = "owner"
                    # Get permission flags
                    try:
                        info["permissions"] = {
                            "print": pdf.allow.print_highres or pdf.allow.print_lowres,
                            "copy": pdf.allow.extract_for_accessibility or pdf.allow.extract,
                            "modify": pdf.allow.modify_annotation or pdf.allow.modify_other,
                        }
                    except Exception:
                        pass
                return info
        except pikepdf._core.PasswordError:
            info["needs_password"] = True
            info["encryption_type"] = "user"  # or "both" if owner pw also set
            return info
        except Exception:
            pass  # Fall through to fitz

    # Fallback to PyMuPDF
    if fitz is not None:
        try:
            doc = fitz.open(str(pdf_path))
            info["needs_password"] = bool(getattr(doc, "needs_pass", False))

            if not info["needs_password"]:
                info["can_read"] = True
                # Check for owner restrictions via metadata
                try:
                    metadata = doc.metadata or {}
                    # PyMuPDF doesn't expose permissions directly without authenticating
                    # But if we can open it, we can read it
                    if doc.is_encrypted:
                        info["has_restrictions"] = True
                        info["encryption_type"] = "owner"
                except Exception:
                    pass
            else:
                info["encryption_type"] = "user"

            doc.close()
            return info
        except Exception as e:
            logger.warning(f"Failed to check PDF encryption: {e}")

    return info


def is_encrypted(pdf_path: Union[str, Path]) -> bool:
    """Check if a PDF requires a password to open (user password).

    NOTE: This returns False for owner-restricted PDFs since they
    can be opened and read without a password. Use get_encryption_info()
    for detailed encryption status.

    Args:
        pdf_path: Path to PDF file

    Returns:
        True if PDF requires user password to open, False otherwise
    """
    info = get_encryption_info(pdf_path)
    return info.get("needs_password", False)


def _find_wordlist() -> Optional[Path]:
    """Find an available wordlist file.

    Returns:
        Path to wordlist if found, None otherwise
    """
    settings = _get_settings()

    # Check environment variable first
    if settings.get("wordlist"):
        wl_path = Path(settings["wordlist"])
        if wl_path.exists():
            return wl_path

    # Check default locations
    for path in DEFAULT_WORDLIST_PATHS:
        path = Path(path)
        if path.exists():
            return path

    return None


def _try_common_passwords(pdf_path: Union[str, Path]) -> Tuple[Optional[str], Dict[str, Any]]:
    """Try common passwords before brute-force.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Tuple of (password if found, metadata dict)
    """
    meta: Dict[str, Any] = {
        "common_passwords_attempted": True,
        "common_passwords_count": len(COMMON_PASSWORDS),
    }

    # Try with pikepdf (preferred)
    if pikepdf is not None:
        for pwd in COMMON_PASSWORDS:
            try:
                with pikepdf.open(str(pdf_path), password=pwd):
                    meta["method"] = "pikepdf"
                    return pwd, meta
            except pikepdf._core.PasswordError:
                continue
            except Exception:
                continue

    # Fallback to PyMuPDF
    if fitz is not None:
        try:
            doc = fitz.open(str(pdf_path))
            for pwd in COMMON_PASSWORDS:
                try:
                    if doc.authenticate(pwd):
                        doc.close()
                        meta["method"] = "fitz"
                        return pwd, meta
                except Exception:
                    continue
            doc.close()
        except Exception:
            pass

    meta["found"] = False
    return None, meta


def _try_wordlist(
    pdf_path: Union[str, Path],
    wordlist_path: Optional[Path] = None,
    max_words: int = 100000,
) -> Tuple[Optional[str], Dict[str, Any]]:
    """Try passwords from a wordlist file.

    Args:
        pdf_path: Path to PDF file
        wordlist_path: Path to wordlist file (auto-detected if None)
        max_words: Maximum words to try (default 100k)

    Returns:
        Tuple of (password if found, metadata dict)
    """
    meta: Dict[str, Any] = {
        "wordlist_attempted": True,
    }

    if wordlist_path is None:
        wordlist_path = _find_wordlist()

    if wordlist_path is None:
        meta["wordlist_error"] = "no_wordlist_found"
        meta["wordlist_hint"] = "Set EXTRACTOR_PDF_DECRYPT_WORDLIST or install rockyou.txt"
        return None, meta

    meta["wordlist_path"] = str(wordlist_path)

    try:
        words_tried = 0
        with open(wordlist_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if words_tried >= max_words:
                    break
                pwd = line.strip()
                if not pwd:
                    continue
                words_tried += 1

                # Try with pikepdf
                if pikepdf is not None:
                    try:
                        with pikepdf.open(str(pdf_path), password=pwd):
                            meta["words_tried"] = words_tried
                            meta["method"] = "pikepdf"
                            return pwd, meta
                    except pikepdf._core.PasswordError:
                        continue
                    except Exception:
                        continue

                # Fallback to fitz
                elif fitz is not None:
                    try:
                        doc = fitz.open(str(pdf_path))
                        if doc.authenticate(pwd):
                            doc.close()
                            meta["words_tried"] = words_tried
                            meta["method"] = "fitz"
                            return pwd, meta
                        doc.close()
                    except Exception:
                        continue

        meta["words_tried"] = words_tried
        meta["found"] = False

    except Exception as e:
        meta["wordlist_error"] = str(e)

    return None, meta


def _crack_with_pikepdf(
    pdf_path: Union[str, Path],
    charset: str,
    minlen: int,
    maxlen: int,
    limit: int,
) -> Tuple[Optional[str], Dict[str, Any]]:
    """Brute-force PDF password using pikepdf directly.

    Args:
        pdf_path: Path to PDF file
        charset: Characters to try
        minlen: Minimum password length
        maxlen: Maximum password length
        limit: Maximum attempts

    Returns:
        Tuple of (password or None, metadata dict)
    """
    meta: Dict[str, Any] = {
        "pikepdf_bruteforce_attempted": True,
        "charset": charset,
        "minlen": minlen,
        "maxlen": maxlen,
        "limit": limit,
    }

    if pikepdf is None:
        meta["pikepdf_error"] = "not_installed"
        meta["pikepdf_hint"] = "Install with: pip install pikepdf"
        return None, meta

    charset = "".join(dict.fromkeys(charset))
    if not charset:
        meta["pikepdf_error"] = "empty_charset"
        return None, meta

    # Calculate search space
    total_space = 0
    for length in range(max(1, minlen), max(minlen, maxlen) + 1):
        try:
            total_space += len(charset) ** length
        except OverflowError:
            total_space = limit + 1
            break

    meta["search_space"] = total_space
    if limit > 0 and total_space > limit:
        meta["pikepdf_skipped"] = "limit_exceeded"
        return None, meta

    attempts = 0
    for length in range(max(1, minlen), max(minlen, maxlen) + 1):
        for combo in itertools.product(charset, repeat=length):
            attempts += 1
            if attempts > limit:
                break
            candidate = "".join(combo)
            try:
                with pikepdf.open(str(pdf_path), password=candidate):
                    meta["attempts"] = attempts
                    return candidate, meta
            except pikepdf._core.PasswordError:
                continue
            except Exception:
                continue

    meta["attempts"] = attempts
    meta["found"] = False
    return None, meta


def _brute_force_password(
    raw_bytes: bytes,
    charset: str,
    minlen: int,
    maxlen: int,
    limit: int,
) -> Tuple[Optional[str], Dict[str, Any]]:
    """Brute-force PDF password using PyMuPDF.

    Args:
        raw_bytes: PDF file contents
        charset: Characters to try
        minlen: Minimum password length
        maxlen: Maximum password length
        limit: Maximum attempts before giving up

    Returns:
        Tuple of (password or None, metadata dict)
    """
    meta: Dict[str, Any] = {
        "bruteforce_attempted": True,
        "bruteforce_limit": limit,
    }

    if limit <= 0:
        meta["bruteforce_skipped"] = "disabled"
        return None, meta

    if fitz is None:
        meta["bruteforce_error"] = "pymupdf_missing"
        return None, meta

    charset = "".join(dict.fromkeys(charset))  # Remove duplicates
    if not charset:
        meta["bruteforce_error"] = "empty_charset"
        return None, meta

    # Calculate search space
    total_space = 0
    for length in range(max(1, minlen), max(minlen, maxlen) + 1):
        try:
            total_space += len(charset) ** length
        except OverflowError:
            total_space = limit + 1
            break

    meta["bruteforce_space"] = total_space
    if limit > 0 and total_space > limit:
        meta["bruteforce_skipped"] = "limit_exceeded"
        return None, meta

    try:
        doc = fitz.open(stream=raw_bytes, filetype="pdf")
    except Exception as exc:
        meta["bruteforce_error"] = f"open_failed:{exc}"
        return None, meta

    attempts = 0
    try:
        for length in range(max(1, minlen), max(minlen, maxlen) + 1):
            for combo in itertools.product(charset, repeat=length):
                attempts += 1
                candidate = "".join(combo)
                try:
                    if doc.authenticate(candidate):
                        meta["bruteforce_attempts"] = attempts
                        return candidate, meta
                except Exception:
                    continue
    finally:
        doc.close()

    meta["bruteforce_attempts"] = attempts
    meta["bruteforce_failed"] = True
    return None, meta


def _crack_with_pdferli(
    pdf_path: Union[str, Path],
    settings: Dict[str, Any],
) -> Tuple[Optional[str], Dict[str, Any]]:
    """Attempt to crack password using pdferli library (parallel).

    Args:
        pdf_path: Path to encrypted PDF
        settings: Decryption settings dict

    Returns:
        Tuple of (password or None, metadata dict)
    """
    meta: Dict[str, Any] = {
        "pdferli_attempted": True,
        "charset": settings.get("charset"),
        "minlen": settings.get("minlen"),
        "maxlen": settings.get("maxlen"),
    }

    try:
        from pdferli import crack_password  # type: ignore
    except ImportError as exc:
        meta["pdferli_error"] = f"not_installed: {exc}"
        meta["pdferli_hint"] = "Install with: pip install pdferli>=0.11"
        return None, meta

    charset = str(settings.get("charset") or "")
    if not charset:
        meta["pdferli_error"] = "empty_charset"
        return None, meta

    timeout = int(settings.get("timeout", 30))
    minlen = int(settings.get("minlen", 1))
    maxlen = int(settings.get("maxlen", minlen))
    processes = int(settings.get("processes", 1))
    verbose = bool(settings.get("verbose"))

    def _worker(path: str, queue: multiprocessing.Queue) -> None:
        """Execute password cracking and place result in a queue."""
        try:
            pwd = crack_password(
                file=path,
                chars=charset,
                minlen=minlen,
                maxlen=maxlen,
                processes=processes,
                verbose=verbose,
            )
            queue.put({"password": pwd})
        except Exception as exc:
            queue.put({"error": str(exc)})

    queue: multiprocessing.Queue = multiprocessing.Queue()
    start = time.perf_counter()
    proc = multiprocessing.Process(target=_worker, args=(str(pdf_path), queue))
    proc.start()
    proc.join(timeout)

    if proc.is_alive():
        proc.terminate()
        proc.join()
        meta["pdferli_timeout"] = True
        meta["pdferli_ms"] = int((time.perf_counter() - start) * 1000)
        return None, meta

    result = queue.get() if not queue.empty() else {}
    meta["pdferli_ms"] = int((time.perf_counter() - start) * 1000)

    if "error" in result:
        meta["pdferli_error"] = result.get("error")
        return None, meta

    password = result.get("password")
    return password, meta


def extract_pdf_hash(pdf_path: Union[str, Path]) -> Tuple[Optional[str], Dict[str, Any]]:
    """Extract PDF hash for offline cracking with hashcat/john.

    This extracts the encryption parameters from the PDF so you can
    crack it offline with GPU acceleration using hashcat.

    Hashcat modes:
        - 10400: PDF 1.1-1.3 (RC4 40-bit)
        - 10500: PDF 1.4-1.6 (RC4 128-bit)
        - 10600: PDF 1.7 Level 3 (AES-128)
        - 10700: PDF 1.7 Level 8 (AES-256)

    Args:
        pdf_path: Path to encrypted PDF

    Returns:
        Tuple of (hash string for hashcat, metadata dict)
    """
    meta: Dict[str, Any] = {
        "hash_extraction_attempted": True,
    }

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        meta["error"] = "file_not_found"
        return None, meta

    try:
        content = pdf_path.read_bytes()
    except Exception as e:
        meta["error"] = f"read_failed: {e}"
        return None, meta

    # Find /Encrypt dictionary
    encrypt_match = re.search(rb"/Encrypt\s+(\d+)\s+(\d+)\s+R", content)
    if not encrypt_match:
        meta["error"] = "no_encrypt_dict"
        meta["hint"] = "PDF may not be encrypted or uses non-standard encryption"
        return None, meta

    encrypt_obj_num = int(encrypt_match.group(1))
    meta["encrypt_obj"] = encrypt_obj_num

    # Find encryption parameters
    # Look for /V (version), /R (revision), /O (owner), /U (user), /P (permissions)

    # Find the object
    obj_pattern = rb"%d\s+\d+\s+obj(.*?)endobj" % encrypt_obj_num
    obj_match = re.search(obj_pattern, content, re.DOTALL)

    if not obj_match:
        meta["error"] = "encrypt_obj_not_found"
        return None, meta

    encrypt_dict = obj_match.group(1)

    # Extract encryption version
    v_match = re.search(rb"/V\s+(\d+)", encrypt_dict)
    r_match = re.search(rb"/R\s+(\d+)", encrypt_dict)
    p_match = re.search(rb"/P\s+(-?\d+)", encrypt_dict)

    if not all([v_match, r_match, p_match]):
        meta["error"] = "missing_encryption_params"
        return None, meta

    v = int(v_match.group(1))
    r = int(r_match.group(1))
    p = int(p_match.group(1))

    meta["encryption_version"] = v
    meta["encryption_revision"] = r
    meta["permissions"] = p

    # Extract O and U strings (owner and user password hashes)
    o_match = re.search(rb"/O\s*<([0-9A-Fa-f]+)>", encrypt_dict)
    u_match = re.search(rb"/U\s*<([0-9A-Fa-f]+)>", encrypt_dict)

    if not o_match:
        o_match = re.search(rb"/O\s*\((.{32})\)", encrypt_dict, re.DOTALL)
    if not u_match:
        u_match = re.search(rb"/U\s*\((.{32})\)", encrypt_dict, re.DOTALL)

    if not (o_match and u_match):
        meta["error"] = "missing_o_u_strings"
        return None, meta

    o_value = o_match.group(1)
    u_value = u_match.group(1)

    # Convert to hex if needed
    if len(o_value) == 32:
        o_hex = o_value.hex()
    else:
        o_hex = o_value.decode("latin-1") if isinstance(o_value, bytes) else o_value

    if len(u_value) == 32:
        u_hex = u_value.hex()
    else:
        u_hex = u_value.decode("latin-1") if isinstance(u_value, bytes) else u_value

    meta["o_hash"] = o_hex[:64] if len(o_hex) > 64 else o_hex
    meta["u_hash"] = u_hex[:64] if len(u_hex) > 64 else u_hex

    # Find document ID
    id_match = re.search(rb"/ID\s*\[\s*<([0-9A-Fa-f]+)>", content)
    if id_match:
        doc_id = id_match.group(1).decode("ascii")
    else:
        id_match = re.search(rb"/ID\s*\[\s*\((.{16})\)", content, re.DOTALL)
        if id_match:
            doc_id = id_match.group(1).hex()
        else:
            meta["error"] = "missing_doc_id"
            return None, meta

    meta["doc_id"] = doc_id[:32]

    # Determine hashcat mode
    if v == 1 and r == 2:
        hashcat_mode = 10400  # PDF 1.1-1.3
        hash_format = f"$pdf$1*2*40*{p}*1*16*{doc_id[:32]}*32*{u_hex[:64]}*32*{o_hex[:64]}"
    elif v == 2 and r == 3:
        hashcat_mode = 10500  # PDF 1.4-1.6
        hash_format = f"$pdf$2*3*128*{p}*1*16*{doc_id[:32]}*32*{u_hex[:64]}*32*{o_hex[:64]}"
    elif v == 4 and r == 4:
        hashcat_mode = 10600  # PDF 1.7 AES-128
        hash_format = f"$pdf$4*4*128*{p}*1*16*{doc_id[:32]}*32*{u_hex[:64]}*32*{o_hex[:64]}"
    elif v == 5 and r in (5, 6):
        hashcat_mode = 10700  # PDF 1.7 AES-256
        hash_format = f"$pdf$5*{r}*256*{p}*1*16*{doc_id[:32]}*32*{u_hex[:64]}*32*{o_hex[:64]}"
    else:
        meta["error"] = f"unsupported_encryption: V={v}, R={r}"
        meta["hint"] = "This encryption type may not be supported by hashcat"
        return None, meta

    meta["hashcat_mode"] = hashcat_mode
    meta["hashcat_command"] = f"hashcat -m {hashcat_mode} hash.txt wordlist.txt"

    return hash_format, meta


def decrypt_pdf(
    pdf_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    password: Optional[str] = None,
    auto_decrypt: bool = True,
    wordlist_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Decrypt a password-protected PDF.

    Tries multiple strategies in order:
    1. User-provided password (if given)
    2. Common passwords dictionary (expanded list)
    3. Wordlist/dictionary attack (if wordlist available)
    4. pikepdf direct brute-force
    5. pdferli parallel cracking (if installed and enabled)
    6. PyMuPDF brute-force fallback
    7. Extract hash for hashcat (if all else fails)

    Args:
        pdf_path: Path to encrypted PDF
        output_path: Optional path for decrypted output (default: same dir with _decrypted suffix)
        password: Optional known password to try first
        auto_decrypt: Whether to attempt automatic decryption (default: True)
        wordlist_path: Optional path to wordlist file

    Returns:
        Dict with keys:
            - success: bool
            - password: str (if found)
            - decrypted_path: Path (if output written)
            - method: str (how password was found)
            - error: str (if failed)
            - hashcat_hash: str (for offline cracking if password not found)
            - metadata: dict (detailed attempt info)
    """
    pdf_path = Path(pdf_path)
    result: Dict[str, Any] = {
        "success": False,
        "source_path": str(pdf_path),
        "metadata": {},
    }

    if pikepdf is None and fitz is None:
        result["error"] = "Neither pikepdf nor PyMuPDF installed"
        return result

    if not pdf_path.exists():
        result["error"] = f"File not found: {pdf_path}"
        return result

    # Check if actually encrypted
    if not is_encrypted(pdf_path):
        result["success"] = True
        result["method"] = "not_encrypted"
        result["decrypted_path"] = str(pdf_path)
        return result

    if not auto_decrypt:
        result["error"] = "PDF is encrypted and auto_decrypt=False"
        result["metadata"]["encrypted"] = True
        return result

    settings = _get_settings()
    result["metadata"]["settings"] = settings

    # Strategy 1: User-provided password
    if password:
        if pikepdf is not None:
            try:
                with pikepdf.open(str(pdf_path), password=password):
                    result["success"] = True
                    result["password"] = password
                    result["method"] = "user_provided"
                    result["metadata"]["user_password_worked"] = True
            except pikepdf._core.PasswordError:
                result["metadata"]["user_password_worked"] = False
            except Exception as e:
                result["metadata"]["user_password_error"] = str(e)
        elif fitz is not None:
            try:
                doc = fitz.open(str(pdf_path))
                if doc.authenticate(password):
                    result["success"] = True
                    result["password"] = password
                    result["method"] = "user_provided"
                    result["metadata"]["user_password_worked"] = True
                else:
                    result["metadata"]["user_password_worked"] = False
                doc.close()
            except Exception as e:
                result["metadata"]["user_password_error"] = str(e)

    # Strategy 2: Common passwords
    if not result["success"]:
        pwd, common_meta = _try_common_passwords(pdf_path)
        result["metadata"]["common_passwords"] = common_meta
        if pwd is not None:
            result["success"] = True
            result["password"] = pwd
            result["method"] = "common_password"

    # Strategy 3: Wordlist attack
    if not result["success"] and settings.get("enable"):
        wl_path = Path(wordlist_path) if wordlist_path else None
        pwd, wordlist_meta = _try_wordlist(pdf_path, wl_path)
        result["metadata"]["wordlist"] = wordlist_meta
        if pwd is not None:
            result["success"] = True
            result["password"] = pwd
            result["method"] = "wordlist"

    # Strategy 4: pikepdf direct brute-force
    if not result["success"] and settings.get("enable") and pikepdf is not None:
        pwd, pikepdf_meta = _crack_with_pikepdf(
            pdf_path,
            settings.get("charset", "0123456789"),
            settings.get("minlen", 4),
            settings.get("maxlen", 6),
            min(settings.get("bruteforce_limit", 50000), 10000),  # Limit for direct
        )
        result["metadata"]["pikepdf_bruteforce"] = pikepdf_meta
        if pwd:
            result["success"] = True
            result["password"] = pwd
            result["method"] = "pikepdf_bruteforce"

    # Strategy 5: pdferli parallel (if available)
    if not result["success"] and settings.get("enable"):
        pwd, pdferli_meta = _crack_with_pdferli(pdf_path, settings)
        result["metadata"]["pdferli"] = pdferli_meta
        if pwd:
            result["success"] = True
            result["password"] = pwd
            result["method"] = "pdferli"

    # Strategy 6: PyMuPDF brute-force fallback
    if not result["success"] and settings.get("bruteforce_limit", 0) > 0 and fitz is not None:
        raw_bytes = pdf_path.read_bytes()
        pwd, brute_meta = _brute_force_password(
            raw_bytes,
            settings.get("charset", "0123456789"),
            settings.get("minlen", 4),
            settings.get("maxlen", 6),
            settings.get("bruteforce_limit", 50000),
        )
        result["metadata"]["bruteforce"] = brute_meta
        if pwd:
            result["success"] = True
            result["password"] = pwd
            result["method"] = "bruteforce"

    # Strategy 7: Extract hash for hashcat (if all else fails)
    if not result["success"]:
        hash_str, hash_meta = extract_pdf_hash(pdf_path)
        result["metadata"]["hash_extraction"] = hash_meta
        if hash_str:
            result["hashcat_hash"] = hash_str
            result["hashcat_mode"] = hash_meta.get("hashcat_mode")
            result["hashcat_command"] = hash_meta.get("hashcat_command")

    # Save decrypted version if successful
    if result["success"] and result.get("password") is not None:
        if output_path is None:
            output_path = pdf_path.parent / f"{pdf_path.stem}_decrypted.pdf"
        output_path = Path(output_path)

        try:
            if pikepdf is not None:
                with pikepdf.open(str(pdf_path), password=result["password"]) as pdf:
                    pdf.save(str(output_path))
            elif fitz is not None:
                doc = fitz.open(str(pdf_path))
                doc.authenticate(result["password"])
                new_doc = fitz.open()
                new_doc.insert_pdf(doc)
                new_doc.save(str(output_path), garbage=4, deflate=True)
                new_doc.close()
                doc.close()

            result["decrypted_path"] = str(output_path)
            logger.info(f"Decrypted PDF saved to: {output_path}")
        except Exception as e:
            result["metadata"]["save_error"] = str(e)
            logger.warning(f"Failed to save decrypted PDF: {e}")

    if not result["success"]:
        result["error"] = "Could not decrypt PDF - password not found"
        if result.get("hashcat_hash"):
            result["metadata"]["hint"] = (
                f"Use hashcat for GPU cracking: {result.get('hashcat_command', 'hashcat -m MODE hash.txt wordlist.txt')}"
            )
        else:
            result["metadata"]["hint"] = (
                "Enable brute-force with EXTRACTOR_PDF_DECRYPT_ENABLE=1 "
                "or provide a wordlist via EXTRACTOR_PDF_DECRYPT_WORDLIST"
            )

    return result


def decrypt_pdf_to_bytes(
    pdf_path: Union[str, Path],
    password: Optional[str] = None,
    auto_decrypt: bool = True,
) -> Tuple[Optional[bytes], Dict[str, Any]]:
    """Decrypt a PDF and return bytes (no file write).

    Args:
        pdf_path: Path to encrypted PDF
        password: Optional known password
        auto_decrypt: Whether to attempt automatic decryption

    Returns:
        Tuple of (decrypted bytes or None, result dict)
    """
    result = decrypt_pdf(pdf_path, password=password, auto_decrypt=auto_decrypt)

    if not result["success"]:
        return None, result

    try:
        if pikepdf is not None and result.get("password"):
            with pikepdf.open(str(pdf_path), password=result["password"]) as pdf:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    pdf.save(tmp.name)
                    decrypted_bytes = Path(tmp.name).read_bytes()
                    Path(tmp.name).unlink()
                    return decrypted_bytes, result
        elif fitz is not None:
            doc = fitz.open(str(pdf_path))
            if result.get("password"):
                doc.authenticate(result["password"])
            new_doc = fitz.open()
            new_doc.insert_pdf(doc)
            doc.close()
            decrypted_bytes = new_doc.tobytes(garbage=4, deflate=True)
            new_doc.close()
            return decrypted_bytes, result
        else:
            # Not encrypted, just read the file
            return Path(pdf_path).read_bytes(), result
    except Exception as e:
        result["metadata"]["tobytes_error"] = str(e)
        return None, result
