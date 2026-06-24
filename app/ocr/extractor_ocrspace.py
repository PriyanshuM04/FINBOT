"""
OCR extractor using OCR.space API — no local model, no memory issues.
Replaces EasyOCR for Render deployment.
"""
import httpx
from app.config import settings


def extract_text_from_url(image_url: str, twilio_sid: str, twilio_token: str) -> list[str]:
    """
    Download image from Twilio URL and send to OCR.space API.
    Returns list of text lines extracted from the image.
    """
    # Download image from Twilio
    response = httpx.get(
        image_url,
        auth=(twilio_sid, twilio_token),
        follow_redirects=True,
        timeout=30.0,
    )
    response.raise_for_status()

    image_bytes = response.content
    content_type = response.headers.get("content-type", "image/jpeg")

    # Send to OCR.space API
    import base64
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    base64_image = f"data:{content_type};base64,{b64}"

    ocr_response = httpx.post(
        "https://api.ocr.space/parse/image",
        data={
            "base64Image": base64_image,
            "language": "eng",
            "OCREngine": 2,       # Engine 2 is better for complex layouts
            "isOverlayRequired": False,
            "detectOrientation": True,
            "scale": True,
        },
        headers={"apikey": settings.OCR_SPACE_API_KEY},
        timeout=30.0,
    )

    ocr_response.raise_for_status()
    result = ocr_response.json()

    # Extract text lines from response
    if result.get("IsErroredOnProcessing"):
        error_msg = result.get("ErrorMessage", ["Unknown OCR error"])
        print(f"OCR.space error: {error_msg}")
        return []

    texts = []
    parsed_results = result.get("ParsedResults", [])
    for parsed in parsed_results:
        text = parsed.get("ParsedText", "")
        if text:
            # Split into lines, clean up
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            texts.extend(lines)

    return texts