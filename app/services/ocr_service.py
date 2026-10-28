import logging
from io import BytesIO

import fitz
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from app.config import TESSERACT_CMD

logger = logging.getLogger("receipt_app")

if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


class OCRProcessingError(Exception):
    """Raised when OCR processing fails."""


def _preprocess_image(image: Image.Image) -> Image.Image:
    """Improve image readability before OCR."""
    image = ImageOps.grayscale(image)
    image = ImageOps.autocontrast(image)
    image = ImageEnhance.Contrast(image).enhance(1.5)
    image = image.filter(ImageFilter.SHARPEN)
    return image


def _ocr_score(text: str, confidence: float) -> float:
    """Score OCR output using confidence and readable content."""
    if not text.strip():
        return 0.0

    characters = [
        char for char in text
        if char.isalnum()
    ]

    total_chars = max(len(text.strip()), 1)
    readable_ratio = len(characters) / total_chars

    return (
        confidence * 0.6
        + readable_ratio * 30
        + min(len(characters), 500) * 0.02
    )


def _extract_candidate(
    image: Image.Image,
    page_number: int,
    psm: int,
) -> tuple[str, float]:
    """Extract text using one Tesseract page segmentation mode."""
    try:
        data = pytesseract.image_to_data(
            image,
            lang="eng",
            config=f"--oem 3 --psm {psm}",
            output_type=pytesseract.Output.DICT,
            timeout=60,
        )

        lines = {}
        confidences = []

        for index, word in enumerate(data["text"]):
            word = word.strip()

            if not word:
                continue

            try:
                confidence = float(data["conf"][index])
            except (ValueError, TypeError):
                confidence = -1

            if confidence >= 0:
                confidences.append(confidence)

            key = (
                data["block_num"][index],
                data["par_num"][index],
                data["line_num"][index],
            )

            lines.setdefault(key, []).append(word)

        text = "\n".join(
            " ".join(words)
            for words in lines.values()
            if words
        ).strip()

        average_confidence = (
            sum(confidences) / len(confidences)
            if confidences
            else 0.0
        )

        return text, average_confidence

    except Exception:
        logger.exception(
            "OCR candidate failed for page %s using PSM %s",
            page_number,
            psm,
        )
        return "", 0.0


def _extract_page_text(
    page: fitz.Page,
    page_number: int,
) -> str:
    """Try multiple OCR layouts and select the strongest result."""
    try:
        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(2.5, 2.5),
            alpha=False,
        )

        image = Image.open(
            BytesIO(pixmap.tobytes("png"))
        ).convert("RGB")

        image = _preprocess_image(image)

    except Exception as exc:
        raise OCRProcessingError(
            f"Could not prepare page {page_number} for OCR."
        ) from exc

    best_text = ""
    best_score = 0.0

    for psm in (6, 4, 11):
        candidate, confidence = _extract_candidate(
            image,
            page_number,
            psm,
        )

        score = _ocr_score(candidate, confidence)

        if score > best_score:
            best_score = score
            best_text = candidate

    return best_text


def extract_text_with_ocr(
    pdf_bytes: bytes,
    page_numbers: list[int] | None = None,
) -> str:
    """
    Extract OCR text from a PDF.

    Args:
        pdf_bytes: Original PDF bytes.
        page_numbers: Optional 1-based page numbers.
                      None means OCR every page.

    Returns:
        Extracted text with page markers.
    """
    if not pdf_bytes:
        raise OCRProcessingError(
            "The uploaded PDF is empty."
        )

    try:
        document = fitz.open(
            stream=pdf_bytes,
            filetype="pdf",
        )
    except Exception as exc:
        raise OCRProcessingError(
            "Could not open the PDF for OCR."
        ) from exc

    try:
        if document.needs_pass:
            raise OCRProcessingError(
                "Password-protected PDFs are not supported."
            )

        if page_numbers is None:
            selected_pages = list(
                range(1, document.page_count + 1)
            )
        else:
            selected_pages = sorted(
                set(page_numbers)
            )

        for page_number in selected_pages:
            if (
                not isinstance(page_number, int)
                or page_number < 1
                or page_number > document.page_count
            ):
                raise OCRProcessingError(
                    f"Invalid OCR page number: {page_number}"
                )

        extracted_pages = []

        for page_number in selected_pages:
            page = document[page_number - 1]

            try:
                text = _extract_page_text(
                    page,
                    page_number,
                )
            except OCRProcessingError:
                logger.exception(
                    "OCR failed for page %s",
                    page_number,
                )
                text = ""

            if text:
                extracted_pages.append(
                    f"[Page {page_number} - OCR]\n{text}"
                )

        result = "\n\n".join(extracted_pages)

        if selected_pages and not result:
            logger.warning(
                "OCR produced no readable text for selected pages: %s",
                selected_pages,
            )

        return result

    finally:
        document.close()