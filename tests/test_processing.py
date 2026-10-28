
from app.services.document_classifier import classify_document
from app.services.category_classifier import classify_category
from app.services.field_extractor import extract_fields
from app.services.result_processor import build_result


def test_receipt_document_classification():
    result = classify_document(
        "Receipt\nKopi Corner\nTotal SGD 18.40"
    )

    assert result["document_type"] == "Receipt"
    assert 0.0 <= result["confidence"] <= 1.0


def test_travel_category_classification():
    result = classify_category(
        "CityCab taxi ride transport fare"
    )

    assert result["category"] == "Travel"
    assert 0.0 <= result["confidence"] <= 1.0


def test_complete_receipt_returns_done():
    result = build_result(
        filename="test_receipt.pdf",
        source="Digital",
        classification={
            "document_type": "Receipt",
            "confidence": 0.95,
        },
        fields={
            "vendor": "Kopi Corner",
            "date": "2026-10-02",
            "amount": "18.40",
            "currency": "SGD",
            "document_number": "RCP-001",
        },
        category="Food & Beverage",
        category_confidence=0.90,
    )

    assert result["Status"] == "Done"
    assert result["Vendor"] == "Kopi Corner"
    assert result["Date"] == "2026-10-02"
    assert result["Amount"] == "18.40"
    assert result["Currency"] == "SGD"
    assert result["Receipt/Invoice Number"] == "RCP-001"


def test_missing_amount_returns_needs_review():
    result = build_result(
        filename="missing_amount.pdf",
        source="Digital",
        classification={
            "document_type": "Receipt",
            "confidence": 0.95,
        },
        fields={
            "vendor": "Test Cafe",
            "date": "2026-10-02",
            "amount": "",
            "currency": "SGD",
            "document_number": "RCP-002",
        },
        category="Food & Beverage",
        category_confidence=0.90,
    )

    assert result["Status"] == "Needs review"
    assert result["Amount"] == ""


def test_missing_document_number_returns_needs_review():
    result = build_result(
        filename="missing_number.pdf",
        source="Digital",
        classification={
            "document_type": "Receipt",
            "confidence": 0.95,
        },
        fields={
            "vendor": "Test Cafe",
            "date": "2026-10-02",
            "amount": "18.40",
            "currency": "SGD",
            "document_number": "",
        },
        category="Food & Beverage",
        category_confidence=0.90,
    )

    assert result["Status"] == "Needs review"
    assert result["Receipt/Invoice Number"] == ""


def test_invalid_date_returns_needs_review():
    result = build_result(
        filename="invalid_date.pdf",
        source="Digital",
        classification={
            "document_type": "Receipt",
            "confidence": 0.95,
        },
        fields={
            "vendor": "Test Cafe",
            "date": "2026-02-30",
            "amount": "18.40",
            "currency": "SGD",
            "document_number": "RCP-003",
        },
        category="Food & Beverage",
        category_confidence=0.90,
    )

    assert result["Status"] == "Needs review"
    assert result["Date"] == ""


def test_invalid_currency_returns_needs_review():
    result = build_result(
        filename="invalid_currency.pdf",
        source="Digital",
        classification={
            "document_type": "Receipt",
            "confidence": 0.95,
        },
        fields={
            "vendor": "Test Cafe",
            "date": "2026-10-02",
            "amount": "18.40",
            "currency": "XYZ",
            "document_number": "RCP-004",
        },
        category="Food & Beverage",
        category_confidence=0.90,
    )

    assert result["Status"] == "Needs review"
    assert result["Currency"] == ""


def test_low_confidence_returns_needs_review():
    result = build_result(
        filename="low_confidence.pdf",
        source="OCR",
        classification={
            "document_type": "Receipt",
            "confidence": 0.60,
        },
        fields={
            "vendor": "Test Cafe",
            "date": "2026-10-02",
            "amount": "18.40",
            "currency": "SGD",
            "document_number": "RCP-005",
        },
        category="Food & Beverage",
        category_confidence=0.90,
    )

    assert result["Status"] == "Needs review"


def test_unsupported_document_clears_expense_fields():
    result = build_result(
        filename="unsupported.pdf",
        source="Digital",
        classification={
            "document_type": "Not an expense document",
            "confidence": 0.95,
        },
        fields={
            "vendor": "Test Vendor",
            "date": "2026-10-02",
            "amount": "100.00",
            "currency": "SGD",
            "document_number": "DOC-001",
        },
        category="Travel",
    )

    assert result["Status"] == "Unsupported"
    assert result["Category"] == ""
    assert result["Vendor"] == ""
    assert result["Date"] == ""
    assert result["Amount"] == ""
    assert result["Currency"] == ""
    assert result["Receipt/Invoice Number"] == ""


def test_unknown_document_type_returns_needs_review():
    result = build_result(
        filename="unknown.pdf",
        source="Digital",
        classification={
            "document_type": "",
            "confidence": 0.0,
        },
        fields={},
    )

    assert result["Status"] == "Needs review"


def test_processing_error_returns_failed():
    result = build_result(
        filename="corrupt.pdf",
        source="",
        error="Invalid or corrupt PDF",
    )

    assert result["Status"] == "Failed"
    assert result["Error"] == "Invalid or corrupt PDF"


def test_field_extractor_uses_total_not_item_price():
    text = """
    KOPI CORNER
    Coffee 1.00
    Subtotal SGD 1.00
    GST SGD 0.10
    TOTAL SGD 1.10
    """

    result = extract_fields(text)

    assert result["amount"] == "1.10"


def test_field_extractor_handles_decimal_amount():
    text = """
    CITYCAB SINGAPORE
    Date: 2026-10-03
    Total Amount: SGD 780.00
    Receipt No: CC-1001
    """

    result = extract_fields(text)

    assert result["amount"] == "780.00"
    assert result["currency"] == "SGD"
