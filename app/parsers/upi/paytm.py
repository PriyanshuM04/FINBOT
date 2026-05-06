import re
from app.parsers.upi.base import BaseUPIParser
from app.parsers.upi.normalizer import ParsedTransaction, normalize


class PaytmParser(BaseUPIParser):
    """
    Paytm OCR fingerprints:
      - "payim" or "paytm" (OCR misreads logo)
      - "Paid Successfully" / "Money Received"
      - "Rupees X Only" — word-form amount (most reliable)
      - "To: MerchantName" / "From: SenderName"
      - "UPI Ref No:" or "Upi Ref No:"
    """

    # Words that can appear in word-amount: "Rupees One Hundred Thirty Only"
    WORD_NUMBERS = {
        "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
        "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
        "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
        "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
        "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
        "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
        "eighty": 80, "ninety": 90, "hundred": 100, "thousand": 1000,
        "lakh": 100000,
    }

    def detect(self, texts: list[str]) -> bool:
        cleaned = self._clean_texts(texts)
        for t in cleaned:
            if "payim" in t or "paytm" in t:
                return True
        return False

    def parse(self, texts: list[str]) -> ParsedTransaction | None:
        cleaned = self._clean_texts(texts)

        # Transaction type
        transaction_type = "debit"
        for t in cleaned:
            if "money received" in t or "received" in t:
                transaction_type = "credit"
                break
            if "paid successfully" in t or "paid" in t:
                transaction_type = "debit"
                break

        # Amount — try word form first (most reliable for Paytm)
        amount = self._parse_word_amount(texts)
        if amount is None:
            amount = self._find_amount(texts)

        # Merchant/sender name
        merchant_name = None
        for i, t in enumerate(cleaned):
            if t.startswith("to:") and transaction_type == "debit":
                raw = texts[i].replace("To:", "").replace("to:", "").strip()
                merchant_name = raw
                break
            if t.startswith("from:") and transaction_type == "credit":
                raw = texts[i].replace("From:", "").replace("from:", "").strip()
                merchant_name = raw
                break

        # UPI ID
        upi_id = self._find_upi_id(texts)

        # Transaction ref
        transaction_id = None
        for i, t in enumerate(cleaned):
            if "upi ref no" in t:
                m = re.search(r"\d{10,}", texts[i])
                if m:
                    transaction_id = m.group(0)
                elif i + 1 < len(texts):
                    m2 = re.search(r"\d{10,}", texts[i + 1])
                    if m2:
                        transaction_id = m2.group(0)
                break

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
            app_source="paytm",
            raw_texts=texts,
            merchant_name=merchant_name,
            upi_id=upi_id,
            transaction_type=transaction_type,
            status=status,
            transaction_id=transaction_id,
        )

    def _parse_word_amount(self, texts: list[str]) -> float | None:
        """
        Parses 'Rupees One Hundred Thirty Only' → 130.0
        Paytm always includes this line — very reliable.
        """
        for text in texts:
            if "rupees" in text.lower() and "only" in text.lower():
                words = re.sub(r"[^a-zA-Z\s]", "", text).lower().split()
                try:
                    amount = self._words_to_number(words)
                    if amount and amount > 0:
                        return float(amount)
                except Exception:
                    pass
        return None

    def _words_to_number(self, words: list[str]) -> int:
        total = 0
        current = 0
        for word in words:
            if word in ("rupees", "only", "and"):
                continue
            val = self.WORD_NUMBERS.get(word)
            if val is None:
                continue
            if val == 100:
                current = current * 100 if current else 100
            elif val == 1000:
                total += (current or 1) * 1000
                current = 0
            elif val == 100000:
                total += (current or 1) * 100000
                current = 0
            else:
                current += val
        total += current
        return total