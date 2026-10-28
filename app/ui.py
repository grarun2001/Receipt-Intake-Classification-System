
import logging

import pandas as pd
import requests
import streamlit as st

from app.config import RESULT_COLUMNS

logger = logging.getLogger("receipt_app")

API_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Receipt Intake & Classification",
    page_icon="🧾",
    layout="wide",
)

st.title("Receipt Intake & Classification")
st.caption(
    "Upload expense PDFs to extract key fields, classify documents, "
    "and review processing results."
)

with st.sidebar:
    st.header("Upload documents")

    uploaded_files = st.file_uploader(
        "Choose PDF files",
        type=["pdf"],
        accept_multiple_files=True,
        help="Upload one or more PDF receipts, invoices, tickets, or hotel folios.",
    )

    process_clicked = st.button(
        "Process documents",
        type="primary",
        disabled=not uploaded_files,
        use_container_width=True,
    )

if process_clicked and uploaded_files:
    file_payloads = [
        (
            "files",
            (
                uploaded_file.name,
                uploaded_file.getvalue(),
                "application/pdf",
            ),
        )
        for uploaded_file in uploaded_files
    ]

    try:
        with st.spinner("Processing documents..."):
            response = requests.post(
                f"{API_URL}/process",
                files=file_payloads,
                timeout=300,
            )
            response.raise_for_status()
            payload = response.json()

        new_results = payload.get("results", [])

        if not isinstance(new_results, list):
            raise ValueError("The API results field is not a list.")

        st.session_state["results"] = new_results
        st.success(
            f"Processing completed for {len(new_results)} file(s)."
        )

    except requests.RequestException:
        logger.exception("Could not reach the processing API.")
        st.error(
            "Could not connect to the backend API. "
            "Start FastAPI in another terminal and try again."
        )

    except (ValueError, KeyError):
        logger.exception("The backend returned an invalid response.")
        st.error(
            "The backend response could not be read. Check the API logs."
        )

results = st.session_state.get("results", [])

