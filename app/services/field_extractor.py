
import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

logger = logging.getLogger("receipt_app")

CURRENCY_CODES = (
    "SGD", "USD", "EUR", "INR", "GBP", "AUD", "CAD", "JPY",
    "MYR", "IDR", "THB", "PHP", "CNY", "NZD", "CHF", "AED",
)

CURRENCY_SYMBOLS = {
    "S$": "SGD",
    "US$": "USD",
    "₹": "INR",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
}


def _find_first(patterns: list[str], text: str) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            value = match.group(1).strip(" \t:#-*|")
            if value:
                return value
    return ""


def _normalize_date(value: str) -> str:
    value = value.strip()
    formats = (
        "%Y-%m-%d", "%Y/%m/%d",
        "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y",
        "%d-%m-%y", "%d/%m/%y",
        "%d %b %Y", "%d %B %Y",
        "%d %b, %Y", "%d %B, %Y",
        "%b %d, %Y", "%B %d, %Y",
        "%d-%b-%Y", "%d-%B-%Y",
    )

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue

    return ""


def _normalize_amount(value: str) -> str:
    cleaned = re.sub(r"[^\d,.+-]", "", value.strip())

    if not cleaned or not re.search(r"\d", cleaned) or "-" in cleaned:
        return ""

    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(".") > cleaned.rfind(","):
            cleaned = cleaned.replace(",", "")
        else:
            cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        if re.fullmatch(r"\d{1,3}(,\d{3})+", cleaned):
            cleaned = cleaned.replace(",", "")
        elif re.search(r",\d{1,2}$", cleaned):
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")

    try:
        amount = Decimal(cleaned)
        if not amount.is_finite() or amount < 0:
            return ""
        return f"{amount:.2f}"
    except (InvalidOperation, ValueError):
        return ""


def _extract_currency(text: str) -> str:
    match = re.search(
        r"\b(" + "|".join(CURRENCY_CODES) + r")\b",
        text,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).upper()

    if re.search(r"(?<!\w)Rp\.?(?=\s*\d)", text, re.IGNORECASE):
        return "IDR"
    if re.search(r"(?<=\d)\s*Rp\.?(?!\w)", text, re.IGNORECASE):
        return "IDR"

    for symbol in ("S$", "US$", "₹", "€", "£", "¥"):
        if symbol in text:
            return CURRENCY_SYMBOLS[symbol]

    return ""


def _clean_vendor(value: str) -> str:
    value = value.strip().strip("*#|:; \t-")
    value = re.sub(r"\s+", " ", value)
    value = re.sub(
        r"^(?:vendor|merchant|supplier|company name|sold by|issued by)"
        r"\s*[:#-]\s*",
        "",
        value,
        flags=re.IGNORECASE,
    )
    return value.strip("*#|:; \t-")


def _is_non_vendor_line(candidate: str) -> bool:
    if not candidate:
        return True

    value = candidate.strip()
    lower = value.lower()

    ignored_exact = {
        "receipt", "tax invoice", "invoice", "sales receipt",
        "payment receipt", "hotel folio", "boarding pass",
        "travel ticket", "expense receipt", "duplicate",
        "original", "copy", "thank you", "thank you for your visit",
        "description", "item description", "particulars",
        "item", "items", "quantity", "qty", "unit price",
        "printer paper and office supplies",
    }

    if lower in ignored_exact:
        return True

    description_patterns = (
        r"\b(?:description|item description|items purchased|"
        r"goods purchased|product details|office supplies)\b",
        r"\b(?:quantity|qty|unit price|price per item)\b",
        r"\b(?:subtotal|grand total|amount due|total paid|total payable)\b",
        r"\b(?:gst|vat|tax)\s*(?:registration|reg\.?|id|number|no\.?)\b",
        r"\b(?:receipt|invoice|document|ticket)\s*(?:number|no\.?|#)\b",
        r"\b(?:tel|telephone|phone|email|https?://|www\.)\b",
        r"\b(?:bill to|ship to|customer name|customer address)\b",
        r"\b(?:payment method|transaction id|order id)\b",
        r"\b(?:street|road|avenue|lane|boulevard|drive)\b",
        r"\b(?:postal code|postcode|zip code)\b",
        r"^\s*(?:page|printed on|generated on)\b",
        r"\b\d{1,4}[-/]\d{1,2}[-/]\d{2,4}\b",
        r"^[\W\d]+$",
    )

    if any(re.search(p, value, re.IGNORECASE) for p in description_patterns):
        return True

    letters = sum(char.isalpha() for char in value)
    digits = sum(char.isdigit() for char in value)

    if letters < 3 or digits > letters or len(value) > 80:
        return True

    words = value.split()
    if len(words) > 7:
        return True

    return False


