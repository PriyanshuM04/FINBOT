import re
from app.parsers.upi.base import BaseUPIParser
from app.parsers.upi.normalizer import ParsedTransaction, normalize


class PhonePeParser(BaseUPIParser):
    """
    PhonePe dark theme: ₹ renders as 8 (or sometimes 6) in OCR.
    Amount appears twice — next to merchant and in "Debited/Credited" row.
    Strategy: prefer the amount from "Debited from / Credited to" section
    because it's more reliably read (8-prefix).
    Also skip account-digit patterns like "0518" (4 digits starting with 0).
    """

    def detect(self, texts: list[str]) -> bool:
        cleaned = self._clean_texts(texts)
        full = " ".join(cleaned)
        for t in cleaned:
            if ("phonepe" in t and "@" not in t) or "tansaction" in t:
                return True
        if ("poweredby" in full or "poweled" in full):
            if any(x in full for x in ["tansaction", "creditedto", "debitedfrom", "sentto"]):
                return True
        return False

    def parse(self, texts: list[str]) -> ParsedTransaction | None:
        cleaned = self._clean_texts(texts)

        # Transaction type
        transaction_type = "debit"
        for t in cleaned:
            if any(x in t for x in ["creditedto", "receivedirom", "received from"]):
                transaction_type = "credit"
                break
            if any(x in t for x in ["debitedfrom", "debited from", "debited ttom",
                                      "paide", "paid?o", "sentto", "sent to"]):
                transaction_type = "debit"
                break

        # Amount — prioritise "Debited from / Credited to" section
        amount = self._find_from_section(texts, cleaned, transaction_type)
        if amount is None:
            amount = self._find_phonepe_amount(texts, cleaned)

        # Merchant name
        merchant_name = None
        debit_triggers  = ["paide", "paid to", "paid?o"]
        credit_triggers = ["receivedirom", "received from"]

        for i, t in enumerate(cleaned):
            if transaction_type == "debit" and any(x in t for x in debit_triggers):
                if i + 1 < len(texts):
                    name = texts[i + 1].strip()
                    name = re.sub(r"\s*[86]\d+\.?\d*$", "", name).strip()
                    if len(name) > 2 and not re.match(r"^\d", name):
                        merchant_name = name
                break
            if transaction_type == "credit" and any(x in t for x in credit_triggers):
                if i + 1 < len(texts):
                    raw = texts[i + 1].strip()
                    name_part = re.sub(r"\s*[86]?\d+[,.]?\d*$", "", raw).strip()
                    merchant_name = name_part if name_part else raw
                break

        # UPI ID
        upi_id = self._find_upi_id(texts)

        # Transaction ID — T-prefixed preferred
        transaction_id = None
        for text in texts:
            m = re.search(r"T\d{15,}", text)
            if m:
                transaction_id = m.group(0)
                break
        if not transaction_id:
            for text in texts:
                m = re.search(r"\b\d{18,}\b", text)
                if m:
                    transaction_id = m.group(0)
                    break
        if not transaction_id:
            for text in texts:
                if "utr" in text.lower():
                    m = re.search(r"\d{10,}", text)
                    if m:
                        transaction_id = m.group(0)
                    break

        # Status
        status = "success"
        for t in cleaned:
            if "successful" in t or "successfu" in t:
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

    def _find_from_section(self, texts, cleaned, txn_type) -> float | None:
        """
        Look for amount in the 'Debited from' or 'Credited to' section.
        These rows have account number + amount, e.g. 'XXXX0983  ₹192.70'.
        OCR reads amount as '8XXXX' pattern reliably here.
        """
        section_triggers = ["debitedfrom", "debited from", "debited ttom", "creditedto", "credited to"]
        for i, t in enumerate(cleaned):
            if any(x in t for x in section_triggers):
                # Check next 4 lines for 8-prefix amount
                for j in range(i + 1, min(i + 5, len(texts))):
                    val = self._decode_8prefix(texts[j].strip())
                    if val is not None:
                        return val
                break
        return None

    def _find_phonepe_amount(self, texts, cleaned) -> float | None:
        """Fallback: scan all lines, skip account-digit patterns."""
        for text in texts[:20]:
            t = text.strip()

            # Skip account-digit patterns: 4 digits starting with 0 (e.g. "0518", "0983")
            if re.match(r"^0\d{3}$", t):
                continue

            # 8-prefix with decimal: "83s00" → 3.00
            m = re.match(r"^8(\d+)[s.](\d{2})$", t)
            if m:
                try:
                    val = float(f"{m.group(1)}.{m.group(2)}")
                    if 0 < val < 100000:
                        return val
                except ValueError:
                    pass

            # Standard 8-prefix
            val = self._decode_8prefix(t)
            if val is not None:
                return val

            # Plain number, cap strictly to avoid account digits
            m = re.match(r"^(\d{1,4}(?:\.\d{1,2})?)$", t)
            if m:
                try:
                    val = float(m.group(1))
                    if 0 < val < 10000:
                        return val
                except ValueError:
                    pass

        return self._find_amount(texts)

    def _decode_8prefix(self, t: str) -> float | None:
        """
        PhonePe dark theme: ₹ → 8 in OCR.
        '810' → ₹10, '81927' → ₹192.7, '819270' → ₹192.70
        Also handles '83s00' → ₹3.00 (decimal point → s)
        """
        # With decimal via 's' or '.': "83s00", "83.00"
        m = re.match(r"^8(\d+)[s.](\d{1,2})$", t)
        if m:
            try:
                val = float(f"{m.group(1)}.{m.group(2)}")
                if 0 < val < 100000:
                    return val
            except ValueError:
                pass

        # Pure 8-prefix digits
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

        return None