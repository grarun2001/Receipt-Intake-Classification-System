import logging
from pathlib import Path

logger = logging.getLogger("receipt_app")


def validate_pdf(filename: str, content: bytes) -> tuple[bool, str]:
    """Validate the uploaded file name, extension, content and PDF signature."""

    if not filename or not filename.strip():
        return False, "Filename is missing."

    if Path(filename).suffix.lower() != ".pdf":
        logger.warning(
            "Upload rejected | filename=%s | reason=unsupported_extension",
            filename,
        )
        return False, "Only PDF files are supported."

    if not content:
        return False, "The uploaded file is empty."

    if not content.startswith(b"%PDF-"):
        logger.warning(
            "Upload rejected | filename=%s | reason=invalid_pdf_signature",
            filename,
        )
        return False, "The file does not appear to be a valid PDF."

    return True, ""