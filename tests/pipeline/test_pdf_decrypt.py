"""Tests for PDF decryption utilities."""

import fitz
import pytest

from extractor.pipeline.utils.pdf_decrypt import (
    is_encrypted,
    decrypt_pdf,
    _try_common_passwords,
    COMMON_PASSWORDS,
)


def _make_encrypted_pdf(path, password="1234"):
    """Create a simple encrypted PDF for testing."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Secret content inside encrypted PDF")
    doc.save(
        str(path),
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw=password,
        user_pw=password,
    )
    doc.close()


def _make_unencrypted_pdf(path):
    """Create a simple unencrypted PDF for testing."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Public content in unencrypted PDF")
    doc.save(str(path))
    doc.close()


def test_is_encrypted_unencrypted(tmp_path):
    """Test is_encrypted returns False for unencrypted PDFs."""
    pdf_path = tmp_path / "unencrypted.pdf"
    _make_unencrypted_pdf(pdf_path)

    assert is_encrypted(pdf_path) is False


def test_is_encrypted_encrypted(tmp_path):
    """Test is_encrypted returns True for encrypted PDFs."""
    pdf_path = tmp_path / "encrypted.pdf"
    _make_encrypted_pdf(pdf_path, password="secret123")

    assert is_encrypted(pdf_path) is True


def test_decrypt_unencrypted_pdf(tmp_path):
    """Test decrypt_pdf handles unencrypted PDFs gracefully."""
    pdf_path = tmp_path / "unencrypted.pdf"
    _make_unencrypted_pdf(pdf_path)

    result = decrypt_pdf(pdf_path)

    assert result["success"] is True
    assert result["method"] == "not_encrypted"


def test_decrypt_with_known_password(tmp_path):
    """Test decrypt_pdf with correct password provided."""
    pdf_path = tmp_path / "encrypted.pdf"
    _make_encrypted_pdf(pdf_path, password="mypassword")

    result = decrypt_pdf(pdf_path, password="mypassword")

    assert result["success"] is True
    assert result["password"] == "mypassword"
    assert result["method"] == "user_provided"


def test_decrypt_with_wrong_password(tmp_path):
    """Test decrypt_pdf with incorrect password."""
    pdf_path = tmp_path / "encrypted.pdf"
    _make_encrypted_pdf(pdf_path, password="correctpassword")

    result = decrypt_pdf(pdf_path, password="wrongpassword")

    # Should fail since wrong password and common passwords won't match
    assert result["metadata"]["user_password_worked"] is False


def test_decrypt_common_password(tmp_path):
    """Test decrypt_pdf finds common passwords."""
    pdf_path = tmp_path / "encrypted.pdf"
    # Use a password from COMMON_PASSWORDS
    _make_encrypted_pdf(pdf_path, password="1234")

    result = decrypt_pdf(pdf_path)

    assert result["success"] is True
    assert result["password"] == "1234"
    assert result["method"] == "common_password"


def test_try_common_passwords_success(tmp_path):
    """Test _try_common_passwords finds known password."""
    pdf_path = tmp_path / "encrypted.pdf"
    _make_encrypted_pdf(pdf_path, password="0000")

    found, metadata = _try_common_passwords(pdf_path)

    assert found == "0000"
    assert metadata["common_passwords_attempted"] is True
    assert "method" in metadata  # pikepdf or fitz


def test_try_common_passwords_failure(tmp_path):
    """Test _try_common_passwords returns None for unknown password."""
    pdf_path = tmp_path / "encrypted.pdf"
    _make_encrypted_pdf(pdf_path, password="verysecret999")

    found, metadata = _try_common_passwords(pdf_path)

    assert found is None
    assert metadata["found"] is False
    assert metadata["common_passwords_attempted"] is True


def test_decrypt_creates_output_file(tmp_path):
    """Test decrypt_pdf creates decrypted output file."""
    pdf_path = tmp_path / "encrypted.pdf"
    output_path = tmp_path / "decrypted_output.pdf"
    _make_encrypted_pdf(pdf_path, password="1234")

    result = decrypt_pdf(pdf_path, output_path=output_path)

    assert result["success"] is True
    assert result["decrypted_path"] == str(output_path)
    assert output_path.exists()

    # Verify decrypted file is readable without password
    doc = fitz.open(str(output_path))
    assert not doc.needs_pass
    text = doc[0].get_text()
    assert "Secret content" in text
    doc.close()


def test_decrypt_nonexistent_file(tmp_path):
    """Test decrypt_pdf handles missing files gracefully."""
    result = decrypt_pdf(tmp_path / "does_not_exist.pdf")

    assert result["success"] is False
    assert "not found" in result["error"].lower()
