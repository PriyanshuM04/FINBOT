import easyocr
import numpy as np
from typing import List

# Initialize once at module level — loading EasyOCR model is expensive
# gpu=False because we're on CPU (Render free tier has no GPU)
_reader = None


def get_reader() -> easyocr.Reader:
    """Lazy-load the EasyOCR reader — only initializes on first call."""
    global _reader
    if _reader is None:
        print("Loading EasyOCR model... (first time only)")
        _reader = easyocr.Reader(["en"], gpu=False)
        print("EasyOCR model loaded.")
    return _reader


def extract_text(image: np.ndarray) -> List[str]:
    """
    Runs EasyOCR on a preprocessed image.
    Returns a flat list of detected text strings in top-to-bottom order.
    """
    reader = get_reader()

    # detail=1 returns (bbox, text, confidence)
    results = reader.readtext(image, detail=1)

    # Sort by vertical position (top to bottom) using bbox y-coordinate
    results_sorted = sorted(results, key=lambda r: r[0][0][1])

    # Filter low confidence results and return just the text
    texts = [text for (_, text, confidence) in results_sorted if confidence > 0.3]

    return texts


def extract_text_with_confidence(image: np.ndarray) -> List[dict]:
    """
    Same as extract_text but returns confidence scores too.
    Useful for debugging parser accuracy.
    """
    reader = get_reader()
    results = reader.readtext(image, detail=1)
    results_sorted = sorted(results, key=lambda r: r[0][0][1])

    return [
        {"text": text, "confidence": round(confidence, 3)}
        for (_, text, confidence) in results_sorted
        if confidence > 0.3
    ]