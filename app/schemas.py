
from typing import Any, Literal

from pydantic import BaseModel, Field


ProcessingStatus = Literal[
    "Done",
    "Needs review",
    "Unsupported",
    "Failed",
]


class HealthResponse(BaseModel):
    status: str = "healthy"


class DocumentResult(BaseModel):
    File: str
    Source: str = ""
    Document_Type: str = Field(
        default="",
        alias="Document Type",
    )
    Category: str = ""
    Vendor: str = ""
    Date: str = ""
    Amount: str = ""
    Currency: str = ""
    Receipt_Invoice_Number: str = Field(
        default="",
        alias="Receipt/Invoice Number",
    )
    Confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    Reason: str = ""
    Status: ProcessingStatus = "Needs review"
    Error: str = ""
    Extracted_Text: str = Field(
        default="",
        alias="Extracted Text",
    )

    model_config = {
        "populate_by_name": True,
        "extra": "allow",
    }


class ProcessFilesResponse(BaseModel):
    total_files: int = Field(ge=0)
    results: list[DocumentResult] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: str
