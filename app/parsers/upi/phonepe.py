import re
from app.parsers.upi.base import BaseUPIParser
from app.parsers.upi.normalizer import ParsedTransaction, normalize


class PhonePeParser(BaseUPIParser):
    """
    PhonePe OCR fingerprints:
      - "Tansaction Successful" (OCR misreads Transaction)
      - "Poweredby" or "Powered by" at bottom
      - "Receivedirom" or "Received from" = credit
      - "Paide" or "Paid to" = debit
      - "Creditedto" = credit, "Debitedfrom" = debit
      - "UTR?" label for transaction ID
    """

    def detect(self, texts: list[str]) -> bool:
        cleaned = self._clean_texts(texts)
        for t in cleaned:
            if "tansaction successful" in t:   # PhonePe OCR artifact
                return True
            if "phonepe" in t:
                return True
            if "poweredby" in t or "powered by" in t:
                # Extra check — only PhonePe uses this exact footer
                if any("tansaction" in x or "creditedto" in x or "debitedfrom" in x
                       for x in cleaned):
                    return True
        return False

    def parse(self, texts: list[str]) -> ParsedTransaction | None:
        cleaned = self._clean_texts(texts)

        # Transaction type
        transaction_type = "debit"
        for t in cleaned:
            if "creditedto" in t or "receivedirom" in t or "received from" in t:
                transaction_type = "credit"
                break
            if "debitedfrom" in t or "paide" in t or "paid to" in t:
                transaction_type = "debit"
                break

        # Amount — PhonePe shows a standalone number
        amount = self._find_phonepe_amount(texts, cleaned, transaction_type)

        # Merchant/sender name
        merchant_name = None
        for i, t in enumerate(cleaned):
            if transaction_type == "debit" and ("paide" in t or "paid to" in t):
                if i + 1 < len(texts):
                    name = texts[i + 1].strip()
                    if len(name) > 2:
                        merchant_name = name
                break
            if transaction_type == "credit" and ("receivedirom" in t or "received from" in t):
                if i + 1 < len(texts):
                    # PhonePe merges name and amount: "Chandan 24,30" → take name part
                    raw = texts[i + 1].strip()
                    name_part = re.sub(r"\d+[,.]?\d*$", "", raw).strip()
                    merchant_name = name_part if name_part else raw
                break

        # UPI ID
        upi_id = self._find_upi_id(texts)

        # Transaction ID — PhonePe uses long numeric ID or T-prefixed ID
        transaction_id = None
        for i, t in enumerate(cleaned):
            if "tansaction" in t and "id" in t or "transaction@d" in t:
                if i + 1 < len(texts):
                    m = re.search(r"[T\d][\d]{10,}", texts[i + 1])
                    if m:
                        transaction_id = m.group(0)
                break
        # Fallback — long number in texts
        if not transaction_id:
            for text in texts:
                m = re.search(r"\b\d{15,}\b", text)
                if m:
                    transaction_id = m.group(0)
                    break

        # Status
        status = "success"
        for t in cleaned:
            if "successful" in t:
                status = "success"
                break
            if "failed" in t:
                status = "failed"
                break

        if amount is None:
            return None

        return normalize(
            amount=amount,
            app_source="phonepe",
            raw_texts=texts,
            merchant_name=merchant_name,
            upi_id=upi_id,
            transaction_type=transaction_type,
            status=status,
            transaction_id=transaction_id,
        )

    def _find_phonepe_amount(
        self, texts: list[str], cleaned: list[str], txn_type: str
    ) -> float | None:
        """
        PhonePe shows amount as standalone number or merged with name.
        For credit: "Chandan 24,30" — the trailing number is amount (₹24.30? or separate)
        For debit: standalone number like "81927" — could be ₹819.27
        """
        # Try standalone number in first 8 lines
        for text in texts[:8]:
            m = re.match(r"^[₹R]?(\d{1,6}(?:[.,]\d{1,2})?)$", text.strip())
            if m:
                try:
                    val = float(m.group(1).replace(",", "."))
                    if val > 0:
                        return val
                except ValueError:
                    continue

        # For credit: amount sometimes merged at end of sender name line
        for t in cleaned:
            if txn_type == "credit" and ("receivedirom" in t or "received from" in t):
                idx = cleaned.index(t)
                if idx + 1 < len(texts):
                    m = re.search(r"(\d+[,.]?\d*)$", texts[idx + 1])
                    if m:
                        try:
                            return float(m.group(1).replace(",", "."))
                        except ValueError:
                            pass

        return self._find_amount(texts)