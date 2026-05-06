from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class ParsedTransaction:
    """
    Standard output object from every UPI parser.
    No matter which app — GPay, PhonePe, Paytm, Amazon Pay —
    the parser always returns this same structure.
    Everything downstream works with this object only.
    """
    amount: float                        # e.g. 150.0
    merchant_name: Optional[str]         # e.g. "Swiggy", "Rahul Kumar"
    upi_id: Optional[str]               # e.g. "swiggy@icici"
    transaction_type: str               # "debit" or "credit"
    status: str                         # "success", "failed", "pending"
    timestamp: Optional[datetime]       # actual transaction time if found
    transaction_id: Optional[str]       # UPI reference number
    app_source: str                     # "gpay", "phonepe", "paytm", "amazonpay"
    raw_texts: list[str]                # original OCR output — kept for debugging


def normalize(
    amount: float,
    app_source: str,
    raw_texts: list[str],
    merchant_name: str = None,
    upi_id: str = None,
    transaction_type: str = "debit",
    status: str = "success",
    timestamp: datetime = None,
    transaction_id: str = None,
) -> ParsedTransaction:
    """Helper to build a ParsedTransaction cleanly."""
    return ParsedTransaction(
        amount=amount,
        merchant_name=merchant_name,
        upi_id=upi_id,
        transaction_type=transaction_type,
        status=status,
        timestamp=timestamp,
        transaction_id=transaction_id,
        app_source=app_source,
        raw_texts=raw_texts,
    )