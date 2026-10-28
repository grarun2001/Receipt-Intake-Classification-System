from pathlib import Path

from app.services.ocr_service import extract_text_with_ocr

PROJECT_ROOT = Path(__file__).resolve().parent
PDF_NAME = "02_scanned_receipt_idr_rp.pdf"

matches = list(PROJECT_ROOT.rglob(PDF_NAME))

if not matches:
    print(f"PDF not found: {PDF_NAME}")
    print("Available PDF files:")

    for pdf in PROJECT_ROOT.rglob("*.pdf"):
        print(pdf.relative_to(PROJECT_ROOT))

    raise SystemExit(1)

pdf_path = matches[0]

print(f"Testing PDF: {pdf_path}")

try:
    text = extract_text_with_ocr(pdf_path.read_bytes())

    print("\n========== OCR OUTPUT ==========\n")
    print(text)
    print("\n========== END OF OUTPUT ==========\n")

    output_path = PROJECT_ROOT / "ocr_output.txt"
    output_path.write_text(text, encoding="utf-8")

    print(f"OCR output saved to: {output_path}")

except Exception as exc:
    print(f"OCR TEST FAILED: {type(exc).__name__}: {exc}")
    raise