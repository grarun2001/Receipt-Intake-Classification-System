import logging

import fitz

logger = logging.getLogger("receipt_app")


class PDFProcessingError(Exception):
    """Raised when a PDF cannot be opened or processed."""


def _has_usable_text(text: str) -> bool:
    if not text:
        return False

    words = [
        word
        for word in text.split()
        if any(char.isalnum() for char in word)
    ]

    meaningful_chars = sum(
        char.isalnum() for char in text
    )

    return meaningful_chars >= 20 and len(words) >= 4


def read_pdf(pdf_bytes: bytes) -> dict:
    if not pdf_bytes:
        raise PDFProcessingError(
            "The uploaded PDF is empty."
        )

    if not pdf_bytes.startswith(b"%PDF-"):
        raise PDFProcessingError(
            "Invalid PDF signature."
        )

    try:
        document = fitz.open(
            stream=pdf_bytes,
            filetype="pdf",
        )
    except Exception as exc:
        raise PDFProcessingError(
            "Invalid or corrupt PDF."
        ) from exc

    try:
        if document.needs_pass:
            raise PDFProcessingError(
                "Password-protected PDFs are not supported."
            )

        if document.page_count == 0:
            raise PDFProcessingError(
                "The PDF contains no pages."
            )

        pages = []

        for page_index, page in enumerate(document):
            page_number = page_index + 1

            try:
                text = (
                    page.get_text("text") or ""
                ).strip()
            except Exception:
                logger.exception(
                    "Text extraction failed for page %s",
                    page_number,
                )
                text = ""

            usable_text = _has_usable_text(text)

            pages.append(
                {
                    "page_number": page_number,
                    "text": text,
                    "has_usable_text": usable_text,
                    "needs_ocr": not usable_text,
                }
            )

        needs_ocr_pages = [
            page["page_number"]
            for page in pages
            if page["needs_ocr"]
        ]

        digital_text_pages = [
            page
            for page in pages
            if page["has_usable_text"]
        ]

        source = (
            "OCR"
            if needs_ocr_pages
            else "Digital"
        )

        digital_text = "\n\n".join(
            f"[Page {page['page_number']}]\n{page['text']}"
            for page in digital_text_pages
        )

        logger.info(
            "PDF processed: pages=%s, digital_pages=%s, "
            "ocr_pages=%s, source=%s",
            document.page_count,
            len(digital_text_pages),
            len(needs_ocr_pages),
            source,
        )

        return {
            "text": digital_text,
            "source": source,
            "page_count": document.page_count,
            "pages": pages,
            "needs_ocr_pages": needs_ocr_pages,
        }

    finally:
        document.close()