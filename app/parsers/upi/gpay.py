import re
from app.parsers.upi.base import BaseUPIParser
from app.parsers.upi.normalizer import ParsedTransaction, normalize


class GPayParser(BaseUPIParser):
    """
    GPay OCR fingerprints:
      - "googlepay" or "google" in texts
      - "POWERED BY Pay" at bottom
      - "Completed" as status
      - Amount appears as "R45" (₹ misread as R)
      - "From PRIYANSHUMALLICK" = debit (sent from user)
      - "to: PRIYANSHUMALLICK" = credit (received by user)
      - "Google transaction id" label
    """

    def detect(self, texts: list[str]) -> bool:
        cleaned = self._clean_texts(texts)
        for t in cleaned:
            if "googlepay" in t or ("google" in t and "pay" in t):
                return True
            if "googlepayr" in t or "googlepaye" in t:   # OCR merges prefix
                return True
        return False

    def parse(self, texts: list[str]) -> ParsedTransaction | None:
        cleaned = self._clean_texts(texts)

        # Transaction type — GPay shows your name in "From" for debit
        # and "to:" for credit
        transaction_type = "debit"
        user_indicators = ["priyanshumallick", "priyanshu"]   # will generalise later

        for t in cleaned:
            if t.startswith("from") and any(u in t for u in user_indicators):
                transaction_type = "debit"
                break
            if t.startswith("to:") and any(u in t for u in user_indicators):
                transaction_type = "credit"
                break

        # Amount — GPay shows as R45, R100 (₹ misread as R)
        amount = self._find_gpay_amount(texts)
        if amount is None:
            amount = self._find_amount(texts)

        # Merchant/sender UPI ID
        # For debit: recipient UPI is the non-user UPI
        # For credit: sender UPI has their phone number prefix
        upi_id = None
        merchant_name = None
        own_upi_fragments = ["okaxis", "oksbi", "okicici", "okhdfcbank", "okaxis"]

        for text in texts:
            m = re.search(r"[\w.\-]+@[\w]+", text)
            if m:
                found = m.group(0).lower()
                # Skip own UPI
                if "priyanshu" in found or "mallick" in found:
                    continue
                upi_id = m.group(0)
                break

        # Sender name for credit — appears before phone number
        if transaction_type == "credit":
            for i, t in enumerate(cleaned):
                # GPay shows "AryanKashyap" merged with "om" prefix due to OCR
                if re.search(r"[a-z]{3,}\s+[a-z]{3,}", t) and i < 3:
                    merchant_name = texts[i].strip()
                    break

        # Transaction ID — 12-digit number
        transaction_id = None
        for text in texts:
            m = re.search(r"\b\d{12}\b", text)
            if m:
                transaction_id = m.group(0)
                break

        # Status
        status = "success"
        for t in cleaned:
            if "completed" in t:
                status = "success"
                break
            if "failed" in t:
                status = "failed"
                break
            if "pending" in t:
                status = "pending"
                break

        if amount is None:
            return None

        return normalize(
            amount=amount,
            app_source="gpay",
            raw_texts=texts,
            merchant_name=merchant_name,
            upi_id=upi_id,
            transaction_type=transaction_type,
            status=status,
            transaction_id=transaction_id,
        )

    def _find_gpay_amount(self, texts: list[str]) -> float | None:
        """GPay shows amount as R45, R100 near the top of screenshot."""
        for text in texts[:5]:   # amount usually in first 5 lines
            m = re.match(r"^[R₹](\d+(?:[.,]\d{1,2})?)$", text.strip())
            if m:
                try:
                    return float(m.group(1).replace(",", "."))
                except ValueError:
                    continue
        return None