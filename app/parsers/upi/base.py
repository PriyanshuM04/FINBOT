from abc import ABC, abstractmethod
from app.parsers.upi.normalizer import ParsedTransaction


class BaseUPIParser(ABC):
    """
    All UPI parsers inherit from this.
    Each parser implements detect() and parse().
    """

    @abstractmethod
    def detect(self, texts: list[str]) -> bool:
        """
        Returns True if this parser should handle these OCR texts.
        Each app has unique fingerprint words to detect it.
        """
        pass

    @abstractmethod
    def parse(self, texts: list[str]) -> ParsedTransaction | None:
        """
        Extracts transaction data from OCR texts.
        Returns ParsedTransaction or None if parsing fails.
        """
        pass

    def _find_amount(self, texts: list[str]) -> float | None:
        """
        Shared amount extraction logic.
        Handles OCR artifacts: R45 = ₹45, {20 = ₹20, 7130 = ₹130 etc.
        """
        import re

        for text in texts:
            cleaned = text.strip()

            # Direct ₹ prefix: ₹130, ₹45.50
            m = re.match(r"[₹R\{](\d+(?:[.,]\d{1,2})?)", cleaned)
            if m:
                amount_str = m.group(1).replace(",", ".")
                try:
                    return float(amount_str)
                except ValueError:
                    continue

        return None

    def _find_upi_id(self, texts: list[str]) -> str | None:
        """Finds UPI ID pattern like name@bank in OCR texts."""
        import re
        upi_pattern = re.compile(r"[\w.\-]+@[\w]+", re.IGNORECASE)
        for text in texts:
            m = upi_pattern.search(text)
            if m:
                return m.group(0)
        return None

    def _clean_texts(self, texts: list[str]) -> list[str]:
        """Lowercase stripped version for easier matching."""
        return [t.strip().lower() for t in texts]