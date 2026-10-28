
import logging
import re

logger = logging.getLogger("receipt_app")

DOCUMENT_PATTERNS = {
    "Travel ticket": [
        r"\bboarding pass\b",
        r"\be-?\s*ticket\b",
        r"\bflight ticket\b",
        r"\bflight itinerary\b",
        r"\bflight\s*(?:no\.?|number)\b",
        r"\btrain ticket\b",
        r"\bbus ticket\b",
        r"\brailway ticket\b",
        r"\bairline ticket\b",
        r"\bdeparture\b.{0,100}\barrival\b",
    ],
    "Hotel folio": [
        r"\bhotel folio\b",
        r"\bguest folio\b",
        r"\broom charge\b",
        r"\broom rate\b",
        r"\bnights stayed\b",
        r"\bcheck[- ]?in(?: date)?\b",
        r"\bcheck[- ]?out(?: date)?\b",
        r"\blodging\b",
        r"\bhotel accommodation\b",
    ],
    "Tax invoice": [
        r"\btax invoice\b",
        r"\bgst invoice\b",
        r"\bvat invoice\b",
        r"\binvoice\b",
        r"\binvoice\s*(?:no\.?|number|#)\b",
    ],
    "Receipt": [
        r"\breceipt\b",
        r"\bsales slip\b",
        r"\bpayment received\b",
        r"\bproof of payment\b",
        r"\btransaction receipt\b",
        r"\bcash receipt\b",
        r"\bfood receipt\b",
        r"\bparking receipt\b",
        r"\btravel receipt\b",
    ],
}

NON_EXPENSE_PATTERNS = [
    r"\bterms and conditions\b",
    r"\bprivacy policy\b",
    r"\bjob application\b",
    r"\bmeeting agenda\b",
    r"\bpersonal letter\b",
    r"\bcurriculum vitae\b",
    r"\bclass timetable\b",
    r"\bminutes of meeting\b",
]

EXPENSE_SIGNALS = [
    r"\bgrand total\b",
    r"\bamount due\b",
    r"\btotal payable\b",
    r"\bpayment received\b",
    r"\bpayment method\b",
    r"\btransaction date\b",
    r"\bsubtotal\b",
    r"\b(?:tax|gst|vat)\s+invoice\b",
    r"\breceipt\b",
    r"\binvoice\b",
    r"\bboarding pass\b",
    r"\bflight ticket\b",
    r"\btrain ticket\b",
    r"\bbus ticket\b",
    r"\bhotel folio\b",
    r"\broom charge\b",
    r"\broom rate\b",
    r"\bfare\b",
    r"\brestaurant\b",
    r"\bfood\b",
    r"\bbeverage\b",
    r"\bdining\b",
    r"\bparking\b",
    r"\bcar park\b",
    r"\btaxi\b",
    r"\bcab\b",
    r"\bhotel\b",
    r"\bmobile bill\b",
    r"\btelecommunication\b",
]

SUPPORTED_TYPES = (
    "Receipt",
    "Tax invoice",
    "Travel ticket",
    "Hotel folio",
)


def _matches(patterns: list[str], text: str) -> list[str]:
    return [
        pattern
        for pattern in patterns
        if re.search(pattern, text, re.IGNORECASE)
    ]


def classify_document(text: str) -> dict:
    if not text or not text.strip():
        return {
            "document_type": "",
            "confidence": 0.0,
            "reason": "No readable document text was available.",
        }

    normalized = re.sub(r"\s+", " ", text).strip().lower()

    expense_matches = _matches(EXPENSE_SIGNALS, normalized)
    non_expense_matches = _matches(NON_EXPENSE_PATTERNS, normalized)

    if non_expense_matches and not expense_matches:
        return {
            "document_type": "Not an expense document",
            "confidence": 0.90,
            "reason": (
                "The document contains non-expense indicators and "
                "no supported expense indicators."
            ),
        }

    matched_patterns = {
        document_type: _matches(patterns, normalized)
        for document_type, patterns in DOCUMENT_PATTERNS.items()
    }

    scores = {document_type: 0 for document_type in SUPPORTED_TYPES}

    for document_type, matches in matched_patterns.items():
        scores[document_type] += len(matches)

    if re.search(r"\b(?:tax|gst|vat)\s+invoice\b", normalized):
        scores["Tax invoice"] += 4

    if re.search(
        r"\b(?:boarding pass|e-?\s*ticket|flight ticket|"
        r"train ticket|bus ticket|airline ticket)\b",
        normalized,
    ):
        scores["Travel ticket"] += 4

    if re.search(
        r"\b(?:hotel folio|guest folio|room charge|room rate|"
        r"nights stayed)\b",
        normalized,
    ):
        scores["Hotel folio"] += 4

    if re.search(
        r"\b(?:receipt|sales slip|transaction receipt|cash receipt)\b",
        normalized,
    ):
        scores["Receipt"] += 3

    # A generic "invoice" is weaker than an explicit tax invoice.
    if re.search(r"\binvoice\b", normalized) and not re.search(
        r"\b(?:tax|gst|vat)\s+invoice\b",
        normalized,
    ):
        scores["Tax invoice"] += 1

    best_score = max(scores.values())

    if best_score == 0:
        return {
            "document_type": "Not an expense document",
            "confidence": 0.65,
            "reason": (
                "No supported expense-document type was identified; "
                "manual review may be needed."
            ),
        }

    ranked = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    best_type, best_score = ranked[0]
    second_score = ranked[1][1]

    if best_score == second_score:
        result = {
            "document_type": best_type,
            "confidence": 0.50,
            "reason": (
                "Multiple document types have similar evidence; "
                "manual review is recommended."
            ),
        }
    else:
        matched_count = len(matched_patterns.get(best_type, []))
        margin = best_score - second_score
        confidence = min(0.95, 0.60 + 0.10 * margin)

        if matched_count == 0:
            confidence = min(confidence, 0.65)
        elif matched_count == 1:
            confidence = min(confidence, 0.75)

        result = {
            "document_type": best_type,
            "confidence": round(confidence, 2),
            "reason": (
                f"Document indicators support the classification "
                f"{best_type}."
            ),
        }

    logger.info(
        "Document classification completed | type=%s | confidence=%.2f",
        result["document_type"],
        result["confidence"],
    )
    return result
