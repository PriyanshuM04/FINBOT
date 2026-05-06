"""
Run this script to see raw OCR output on your sample screenshots.
This tells us exactly what text EasyOCR extracts before we write any parsers.

Usage:
    python scripts/test_ocr.py
"""

import sys
import os

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ocr.preprocessor import preprocess_image
from app.ocr.extractor import extract_text_with_confidence

SCREENSHOTS_DIR = "sample_data/screenshots"


def test_screenshot(filepath: str):
    print(f"\n{'='*60}")
    print(f"FILE: {filepath}")
    print("="*60)

    try:
        image = preprocess_image(filepath)
        results = extract_text_with_confidence(image)

        for i, item in enumerate(results):
            print(f"[{i:02d}] ({item['confidence']:.2f}) {item['text']}")

    except Exception as e:
        print(f"ERROR: {e}")


def main():
    if not os.path.exists(SCREENSHOTS_DIR):
        print(f"Directory not found: {SCREENSHOTS_DIR}")
        return

    files = [
        f for f in os.listdir(SCREENSHOTS_DIR)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]

    if not files:
        print("No screenshots found in sample_data/screenshots/")
        return

    print(f"Found {len(files)} screenshots. Running OCR...\n")

    for filename in sorted(files):
        filepath = os.path.join(SCREENSHOTS_DIR, filename)
        test_screenshot(filepath)

    print(f"\n{'='*60}")
    print("Done. Use this output to build your parsers.")


if __name__ == "__main__":
    main()