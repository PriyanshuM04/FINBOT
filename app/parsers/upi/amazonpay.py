import re
from app.parsers.upi.base import BaseUPIParser
from app.parsers.upi.normalizer import ParsedTransaction, normalize


class AmazonPayParser(BaseUPIParser):
    """
    Amazon Pay light theme: ₹ renders correctly BUT small amounts
    like ₹4 and ₹24 get OCR prefix artifacts.
    
    Credit history: "Received" + "₹24" → OCR reads as "724" (7 prefix)
    Live debit:     "Payment Successful" + "₹4" → OCR reads as single digit or misses it
    
    Strategy: find amount ONLY in the top white card section (first 6 lines),
    NOT from account numbers like "2191" which appear lower down.
    """

    def detect(self, texts: list[str]) -> bool:
        cleaned = self._clean_texts(texts)
        for t in cleaned:
            if "amazonpay" in t or "amazompay" in t:
                return True
            if "amazon" in t and any(x in " ".join(cleaned) for x in ["reference", "apl", "yapl"]):
                return True
        return False

    def parse(self, texts: list[str]) -> ParsedTransaction | None:
        cleaned = self._clean_texts(texts)

        # Transaction type
        transaction_type = "debit"
        for t in cleaned:
            if t.strip() in ("received",) or "received" in t and "from" not in t:
                transaction_type = "credit"
                break
            if any(x in t for x in ["paid successfully", "payment successful", "paid to"]):
                transaction_type = "debit"
                break

        # Amount — strictly from top card section only
        amount = self._find_card_amount(texts, cleaned)

        # Merchant name
        merchant_name = None
        for i, t in enumerate(cleaned):
            if transaction_type == "debit" and (
                "paid to:" in t or "paidto:" in t or t == "paid to"
            ):
                if i + 1 < len(texts):
                    name = texts[i + 1].strip()
                    if len(name) > 3:
                        merchant_name = name
                    elif i + 2 < len(texts):
                        merchant_name = texts[i + 2].strip()
                break
            if transaction_type == "credit" and (
                "received from" in t or "receivedirom" in t
            ):
                if i + 1 < len(texts):
                    merchant_name = texts[i + 1].strip()
                break

        # UPI ID — skip own UPI
        upi_id = None
        own_phone = "8521405480"
        for text in texts:
            m = re.search(r"[\w.\-]+@[ya]?[a-z]{2,5}", text, re.IGNORECASE)
            if m:
                if own_phone in text:
                    continue
                upi_id = m.group(0)
                break
        if not upi_id:
            upi_id = self._find_upi_id(texts)

        # Transaction IDs
        upi_txn_id = amazon_ref_id = bank_ref_id = None
        for i, t in enumerate(cleaned):
            if "upi transaction id" in t and i + 1 < len(texts):
                upi_txn_id = texts[i + 1].strip()
            if "amazon reference" in t and i + 1 < len(texts):
                amazon_ref_id = texts[i + 1].strip()
            if "bank reference" in t and i + 1 < len(texts):
                bank_ref_id = texts[i + 1].strip()

        transaction_id = upi_txn_id or amazon_ref_id or bank_ref_id
        if not transaction_id:
            for text in texts:
                m = re.search(r"\b\d{12,}\b", text)
                if m:
                    transaction_id = m.group(0)
                    break

        # Status
        status = "success"
        for t in cleaned:
            if "failed" in t:
                status = "failed"
                break

        return normalize(
            amount=amount if amount is not None else 0.0,
            app_source="amazonpay",
            raw_texts=texts,
            merchant_name=merchant_name,
            upi_id=upi_id,
            transaction_type=transaction_type,
            status=status,
            transaction_id=transaction_id,
        )

    def _find_card_amount(self, texts: list[str], cleaned: list[str]) -> float | None:
        """
        Amazon Pay shows amount in top white card, right after status line.
        Strictly search within 3 lines after the status trigger.
        This avoids picking up account numbers (2191, 0983) from lower sections.

        OCR artifacts on light background:
          ₹24  → "724"  (₹→7)
          ₹20  → "720" or just "20"
          ₹4   → "4" (single digit, sometimes missed)
        """
        status_triggers = ["received", "paid successfully", "payment successful"]

        for i, t in enumerate(cleaned[:10]):
            if any(x in t for x in status_triggers):
                # Search next 3 lines for amount
                for j in range(i + 1, min(i + 4, len(texts))):
                    raw = texts[j].strip()

                    # Standard ₹ prefix
                    m = re.match(r"^[₹](\d+(?:[.,]\d{1,2})?)$", raw)
                    if m:
                        try:
                            return float(m.group(1).replace(",", "."))
                        except ValueError:
                            pass

                    # 7-prefix artifact: "724" → ₹24, "720" → ₹20
                    m = re.match(r"^7(\d{1,4})$", raw)
                    if m:
                        try:
                            val = float(m.group(1))
                            if 0 < val < 10000:
                                return val
                        except ValueError:
                            pass
                    
                    # {-prefix artifact: "{20" → ₹20
                    m = re.match(r"^\{(\d+(?:\.\d{1,2})?)$", raw)
                    if m:
                        try:
                            return float(m.group(1))
                        except ValueError:
                            pass

                    # Plain number — single or double digit amounts
                    m = re.match(r"^(\d{1,4}(?:\.\d{1,2})?)$", raw)
                    if m:
                        try:
                            val = float(m.group(1))
                            # Only trust small numbers here — large = account digits
                            if 0 < val <= 9999:
                                return val
                        except ValueError:
                            pass
                break

        return None