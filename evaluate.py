
import csv
import sys
from contextlib import ExitStack
from decimal import Decimal, InvalidOperation
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
SAMPLE_DIR = BASE_DIR / "sample_docs"
EXPECTED_FILE = BASE_DIR / "expected_results.csv"
API_URL = "http://127.0.0.1:8000/process"

FIELDS = [
    "Source",
    "Document Type",
    "Category",
    "Vendor",
    "Date",
    "Amount",
    "Currency",
    "Status",
]


def normalize(field, value):
    value = str(value or "").strip()

    if field == "Amount" and value:
        try:
            return format(
                Decimal(value).quantize(Decimal("0.01")),
                "f",
            )
        except (InvalidOperation, ValueError):
            return value

    return " ".join(value.split()).casefold()


def load_expected():
    if not EXPECTED_FILE.is_file():
        raise FileNotFoundError(
            f"Expected results file not found: {EXPECTED_FILE}"
        )

    with EXPECTED_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)
        required_headers = ["File", *FIELDS]

        if reader.fieldnames != required_headers:
            raise ValueError(
                "CSV headers must be exactly: "
                + ", ".join(required_headers)
            )

        rows = list(reader)

    if not rows:
        raise ValueError("Expected results CSV contains no data rows.")

    seen_files = set()

    for row_number, row in enumerate(rows, start=2):
        if None in row:
            raise ValueError(
                f"CSV row {row_number} has extra columns. Check its commas."
            )

        filename = (row.get("File") or "").strip()

        if not filename:
            raise ValueError(
                f"CSV row {row_number} has an empty filename."
            )

        if filename in seen_files:
            raise ValueError(
                f"Duplicate filename in expected results: {filename}"
            )

        seen_files.add(filename)
        row["File"] = filename

    return rows


def process_samples(expected_rows):
    upload_paths = []

    for row in expected_rows:
        path = SAMPLE_DIR / row["File"]

        if not path.is_file():
            raise FileNotFoundError(
                f"Sample PDF not found: {path}"
            )

        upload_paths.append(path)

    with ExitStack() as stack:
        files = [
            (
                "files",
                (
                    path.name,
                    stack.enter_context(path.open("rb")),
                    "application/pdf",
                ),
            )
            for path in upload_paths
        ]

        response = requests.post(
            API_URL,
            files=files,
            timeout=300,
        )
        response.raise_for_status()
        payload = response.json()

    results = payload.get("results")

    if not isinstance(results, list):
        raise ValueError(
            "API response does not contain a results list."
        )

    actual_by_file = {}

    for result in results:
        if not isinstance(result, dict):
            continue

        filename = str(result.get("File") or "").strip()

        if filename in actual_by_file:
            raise ValueError(
                f"API returned duplicate results for filename: {filename}"
            )

        if filename:
            actual_by_file[filename] = result

    return actual_by_file


def main():
    try:
        expected_rows = load_expected()
        actual_by_file = process_samples(expected_rows)
    except (
        OSError,
        ValueError,
        requests.RequestException,
    ) as error:
        print(f"Evaluation could not run: {error}")
        print("Check the backend, sample PDFs, and expected CSV.")
        sys.exit(1)

    print("\nRECEIPT INTAKE EVALUATION")
    print("=" * 65)
    print(f"Expected documents: {len(expected_rows)}")
    print(f"API result documents: {len(actual_by_file)}")

    matched_files = sum(
        1 for row in expected_rows
        if row["File"] in actual_by_file
    )
    coverage = matched_files / len(expected_rows) * 100

    print(f"Matched expected files: {matched_files}/{len(expected_rows)}")
    print(f"Evaluation coverage: {coverage:.2f}%")

    field_correct = {field: 0 for field in FIELDS}
    field_total = {field: 0 for field in FIELDS}
    mismatches = []

    for expected in expected_rows:
        filename = expected["File"]
        actual = actual_by_file.get(filename)

        if actual is None:
            mismatches.append(
                (
                    filename,
                    "File",
                    filename,
                    "Missing from API results",
                )
            )
            continue

        for field in FIELDS:
            expected_value = expected.get(field, "")
            actual_value = actual.get(field, "")

            field_total[field] += 1

            if normalize(field, expected_value) == normalize(
                field, actual_value
            ):
                field_correct[field] += 1
            else:
                mismatches.append(
                    (
                        filename,
                        field,
                        expected_value,
                        actual_value,
                    )
                )

    print("\nFIELD-WISE ACCURACY")
    print("-" * 65)

    for field in FIELDS:
        total = field_total[field]
        correct = field_correct[field]
        accuracy = correct / total * 100 if total else 0.0

        print(
            f"{field:18} {correct:2}/{total:<2} "
            f"({accuracy:6.2f}%)"
        )

    print("\nMISMATCH DETAILS")
    print("-" * 65)

    if not mismatches:
        print("All evaluated fields match the expected results.")
    else:
        for filename, field, expected_value, actual_value in mismatches:
            print(f"{filename} | {field}")
            print(f"  Expected: {expected_value!r}")
            print(f"  Actual:   {actual_value!r}")

    print("\nSTATUS SUMMARY")
    print("-" * 65)

    status_counts = {}
    for result in actual_by_file.values():
        status = result.get("Status") or "Unknown"
        status_counts[status] = status_counts.get(status, 0) + 1

    for status in ["Done", "Needs review", "Unsupported", "Failed"]:
        print(f"{status:18} {status_counts.get(status, 0)}")

    total_fields = sum(field_total.values())
    total_correct = sum(field_correct.values())
    overall = (
        total_correct / total_fields * 100
        if total_fields
        else 0.0
    )

    print(f"\nOverall field accuracy: {overall:.2f}%")
    print("Note: Each evaluated field has equal weight.")
    print("Accuracy is calculated only for files returned by the API.")

    if matched_files != len(expected_rows) or mismatches:
        print("\nEvaluation result: MISMATCHES FOUND")
    else:
        print("\nEvaluation result: ALL CHECKED FIELDS MATCH")


if __name__ == "__main__":
    main()
