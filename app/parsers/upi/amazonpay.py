import re
from app.parsers.upi.base import BaseUPIParser
from app.parsers.upi.normalizer import ParsedTransaction, normalize


class AmazonPayParser(BaseUPIParser):
    """
    Amazon Pay OCR fingerprints:
      - "amazonpay" or "amazompay" (OCR artifact)
      - "Paid successfully" = debit
      - "Received" = credit
      - "Paid to:" → merchant name on next line
      - "Received from" → sender name on next line
      - "UPI transaction ID" label
      - "Amazon reference ID" label
      - UPI IDs end in @apl or @yapl
    """

    def detect(self, texts: list[str]) -> bool:
        cleaned = self._clean_texts(texts)
        for t in cleaned:
            if "amazonpay" in t or "amazompay" in t:
                return True
            if "amazon" in t and ("pay" in t or "reference" in t):
                return True
        return False

    def parse(self, texts: list[str]) -> ParsedTransaction | None:
        cleaned = self._clean_texts(texts)

        # Transaction type
        transaction_type = "debit"
        for t in cleaned:
            if "received" in t and "from" not in t:
                transaction_type = "credit"
                break
            if "paid successfully" in t or "paid to" in t:
                transaction_type = "debit"
                break

        # Amount — appears early in the screenshot as standalone number
        amount = self._find_amazon_amount(texts)
        if amount is None:
            amount = self._find_amount(texts)

        # Merchant/sender name
        merchant_name = None
        for i, t in enumerate(cleaned):
            if transaction_type == "debit" and ("paid to:" in t or "paidto:" in t):
                if i + 1 < len(texts):
                    merchant_name = texts[i + 1].strip()
                break
            if transaction_type == "credit" and ("received from" in t or "receivedirom" in t):
                if i + 1 < len(texts):
                    merchant_name = texts[i + 1].strip()
                break

        # UPI ID — Amazon Pay uses @apl or @yapl suffix
        upi_id = None
        for text in texts:
            m = re.search(r"[\w.\-]+@[ya]?apl", text, re.IGNORECASE)
            if m:
                # Skip own UPI (contains user's phone number)
                upi_id = m.group(0)
                break
        # Fallback to generic UPI finder
        if not upi_id:
            upi_id = self._find_upi_id(texts)

        # Transaction IDs — Amazon Pay has two: UPI txn ID and Amazon ref ID
        upi_txn_id = None
        amazon_ref_id = None

        for i, t in enumerate(cleaned):
            if "upi transaction id" in t:
                if i + 1 < len(texts):
                    upi_txn_id = texts[i + 1].strip()
            if "amazon reference" in t:
                if i + 1 < len(texts):
                    amazon_ref_id = texts[i + 1].strip()

        transaction_id = upi_txn_id or amazon_ref_id

        # Status
        status = "success"
        for t in cleaned:
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
            app_source="amazonpay",
            raw_texts=texts,
            merchant_name=merchant_name,
            upi_id=upi_id,
            transaction_type=transaction_type,
            status=status,
            transaction_id=transaction_id,
        )

    def _find_amazon_amount(self, texts: list[str]) -> float | None:
        """
        Amazon Pay shows amount as standalone number near the top.
        OCR artifacts: {20 = ₹20, 724 = ₹724
        """
        for text in texts[:6]:
            cleaned = text.strip()
            # Remove leading { or ₹ or R
            m = re.match(r"^[{₹R]?(\d+(?:[.,]\d{1,2})?)$", cleaned)
            if m:
                try:
                    val = float(m.group(1).replace(",", "."))
                    if val > 0:
                        return val
                except ValueError:
                    continue
        return None