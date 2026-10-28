
import re


CATEGORY_KEYWORDS = {
    "Food & Beverage": [
        "restaurant", "cafe", "coffee", "food", "beverage",
        "lunch", "dinner", "breakfast", "bakery", "catering",
        "meal", "dining", "takeaway", "tea shop", "menu",
        "food order", "serving",
    ],
    "Travel": [
        "taxi", "cab", "ride", "flight", "airline", "train",
        "bus", "metro", "parking", "car park", "toll", "fare",
        "transport", "boarding pass", "ticket", "travel", "fuel",
        "petrol", "diesel", "car rental", "airport transfer",
    ],
    "Accommodation": [
        "hotel", "accommodation", "room rate", "guest folio",
        "lodging", "check-in", "check-out", "room charge",
        "night stay", "nights stayed", "guest room",
    ],
    "Office Supplies": [
        "stationery", "office supplies", "printer", "paper",
        "ink cartridge", "toner", "pen", "notebook",
        "office equipment", "stapler", "file folder",
        "writing materials",
    ],
}

OTHER_EXPENSE_KEYWORDS = [
    "mobile bill",
    "mobile service",
    "mobile plan",
    "mobile telecom",
    "telecom",
    "telecommunication",
    "telephone bill",
    "internet bill",
    "broadband",
    "phone bill",
    "data plan",
    "software licence",
    "software license",
    "subscription",
    "utility bill",
    "electricity bill",
    "water bill",
    "insurance premium",
    "membership fee",
]

NON_EXPENSE_DOCUMENTS = {
    "not an expense document",
    "non-expense",
    "unsupported",
}

SUPPORTED_EXPENSE_TYPES = {
    "receipt",
    "tax invoice",
    "travel ticket",
    "hotel folio",
}


def _normalize(text: str) -> str:
    """Normalize extracted text before category matching."""
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _contains_phrase(text: str, phrase: str) -> bool:
    """Match a keyword as a phrase rather than a partial word."""
    pattern = rf"(?<!\w){re.escape(phrase.lower())}(?!\w)"
    return re.search(pattern, text, re.IGNORECASE) is not None


def classify_category(
    text: str,
    document_type: str = "",
) -> dict:
    """
    Classify an expense using textual evidence.

    Returns one of the supported categories or an empty category
    when evidence is missing or ambiguous.
    """
    normalized_text = _normalize(text)
    normalized_type = _normalize(document_type)

    if normalized_type in NON_EXPENSE_DOCUMENTS:
        return {
            "category": "",
            "confidence": 0.0,
            "reason": "Non-expense document; category is not applicable.",
        }

    if not normalized_text:
        return {
            "category": "",
            "confidence": 0.0,
            "reason": "No readable text is available for category classification.",
        }

    # Score each category from explicit keyword matches.
    scores = {}
    matched_keywords = {}

    for category, keywords in CATEGORY_KEYWORDS.items():
        matches = [
            keyword for keyword in keywords
            if _contains_phrase(normalized_text, keyword)
        ]

        if matches:
            scores[category] = len(matches)
            matched_keywords[category] = matches

    other_matches = [
        keyword for keyword in OTHER_EXPENSE_KEYWORDS
        if _contains_phrase(normalized_text, keyword)
    ]

    if other_matches:
        # Specific telecom, software, utility and similar evidence
        # is strong evidence for Other.
        scores["Other"] = len(other_matches)
        matched_keywords["Other"] = other_matches

    if not scores:
        return {
            "category": "",
            "confidence": 0.0,
            "reason": (
                "No category-specific evidence was found; "
                "manual review is recommended."
            ),
        }

    ranked = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    best_category, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    # Conflicting categories with equal evidence are not guessed.
    if best_score == second_score:
        return {
            "category": "",
            "confidence": 0.0,
            "reason": (
                "Multiple expense categories have similar evidence; "
                "manual review is recommended."
            ),
        }

    # A single weak keyword is not enough for a high-confidence result.
    confidence = min(
        0.95,
        0.65 + 0.10 * (best_score - second_score),
    )

    if best_score == 1:
        confidence = min(confidence, 0.70)

    matched = matched_keywords.get(best_category, [])

    return {
        "category": best_category,
        "confidence": round(confidence, 2),
        "reason": (
            f"Category identified as {best_category} from textual evidence: "
            + ", ".join(matched)
            + "."
        ),
    }
