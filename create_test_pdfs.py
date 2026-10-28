
from pathlib import Path
from io import BytesIO

import fitz
from PIL import Image, ImageDraw, ImageFont


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "sample_docs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# Fictional assessment test data only.
# True = scanned/image-based PDF; False = digital text PDF.
DOCUMENTS = [
    {
        "file": "R01.pdf",
        "scanned": False,
        "text": [
            "Kopi Corner",
            "RECEIPT",
            "Receipt No: KC-1001",
            "Date: 2026-10-02",
            "Food and Beverage",
            "Coffee and sandwich",
            "Total SGD 18.40",
        ],
    },
    {
        "file": "R02.pdf",
        "scanned": False,
        "text": [
            "CityCab Singapore",
            "RECEIPT",
            "Receipt No: CC-1002",
            "Transaction Date: 2026-10-03",
            "Taxi ride",
            "Transport fare",
            "Total SGD 24.60",
        ],
    },
    {
        "file": "R03.pdf",
        "scanned": True,
        "text": [
            "Lotus Garden Restaurant",
            "RECEIPT",
            "Receipt No: LG-1003",
            "Date: 2026-10-04",
            "Restaurant dining",
            "Food and beverages",
            "Total SGD 86.20",
        ],
    },
    {
        "file": "R04.pdf",
        "scanned": False,
        "text": [
            "SkyJet Airways",
            "FLIGHT TICKET",
            "E-Ticket No: SJ-1004",
            "Travel Date: 2026-10-06",
            "Departure: Singapore",
            "Arrival: Bengaluru",
            "Airline ticket fare",
            "Total USD 312.00",
        ],
    },
    {
        "file": "R05.pdf",
        "scanned": False,
        "text": [
            "Harbourview Hotel",
            "HOTEL FOLIO",
            "Invoice No: HV-1005",
            "Check-in Date: 2026-10-08",
            "Room rate",
            "Accommodation charges",
            "Grand Total SGD 540.00",
        ],
    },
    {
        "file": "R06.pdf",
        "scanned": True,
        "text": [
            "PaperMart",
            "RECEIPT",
            "Receipt No: PM-1006",
            "Date: 2026-10-05",
            "Office Supplies",
            "Printer paper and stationery",
            "Total SGD 47.85",
        ],
    },
    {
        "file": "R07.pdf",
        "scanned": False,
        "text": [
            "TechHub Pte Ltd",
            "TAX INVOICE",
            "Invoice No: TH-1007",
            "Invoice Date: 2026-09-28",
            "Printer paper and office supplies",
            "Subtotal SGD 120.00",
            "Tax SGD 9.00",
            "Grand Total SGD 129.00",
        ],
    },
    {
        "file": "R08.pdf",
        "scanned": True,
        "text": [
            "Metro Cabs Bengaluru",
            "RECEIPT",
            "Receipt No: MC-1008",
            "Date: 2026-10-09",
            "Taxi transport fare",
            "Total INR 780.00",
        ],
    },
    {
        "file": "R09.pdf",
        "scanned": False,
        "text": [
            "Brasserie Lune",
            "RECEIPT",
            "Receipt No: BL-1009",
            "Date: 2026-10-10",
            "Restaurant dining",
            "Food and beverage",
            "Total EUR 54.50",
        ],
    },
    {
        "file": "R10.pdf",
        "scanned": True,
        "text": [
            "CarPark Central",
            "RECEIPT",
            "Receipt No: CP-1010",
            "Date: 2026-10-07",
            "Parking charge",
            "Payment method: Card",
            "Amount unreadable",
        ],
    },
    {
        "file": "R11.pdf",
        "scanned": False,
        "text": [
            "MEETING AGENDA",
            "Project Planning Meeting",
            "Date: 2026-10-12",
            "1. Project updates",
            "2. Discussion topics",
            "3. Action items",
        ],
    },
    {
        "file": "R12.pdf",
        "scanned": False,
        "text": [
            "StarLink Mobile",
            "TAX INVOICE",
            "Invoice No: SM-1012",
            "Invoice Date: 2026-10-01",
            "Mobile bill",
            "Telecommunication service",
            "Total SGD 68.00",
        ],
    },
]


def load_font(size: int):
    """Load a readable font available on Windows."""
    candidates = [
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\calibri.ttf"),
    ]

    for font_path in candidates:
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size)

    return ImageFont.load_default()


def create_digital_pdf(output_path: Path, lines: list[str]) -> None:
    """Create a PDF with selectable, digitally embedded text."""
    document = fitz.open()

    try:
        page = document.new_page(width=595, height=842)
        y = 65

        for index, line in enumerate(lines):
            font_size = 16 if index == 0 else 12
            page.insert_text(
                (55, y),
                line,
                fontsize=font_size,
                fontname="helv",
                color=(0, 0, 0),
            )
            y += 32 if index == 0 else 25

        document.save(output_path, garbage=4, deflate=True)
    finally:
        document.close()


def create_scanned_pdf(output_path: Path, lines: list[str]) -> None:
    """Create an image-only PDF so text extraction requires OCR."""
    image = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(image)
    font = load_font(36)

    y = 130

    for index, line in enumerate(lines):
        current_font = load_font(44) if index == 0 else font
        draw.text(
            (105, y),
            line,
            fill=(20, 20, 20),
            font=current_font,
        )
        y += 85

    # Slight rotation simulates a real scanned page.
    image = image.rotate(
        0.4,
        resample=Image.Resampling.BICUBIC,
        expand=False,
        fillcolor="white",
    )

    image_buffer = BytesIO()
    image.save(image_buffer, format="PNG", dpi=(150, 150))

    document = fitz.open()

    try:
        page = document.new_page(width=595, height=842)
        page.insert_image(
            page.rect,
            stream=image_buffer.getvalue(),
        )
        document.save(output_path, garbage=4, deflate=True)
    finally:
        document.close()


def main() -> None:
    created = 0

    for item in DOCUMENTS:
        output_path = OUTPUT_DIR / item["file"]

        if item["scanned"]:
            create_scanned_pdf(output_path, item["text"])
            source_type = "scanned/image-based"
        else:
            create_digital_pdf(output_path, item["text"])
            source_type = "digital/text-based"

        created += 1
        print(f"Created {item['file']} | {source_type}")

    print(f"\nFinished: {created} synthetic PDFs created in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