def _extract_vendor(lines: list[str]) -> str:
    """Prefer labelled merchants, then plausible merchant-name lines."""
    if not lines:
        return ""

    labelled = _find_first(
        [
            r"^\s*(?:vendor|merchant|supplier|company\s*name)"
            r"\s*[:#-]\s*(.+?)\s*$",
            r"^\s*(?:sold\s+by|issued\s+by)\s*[:#-]\s*(.+?)\s*$",
        ],
        "\n".join(lines),
    )

    if labelled:
        candidate = _clean_vendor(labelled)
        if not _is_non_vendor_line(candidate):
            return candidate

    candidates = []
    description_words = {
        "paper", "supplies", "printer", "printing", "purchase",
        "purchased", "description", "quantity", "service",
        "services", "item", "items", "product", "products",
        "subtotal", "discount", "tax", "total", "payment",
    }

    for index, line in enumerate(lines[:15]):
        candidate = _clean_vendor(line)

        if _is_non_vendor_line(candidate):
            continue

        words = candidate.split()
        lower_words = {word.lower().strip(".,:;") for word in words}

        if len(words) >= 3 and len(lower_words & description_words) >= 2:
            continue

        letters = sum(char.isalpha() for char in candidate)
        uppercase_count = sum(
            char.isupper() for char in candidate if char.isalpha()
        )
        uppercase_ratio = uppercase_count / max(letters, 1)

        score = 0
        score += 5 if 1 <= len(words) <= 4 else 0
        score += 2 if uppercase_ratio >= 0.7 else 0
        score += 2 if re.search(
            r"\b(?:pte|ltd|limited|inc|llc|restaurant|hotel|"
            r"mart|cab|cabs|airways|mobile)\b",
            candidate,
            re.IGNORECASE,
        ) else 0
        score -= index * 0.6
        score -= 3 if lower_words & description_words else 0

        candidates.append((score, index, candidate))

    if not candidates:
        return ""

    candidates.sort(key=lambda item: (-item[0], item[1]))
    best_score, _, best_candidate = candidates[0]

    return best_candidate if best_score >= 2 else ""


def _extract_document_number(text: str) -> str:
    """Extract common receipt, invoice and transaction reference numbers."""
    patterns = [
        r"\b(?:receipt|invoice|document|ticket|folio)\s*"
        r"(?:number|no\.?|#)\s*[:#=\-]?\s*"
        r"([A-Z0-9][A-Z0-9/-]{2,})",

        r"\b(?:invoice|receipt|ticket|folio)\s*"
        r"(?:id|ref(?:erence)?|number|no\.?)\s*[:#=\-]\s*"
        r"([A-Z0-9][A-Z0-9/-]{2,})",

        r"\b(?:reference|ref)\s*(?:number|no\.?|#|id)?\s*"
        r"[:#=\-]\s*([A-Z0-9][A-Z0-9/-]{2,})",

        r"\b(?:transaction|booking|confirmation|order)\s*"
        r"(?:id|number|no\.?|reference|ref)\s*[:#=\-]?\s*"
        r"([A-Z0-9][A-Z0-9/-]{2,})",

        r"\b(?:transaction|booking|confirmation|order)\s*"
        r"(?:id|number|no\.?|reference|ref)\s+"
        r"([A-Z0-9][A-Z0-9/-]{2,})",
    ]

    return _find_first(patterns, text)



