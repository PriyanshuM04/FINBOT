from app.parsers.upi.gpay import GPayParser
from app.parsers.upi.phonepe import PhonePeParser
from app.parsers.upi.paytm import PaytmParser
from app.parsers.upi.amazonpay import AmazonPayParser
from app.parsers.upi.normalizer import ParsedTransaction

# All parsers in priority order
PARSERS = [
    PhonePeParser(),
    GPayParser(),
    PaytmParser(),
    AmazonPayParser(),
]


def parse_upi_screenshot(texts: list[str]) -> ParsedTransaction | None:
    """
    Given OCR text lines from a UPI screenshot,
    auto-detects the app and returns a ParsedTransaction.
    Returns None if no parser can handle it.
    """
    for parser in PARSERS:
        if parser.detect(texts):
            result = parser.parse(texts)
            if result:
                return result

    return None