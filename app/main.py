import logging

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

from app.services.pdf_reader import (
    read_pdf,
    PDFProcessingError,
)
from app.services.ocr_service import (
    extract_text_with_ocr,
    OCRProcessingError,
)
from app.services.document_classifier import classify_document
from app.services.category_classifier import classify_category
from app.services.field_extractor import extract_fields
from app.services.result_processor import build_result
from app.utils.validators import validate_pdf
from app.utils.logging_config import setup_logging


setup_logging()
logger = logging.getLogger("receipt_app")


app = FastAPI(
    title="Receipt Intake & Classification API",
    version="1.0.0",
    description="Extracts and classifies expense documents.",
)


def process_document(filename: str, content: bytes) -> dict:
    """Process one PDF and return its result."""

    is_valid, validation_error = validate_pdf(
        filename,
        content,
    )

    if not is_valid:
        result = build_result(
            filename=filename,
            error=validation_error,
        )
        result["Extracted Text"] = ""
        return result

    try:
        # Step 1: Read the PDF and inspect each page.
        pdf_result = read_pdf(content)

        source = pdf_result["source"]
        pages = pdf_result["pages"]
        needs_ocr_pages = pdf_result["needs_ocr_pages"]

        # Step 2: Keep extracted digital text.
        text_parts = []

        for page in pages:
            if page["has_usable_text"] and page["text"].strip():
                text_parts.append(
                    f"[Page {page['page_number']} - Digital]\n"
                    f"{page['text']}"
                )

        # Step 3: Run OCR only on pages that need it.
        if needs_ocr_pages:
            try:
                ocr_text = extract_text_with_ocr(
                    content,
                    page_numbers=needs_ocr_pages,
                )

                if ocr_text and ocr_text.strip():
                    text_parts.append(ocr_text)

            except OCRProcessingError:
                logger.exception(
                    "OCR processing failed | file=%s | pages=%s",
                    filename,
                    needs_ocr_pages,
                )

        # Step 4: Combine all extracted text.
        text = "\n\n".join(text_parts).strip()

        if not text:
            raise PDFProcessingError(
                "No readable text could be extracted from this PDF."
            )

        logger.info(
            "Text extraction completed | file=%s | source=%s",
            filename,
            source,
        )

        # Step 5: Identify the document type.
        document_result = classify_document(text)
        document_type = document_result["document_type"]

        # Step 6: Extract document fields.
        fields = extract_fields(text)

        # Step 7: Classify the expense category.
        category_result = classify_category(
            text,
            document_type,
        )

        # Step 8: Build the final processing result.
        result = build_result(
            filename=filename,
            source=source,
            classification=document_result,
            fields=fields,
            category=category_result["category"],
            reason=category_result["reason"],
            category_confidence=category_result["confidence"],
        )

        result["Extracted Text"] = text

        return result

    except PDFProcessingError as exc:
        logger.warning(
            "PDF processing issue | file=%s | reason=%s",
            filename,
            str(exc),
        )

        result = build_result(
            filename=filename,
            error=str(exc),
        )
        result["Extracted Text"] = ""
        return result

    except Exception:
        logger.exception(
            "Unexpected processing error | file=%s",
            filename,
        )

        result = build_result(
            filename=filename,
            error="An unexpected error occurred while processing this PDF.",
        )
        result["Extracted Text"] = ""
        return result


@app.get("/health")
def health_check():
    """Check whether the API is running."""

    return {"status": "healthy"}


@app.post("/process")
async def process_files(files: list[UploadFile] = File(...)):
    """Process multiple PDF files independently."""

    if not files:
        return JSONResponse(
            status_code=400,
            content={
                "error": "Upload at least one PDF file."
            },
        )

    results = []

    for uploaded_file in files:
        filename = uploaded_file.filename or ""

        try:
            content = await uploaded_file.read()

            result = process_document(
                filename=filename,
                content=content,
            )

            results.append(result)

        except Exception:
            logger.exception(
                "Upload handling failed | file=%s",
                filename,
            )

            failed_result = build_result(
                filename=filename or "unknown.pdf",
                error="The uploaded file could not be read.",
            )

            failed_result["Extracted Text"] = ""
            results.append(failed_result)

        finally:
            await uploaded_file.close()

    return {
        "total_files": len(results),
        "results": results,
    }