if results:
    dataframe = pd.DataFrame(results)

    # Ensure expected columns exist even if some results omit a field.
    for column in RESULT_COLUMNS:
        if column not in dataframe.columns:
            dataframe[column] = ""

    # Ensure columns used by the UI are available.
    extra_columns = [
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
        "Extracted Text",
    ]

    for column in extra_columns:
        if column not in dataframe.columns:
            dataframe[column] = ""

    dataframe["File"] = dataframe["File"].fillna("").astype(str)
    dataframe["Status"] = dataframe["Status"].fillna("").astype(str)
    dataframe["Category"] = dataframe["Category"].fillna("").astype(str)

    # Stable per-result identifier handles duplicate filenames.
    dataframe = dataframe.reset_index(drop=True)
    dataframe["_row_id"] = dataframe.index

    st.subheader("Processing overview")

    total_files = len(dataframe)
    done_count = int((dataframe["Status"] == "Done").sum())
    review_count = int((dataframe["Status"] == "Needs review").sum())
    unsupported_count = int((dataframe["Status"] == "Unsupported").sum())
    failed_count = int((dataframe["Status"] == "Failed").sum())

    metric_columns = st.columns(5)
    metrics = [
        ("Total files", total_files),
        ("Done", done_count),
        ("Needs review", review_count),
        ("Unsupported", unsupported_count),
        ("Failed", failed_count),
    ]

    for column, (label, value) in zip(metric_columns, metrics):
        column.metric(label, value)

    st.subheader("Filter results")

    filter_columns = st.columns(2)

    statuses = ["All"] + sorted(
        value for value in dataframe["Status"].unique().tolist() if value
    )
    categories = ["All"] + sorted(
        value for value in dataframe["Category"].unique().tolist() if value
    )

    with filter_columns[0]:
        selected_status = st.selectbox("Status", statuses)

    with filter_columns[1]:
        selected_category = st.selectbox("Category", categories)

    filtered = dataframe.copy()

    if selected_status != "All":
        filtered = filtered[filtered["Status"] == selected_status]

    if selected_category != "All":
        filtered = filtered[filtered["Category"] == selected_category]

    st.subheader("Document results")

    def style_status(row):
        colors = {
            "Done": "#e6f4ea",
            "Needs review": "#fff4ce",
            "Unsupported": "#e8eaf6",
            "Failed": "#fce8e6",
        }
        color = colors.get(row.get("Status", ""), "")
        return [
            f"background-color: {color}" if color else ""
            for _ in row
        ]

    display_columns = [
        column for column in RESULT_COLUMNS
        if column in filtered.columns
    ]

    st.dataframe(
        filtered[display_columns].style.apply(style_status, axis=1),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Confidence": st.column_config.ProgressColumn(
                "Confidence",
                min_value=0.0,
                max_value=1.0,
                format="%.2f",
            ),
        },
    )

    # Export the expected columns only; extracted text stays out of the CSV.
    export_dataframe = dataframe.reindex(columns=RESULT_COLUMNS).copy()
    csv_data = export_dataframe.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        "Export all results to CSV",
        data=csv_data,
        file_name="receipt_processing_results.csv",
        mime="text/csv",
    )

    st.subheader("Document details")

    # Use row identity rather than filename, since filenames can repeat.
    row_options = dataframe["_row_id"].tolist()

    def row_label(row_id):
        row = dataframe.loc[dataframe["_row_id"] == row_id].iloc[0]
        occurrence = int(
            (dataframe.loc[:row_id, "File"] == row["File"]).sum()
        )
        duplicate_count = int((dataframe["File"] == row["File"]).sum())

        if duplicate_count > 1:
            return f"{row['File']} (upload {occurrence})"
        return row["File"] or f"Document {row_id + 1}"

    selected_row_id = st.selectbox(
        "Select a file to inspect",
        options=row_options,
        format_func=row_label,
    )

    selected_row = dataframe.loc[
        dataframe["_row_id"] == selected_row_id
    ].iloc[0]

    detail_columns = st.columns(2)

    with detail_columns[0]:
        st.markdown("**Extracted fields**")

        for field in [
            "Source",
            "Document Type",
            "Category",
            "Vendor",
            "Date",
            "Amount",
            "Currency",
            "Receipt/Invoice Number",
        ]:
            value = selected_row.get(field, "")
            if pd.isna(value) or not str(value).strip():
                value = "—"

            st.write(f"**{field}:** {value}")

    with detail_columns[1]:
        st.markdown("**Processing information**")
        st.write(f"**Status:** {selected_row.get('Status', '')}")
        st.write(f"**Confidence:** {selected_row.get('Confidence', 0)}")
        st.write(f"**Reason:** {selected_row.get('Reason', '') or '—'}")
        st.write(f"**Error:** {selected_row.get('Error', '') or '—'}")

    extracted_text = selected_row.get("Extracted Text", "")

    with st.expander("View extracted / OCR text"):
        if isinstance(extracted_text, str) and extracted_text.strip():
            st.text_area(
                "Extracted document text",
                value=extracted_text,
                height=250,
                disabled=True,
                label_visibility="collapsed",
            )
        else:
            st.info("No extracted text is available for this file.")

    st.subheader("Expense totals by currency")

    done_rows = dataframe[
        (dataframe["Status"] == "Done")
        & dataframe["Amount"].fillna("").astype(str).str.strip().ne("")
        & dataframe["Currency"].fillna("").astype(str).str.strip().ne("")
    ].copy()

    if not done_rows.empty:
        done_rows["Amount"] = pd.to_numeric(
            done_rows["Amount"],
            errors="coerce",
        )

        totals = (
            done_rows.dropna(subset=["Amount"])
            .groupby(["Category", "Currency"], as_index=False)["Amount"]
            .sum()
            .sort_values(["Category", "Currency"])
        )

        totals["Amount"] = totals["Amount"].round(2)

        if not totals.empty:
            st.dataframe(
                totals,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No valid completed expense amounts are available.")
    else:
        st.info("No completed expense amounts are available yet.")

else:
    st.info("Upload one or more PDF files, then select Process documents.")
