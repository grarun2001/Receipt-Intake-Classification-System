
import logging
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

logger = logging.getLogger("receipt_app")

SUPPORTED_DOCUMENT_TYPES = {
    "Receipt",
    "Tax invoice",
    "Travel ticket",
    "Hotel folio",
}

SUPPORTED_CATEGORIES = {
    "Food & Beverage",
    "Travel",
    "Accommodation",
    "Office Supplies",
    "Other",
}

SUPPORTED_CURRENCIES = {
    "SGD", "USD", "EUR", "INR", "GBP", "AUD", "CAD", "JPY",
    "MYR", "IDR", "THB", "PHP", "CNY", "NZD", "CHF", "AED",
}

CONFIDENCE_THRESHOLD = 0.70

# All fields listed here must be populated for a Done result.
REQUIRED_FIELDS = {
    "Category": "category",
    "Vendor": "vendor",
    "Date": "date",
    "Amount": "amount",
    "Currency": "currency",
    "Receipt/Invoice Number": "document_number",
}


def _safe_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0

    if not 0.0 <= confidence <= 1.0:
        return 0.0

    return confidence


def _valid_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False

    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def _valid_amount(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False

    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return False

    return (
        amount.is_finite()
        and amount >= 0
        and amount.as_tuple().exponent == -2
    )


def _append_reason(existing: str, message: str) -> str:
    if not existing:
        return message
    if message.lower() in existing.lower():
        return existing
    return f"{existing.rstrip()} {message}"


def build_result(
    filename: str,
    source: str = "",
    classification: dict[str, Any] | None = None,
    fields: dict[str, Any] | None = None,
    category: str = "",
    reason: str = "",
    error: str = "",
    category_confidence: float | None = None,
) -> dict[str, Any]:
    """Build a normalized result and conservatively assign its status."""

    classification = classification or {}
    fields = fields or {}

    document_type = str(
        classification.get("document_type") or ""
    ).strip()

    document_confidence = _safe_confidence(
        classification.get("confidence", 0.0)
    )

    if category_confidence is None:
        # Compatibility fallback. The caller should pass the actual
        # category classifier confidence whenever it is available.
        category_confidence = (
            document_confidence if category else 0.0
        )

    category_confidence = _safe_confidence(category_confidence)

    overall_confidence = min(
        document_confidence,
        category_confidence,
    )

    result = {
        "File": filename,
        "Source": source,
        "Document Type": document_type,
        "Category": str(category or "").strip(),
        "Vendor": str(fields.get("vendor") or "").strip(),
        "Date": str(fields.get("date") or "").strip(),
        "Amount": str(fields.get("amount") or "").strip(),
        "Currency": str(fields.get("currency") or "").strip().upper(),
        "Receipt/Invoice Number": str(
            fields.get("document_number") or ""
        ).strip(),
        "Confidence": round(overall_confidence, 2),
        "Reason": (
            str(reason).strip()
            or str(classification.get("reason") or "").strip()
        ),
        "Status": "",
        "Error": str(error or "").strip(),
    }

    if result["Error"]:
        result["Status"] = "Failed"
        result["Reason"] = _append_reason(
            result["Reason"],
            "Document processing failed.",
        )
        logger.warning(
            "Document processing failed | file=%s",
            filename,
        )
        return result

    if document_type == "Not an expense document":
        for column in (
            "Category",
            "Vendor",
            "Date",
            "Amount",
            "Currency",
            "Receipt/Invoice Number",
        ):
            result[column] = ""

        result["Status"] = "Unsupported"
        result["Reason"] = _append_reason(
            result["Reason"],
            "The document is not a supported expense document.",
        )
        return result

    if document_type not in SUPPORTED_DOCUMENT_TYPES:
        result["Document Type"] = ""
        result["Status"] = "Needs review"
        result["Reason"] = _append_reason(
            result["Reason"],
            "Document type is missing, unsupported, or uncertain.",
        )
        return result

    if result["Category"] not in SUPPORTED_CATEGORIES:
        result["Category"] = ""

    if not _valid_date(result["Date"]):
        result["Date"] = ""

    if not _valid_amount(result["Amount"]):
        result["Amount"] = ""

    if result["Currency"] not in SUPPORTED_CURRENCIES:
        result["Currency"] = ""

    missing_fields = [
        column
        for column in REQUIRED_FIELDS
        if not result.get(column)
    ]

    # These checks catch malformed values, but cannot independently
    # prove that an extracted amount matches the original document.
    if missing_fields:
        result["Reason"] = _append_reason(
            result["Reason"],
            "Required fields are missing or invalid: "
            + ", ".join(missing_fields)
            + ".",
        )

    if overall_confidence < CONFIDENCE_THRESHOLD:
        result["Reason"] = _append_reason(
            result["Reason"],
            "Confidence is below the required threshold.",
        )

    if missing_fields or overall_confidence < CONFIDENCE_THRESHOLD:
        result["Status"] = "Needs review"
    else:
        result["Status"] = "Done"

    logger.info(
        "Result created | file=%s | status=%s | confidence=%.2f",
        filename,
        result["Status"],
        overall_confidence,
    )

    return result
