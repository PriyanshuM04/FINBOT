"""
Tests all UPI parsers against screenshots in sample_data/screenshots/.
Shows what each parser extracts — amount, merchant, type, status.

Usage:
    python scripts/test_parsers.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ocr.preprocessor import preprocess_image
from app.ocr.extractor import extract_text
from app.parsers.upi.router import parse_upi_screenshot

SCREENSHOTS_DIR = "sample_data/screenshots"


def test_file(filepath: str):
    print(f"\n{'='*60}")
    print(f"FILE: {os.path.basename(filepath)}")
    print("="*60)

    try:
        image = preprocess_image(filepath)
        texts = extract_text(image)
        result = parse_upi_screenshot(texts)

        if result:
            print(f"  App:          {result.app_source}")
            print(f"  Type:         {result.transaction_type}")
            print(f"  Amount:       ₹{result.amount}")
            print(f"  Merchant:     {result.merchant_name}")
            print(f"  UPI ID:       {result.upi_id}")
            print(f"  Status:       {result.status}")
            print(f"  Txn ID:       {result.transaction_id}")
        else:
            print("  ❌ No parser matched this screenshot")
            print("  Raw OCR texts:")
            for i, t in enumerate(texts):
                print(f"    [{i:02d}] {t}")

    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()


def main():
    files = [
        f for f in os.listdir(SCREENSHOTS_DIR)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]

    if not files:
        print("No screenshots found.")
        return

    print(f"Testing {len(files)} screenshots...\n")

    passed = 0
    failed = 0

    for filename in sorted(files):
        filepath = os.path.join(SCREENSHOTS_DIR, filename)
        test_file(filepath)

    print(f"\n{'='*60}")
    print("Done.")


if __name__ == "__main__":
    main()