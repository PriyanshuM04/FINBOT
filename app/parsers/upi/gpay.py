import re
from app.parsers.upi.base import BaseUPIParser
from app.parsers.upi.normalizer import ParsedTransaction, normalize

GPAY_UPI_SUFFIXES = ["@okaxis", "@okaxs", "@oksbi", "@okicici", "@okhdfcbank", "@okhdfc"]

# OCR substitution map for GPay large amount display
OCR_CHAR_MAP = str.maketrans({
    'i': '1', 'I': '1', 'l': '1',
    'o': '0', 'O': '0',
    's': '',  'S': '',   # decimal point sometimes reads as 's'
    'e': '',  'E': '',   # ₹ reads as 'e'
    'g': '9',
})


class GPayParser(BaseUPIParser):
    """
    GPay dark theme: ₹ renders correctly BUT OCR misreads digits.
    ₹100 → "ei00"   (₹→e, 1→i, then 00)
    ₹45  → "R45"    (₹→R)
    ₹3   → "83s00"  (₹→8, .→s on live minimal screen) wait no —
           Live GPay minimal: "83s00" = ₹3.00 (8=₹, 3=3, s=., 00=00)

    Transaction ID: 12-digit UPI txn ID.
    Phone numbers (+91XXXXXXXXXX = 12 digits with +91) must be excluded.
    """

    def detect(self, texts: list[str]) -> bool:
        cleaned = self._clean_texts(texts)

        for t in cleaned:
            if "google" in t:
                return True
            for suffix in GPAY_UPI_SUFFIXES:
                if suffix in t:
                    return True

        full = " ".join(cleaned)
        if ("poweredby" in full or "powered by" in full) and "completed" in full:
            return True

        # Live GPay: "paidto" without other app markers
        if "paidto" in full or "paid to" in full:
            if not any(x in full for x in ["tansaction", "payim", "paytm",
                                             "amazonpay", "amazompay"]):
                return True

        return False

    def parse(self, texts: list[str]) -> ParsedTransaction | None:
        cleaned = self._clean_texts(texts)

        # Transaction type
        transaction_type = "debit"
        user_fragments = ["priyanshumallick", "priyanshu", "mallick"]

        for t in cleaned:
            # "to:PRIYANSHUMALLICK" → credit (money came to user)
            if re.match(r"to[:\s]", t) and any(u in t for u in user_fragments):
                transaction_type = "credit"
                break
            # "from priyanshu..." → debit (sent by user)
            if t.startswith("from") and any(u in t for u in user_fragments):
                transaction_type = "debit"
                break

        # Amount
        amount = self._find_gpay_amount(texts)
        if amount is None:
            amount = self._find_amount(texts)

        # Merchant / sender name
        merchant_name = None
        if transaction_type == "credit":
            for i, t in enumerate(cleaned):
                if t.startswith("from") or t.startswith("(om"):
                    raw = texts[i]
                    raw = re.sub(r"(?i)^[\(]?from[:\s]*", "", raw).strip()
                    raw = re.sub(r"\+?\d[\d\s]{8,}", "", raw).strip()
                    raw = re.sub(r"\(.*?\)", "", raw).strip()
                    if raw and not any(u in raw.lower() for u in user_fragments):
                        merchant_name = raw
                        break

        if transaction_type == "debit":
            for i, t in enumerate(cleaned):
                if "paidto" in t or t == "paid to":
                    if i + 1 < len(texts):
                        merchant_name = texts[i + 1].strip()
                    break
            # Fallback: "To: Merchant Name" line
            if not merchant_name:
                for i, t in enumerate(cleaned):
                    if t.startswith("to:") and not any(u in t for u in user_fragments):
                        raw = texts[i].split(":", 1)[-1].strip()
                        if raw:
                            merchant_name = raw
                        break

        # UPI ID — skip own
        upi_id = None
        own_fragments = ["priyanshu", "mallick", "2004"]
        for text in texts:
            m = re.search(r"[\w.\-]+@[\w]+", text)
            if m:
                found = m.group(0).lower()
                if any(f in found for f in own_fragments):
                    continue
                upi_id = m.group(0)
                break

        # Transaction ID — 12-digit UPI txn ID
        # Must exclude phone numbers: +91XXXXXXXXXX starts with country code
        transaction_id = None
        for text in texts:
            # Skip lines with phone numbers
            if re.search(r"\+91\s*\d{10}", text):
                continue
            if re.search(r"#91\d{10}", text):
                continue
            m = re.search(r"\b(\d{12})\b", text)
            if m:
                candidate = m.group(1)
                # Phone numbers starting with 91 followed by 10-digit number
                if candidate.startswith("91") and len(candidate) == 12:
                    continue
                transaction_id = candidate
                break

        # Status
        status = "success"
        for t in cleaned:
            if "completed" in t or "successful" in t:
                status = "success"
                break
            if "failed" in t:
                status = "failed"
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
        """
        Handle all GPay amount OCR artifacts:
          ₹45   → "R45"     R-prefix
          ₹100  → "ei00"    ₹→e, 1→i
          ₹3.00 → "83s00"   live minimal: 8=₹, 3=3, s=decimal, 00=00
        """
        for text in texts[:8]:
            t = text.strip()

            # R-prefix: "R45", "R100"
            m = re.match(r"^[R₹](\d+(?:\.\d{1,2})?)$", t)
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    pass

            # Live GPay minimal: "83s00" → ₹3.00
            m = re.match(r"^8(\d+)[sS.](\d{2})$", t)
            if m:
                try:
                    val = float(f"{m.group(1)}.{m.group(2)}")
                    if 0 < val < 100000:
                        return val
                except ValueError:
                    pass

            # 8-prefix without decimal: "810" → ₹10 etc.
            m = re.match(r"^8(\d{1,5})$", t)
            if m:
                inner = m.group(1)
                n = len(inner)
                try:
                    if n <= 3:
                        val = float(inner)
                    elif n == 4:
                        val = float(inner) / 10
                    else:
                        val = float(inner) / 100
                    if 0 < val < 100000:
                        return val
                except ValueError:
                    pass

            # OCR artifact starting with letters: "ei00" → translate → "100"
            if re.match(r"^[a-zA-Z]{1,2}\d{2,}$", t):
                translated = t.translate(OCR_CHAR_MAP)
                digits = re.sub(r"[^0-9]", "", translated)
                if digits:
                    try:
                        val = float(digits)
                        if 0 < val < 1000000:
                            return val
                    except ValueError:
                        pass

        return None