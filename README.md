# Receipt Intake & Classification System

A Python-based document processing system that accepts multiple PDF receipts and invoices, extracts text from digital and scanned documents, classifies document types and expense categories, and extracts key fields for expense review.

## Key Features

- **Batch PDF Processing** — Upload and process multiple PDF documents in a single request.
- **Digital Text Extraction** — Extract embedded text from digitally generated PDFs.
- **OCR Processing** — Extract text from scanned PDFs using Tesseract OCR.
- **Mixed-PDF Support** — Preserve digital text and apply OCR to pages that require it.
- **Document Classification** — Identify receipts, tax invoices, travel tickets, hotel folios, and unsupported documents.
- **Expense Categorization** — Classify expenses into Food & Beverage, Travel, Accommodation, Office Supplies, and Other.
- **Field Extraction** — Extract vendor name, date, total amount, currency, and receipt or invoice number.
- **Confidence & Review Status** — Flag uncertain or incomplete results for manual review.
- **REST API** — Process documents through a FastAPI endpoint.
- **Interactive UI** — Upload documents and review processing results through Streamlit.
- **Evaluation Script** — Compare API outputs against expected ground-truth values and report field-wise accuracy, overall accuracy, mismatches, and status distribution.

## Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python |
| Backend API | FastAPI |
| User Interface | Streamlit |
| PDF Processing | PyMuPDF |
| Optical Character Recognition | Tesseract OCR |
| Image Processing | Pillow |
| HTTP Requests | Requests |
| Evaluation | Custom Python evaluation script with CSV ground truth |

## System Workflow

1. Upload one or more PDF documents through the UI or API.
2. Validate the uploaded files.
3. Extract embedded text from digital PDF pages.
4. Apply OCR to scanned pages or pages without usable digital text.
5. Combine the extracted text with page-level source information.
6. Classify the document type and expense category.
7. Extract key fields such as vendor, date, amount, currency, and document number.
8. Assign a processing status based on the implemented validation and review rules.
9. Display the results for review.
10. Run the evaluation script to compare actual results against expected values.

## Project Structure

```text
receipt_intake_classification/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── schemas.py
│   ├── ui.py
│   └── services/
│       ├── pdf_reader.py
│       └── ocr_service.py
├── tests/
│   ├── __init__.py
│   └── test_processing.py
├── sample_docs/
├── create_test_pdfs.py
├── test_ocr.py
├── expected_results.csv
├── evaluate.py
├── requirements.txt
└── README.md
```

*Note: Update this structure if the final repository contains additional modules or different filenames.*

## Prerequisites

- Python 3.10 or a compatible version supported by the project dependencies
- Tesseract OCR installed on the system
- Git (optional, for version control)

## Installation

### 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd receipt_intake_classification
```

### 2. Create a virtual environment

**Windows PowerShell:**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Configure Tesseract OCR

Install Tesseract OCR and ensure the executable is accessible through your system PATH. If the project configuration requires an explicit executable path, configure it in `app/config.py`.

## Running the Application

### Start the FastAPI backend

From the project root:

```powershell
uvicorn app.main:app --reload
```

Backend URL:

```text
http://127.0.0.1:8000
```

Interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

Health endpoint:

```text
http://127.0.0.1:8000/health
```

### Start the Streamlit UI

Open a separate terminal in the project root, activate the same virtual environment, and run:

```powershell
python -m streamlit run app/ui.py
```

Streamlit will display the local URL in the terminal, typically `http://localhost:8501`.

Keep the backend running while using the UI.

## API Usage

### Process multiple PDFs

**Endpoint:**

```text
POST /process
```

The API accepts multiple PDF files using the `files` multipart form field.

Example using Python:

```python
import requests

url = "http://127.0.0.1:8000/process"

with open("sample_docs/receipt.pdf", "rb") as pdf:
    response = requests.post(
        url,
        files=[
            ("files", ("receipt.pdf", pdf, "application/pdf"))
        ],
        timeout=300,
    )

response.raise_for_status()
print(response.json())
```

Replace the sample filename with an existing PDF from your test dataset.

## Evaluation

The project includes `evaluate.py`, a custom Python-based evaluation script.

It uses `expected_results.csv` as the ground-truth reference and sends the sample documents to the running API.

The evaluation reports:

- Number of expected and returned documents
- Matched-file coverage
- Field-wise accuracy
- Overall field accuracy
- Expected-versus-actual mismatches
- Document status distribution

### Run evaluation

Start the backend first. Then run this command from the project root:

```powershell
python evaluate.py
```

The sample PDFs and expected-results CSV must be available in their configured locations.

**Important:** Evaluation accuracy depends on the actual API output and the correctness of the ground-truth data. Run the script before publishing results; do not report unverified accuracy figures.

## Testing

Run the existing test suite using the test framework configured in the project.

For example, if the tests use pytest:

```powershell
python -m pytest -v
```

If pytest is not included in `requirements.txt`, install it in the development environment before running this command.

## Processing Statuses

| Status | Meaning |
|---|---|
| Done | Processing completed according to the implemented validation rules. |
| Needs review | One or more extracted values require manual verification. |
| Unsupported | The document is not a supported expense document. |
| Failed | The document could not be processed successfully. |

Exact status assignment follows the application’s implemented processing and validation logic.

## Limitations

- OCR quality depends on scan resolution, image quality, orientation, and document layout.
- Handwriting and unusual fonts may reduce extraction accuracy.
- Incorrect or missing information in a document can require manual review.
- Field extraction and classification must be evaluated across different document layouts, not only the provided samples.
- Processing time depends on PDF size, page count, OCR requirements, and available CPU resources.

## Future Improvements

- Add support for more languages and handwritten receipts.
- Improve extraction accuracy with layout-aware document understanding.
- Expand the evaluation dataset to cover more vendors and document formats.
- Add structured evaluation reports and regression testing.
- Improve confidence calibration and manual correction workflows.
- Add authentication, upload-size limits, and production deployment configuration.

## Security Notes

- Never commit API keys, passwords, access tokens, or `.env` files.
- Exclude virtual environments, cache folders, and temporary files from version control.
- Review sample documents before publishing to ensure they do not contain personal or confidential information.

## License

Add a license before distributing this project publicly. Until a license is included, reuse permissions are not explicitly granted.

---

**Project:** Receipt Intake & Classification System  
**Purpose:** Automate initial receipt and invoice processing,