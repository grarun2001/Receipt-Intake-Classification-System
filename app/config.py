
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

LOG_DIR = BASE_DIR / "logs"
SAMPLE_DOCS_DIR = BASE_DIR / "sample_docs"

TESSERACT_CMD = os.getenv(
    "TESSERACT_CMD",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
)

DOCUMENT_TYPES = [
    "Receipt",
    "Tax invoice",
    "Travel ticket",
    "Hotel folio",
    "Not an expense document",
]

EXPENSE_CATEGORIES = [
    "Food & Beverage",
    "Travel",
    "Accommodation",
    "Office Supplies",
    "Other",
]

RESULT_COLUMNS = [
    "File",
    "Source",
    "Document Type",
    "Category",
    "Vendor",
    "Date",
    "Amount",
    "Currency",
    "Receipt/Invoice Number",
    "Confidence",
    "Reason",
    "Status",
    "Error",
]

LOG_DIR.mkdir(parents=True, exist_ok=True)