def _extract_amount(text: str) -> str:
    """Extract a labelled final total; handle OCR line breaks safely."""
    number = r"(?:\d[\d,.]*\d|\d)"
    currency = (
        r"(?:SGD|USD|EUR|INR|GBP|AUD|CAD|IDR|MYR|JPY|THB|PHP|"
        r"CNY|NZD|CHF|AED|US\$|S\$|Rp\.?|₹|€|£|¥)"
    )

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    labels = (
        r"grand\s+total",
        r"total\s+amount(?:\s+payable)?",
        r"total\s+(?:including|inclusive\s+of)\s+(?:tax|gst|vat)",
        r"amount\s+(?:due|payable|paid)",
        r"balance\s+due",
        r"net\s+payable",
        r"total\s+payable",
        r"total\s+paid",
        r"fare\s+total",
        r"parking\s+total",
        r"total",
    )

    def parse_amount(fragment: str) -> str:
        patterns = (
            rf"{currency}\s*(?P<amount>{number})",
            rf"(?P<amount>{number})\s*{currency}\b",
            rf"^\s*(?P<amount>{number})\s*$",
        )

        for pattern in patterns:
            match = re.search(pattern, fragment, re.IGNORECASE)
            if match:
                normalized = _normalize_amount(match.group("amount"))
                if normalized:
                    return normalized

        return ""

    # First preference: amounts explicitly associated with a total label.
    for label in labels:
        candidates = []

        for index, line in enumerate(lines):
            match = re.search(
                rf"(?<![\w]){label}(?![\w])",
                line,
                re.IGNORECASE,
            )
            if not match:
                continue

            is_final_total = bool(re.search(
                r"\b(?:grand\s+total|total\s+amount|amount\s+due|"
                r"amount\s+payable|total\s+payable|total\s+paid|"
                r"balance\s+due|net\s+payable|fare\s+total|"
                r"parking\s+total|total\s+(?:including|inclusive))\b",
                line,
                re.IGNORECASE,
            ))

            if not is_final_total and re.search(
                r"\b(?:sub\s*total|tax|gst|vat|discount)\b",
                line,
                re.IGNORECASE,
            ):
                continue

            amount = parse_amount(line[match.end():])

            if not amount:
                amount = parse_amount(line[:match.start()])

            # OCR may put the amount on the next line.
            if not amount and index + 1 < len(lines):
                amount = parse_amount(lines[index + 1])

            if amount:
                candidates.append(amount)

        if candidates:
            unique = list(dict.fromkeys(candidates))
            return unique[0] if len(unique) == 1 else ""

    # Fallback: fixed regex groups avoid duplicate-name errors.
    fallback_pattern = (
        rf"{currency}\s*(?P<amount1>{number})"
        rf"|(?P<amount2>{number})\s*{currency}\b"
    )

    candidates = []

    for match in re.finditer(fallback_pattern, text, re.IGNORECASE):
        raw = match.group("amount1") or match.group("amount2") or ""
        normalized = _normalize_amount(raw)

        if normalized:
            candidates.append(normalized)

    unique = list(dict.fromkeys(candidates))
    return unique[0] if len(unique) == 1 else ""



def extract_fields(text: str) -> dict:
    """Extract receipt fields without inventing missing values."""
    result = {
        "vendor": "",
        "date": "",
        "amount": "",
        "currency": "",
        "document_number": "",
    }

    if not text or not text.strip():
        return result

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    normalized = "\n".join(lines)

    result["vendor"] = _extract_vendor(lines)

    date_labels = (
        r"(?:transaction date|invoice date|receipt date|issue date|"
        r"travel date|booking date|check-in date|date)"
    )

    raw_date = _find_first(
        [
            rf"\b{date_labels}\s*[:#-]?\s*"
            rf"(\d{{4}}[-/]\d{{1,2}}[-/]\d{{1,2}})",
            rf"\b{date_labels}\s*[:#-]?\s*"
            rf"(\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}})",
            rf"\b{date_labels}\s*[:#-]?\s*"
            rf"(\d{{1,2}}\s+[A-Za-z]{{3,9}},?\s+\d{{4}})",
            rf"\b{date_labels}\s*[:#-]?\s*"
            rf"([A-Za-z]{{3,9}}\s+\d{{1,2}},?\s+\d{{4}})",
        ],
        normalized,
    )

    if raw_date:
        result["date"] = _normalize_date(raw_date)

    result["amount"] = _extract_amount(normalized)
    result["currency"] = _extract_currency(normalized)
    result["document_number"] = _extract_document_number(normalized)

    logger.info(
        "Field extraction completed | populated_fields=%s/5",
        sum(bool(value) for value in result.values()),
    )

    return result
