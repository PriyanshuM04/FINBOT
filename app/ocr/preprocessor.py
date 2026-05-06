import cv2
import numpy as np


def preprocess_image(image_path: str) -> np.ndarray:
    """
    Prepares a raw Android screenshot for EasyOCR.
    Steps: load → resize → grayscale → denoise → sharpen → threshold
    Returns a numpy array ready for OCR.
    """
    # Load image
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not load image at {image_path}")

    # Resize if too large — Android screenshots can be 1080x2400+
    # EasyOCR works best around 1080px wide
    h, w = img.shape[:2]
    if w > 1080:
        scale = 1080 / w
        img = cv2.resize(img, (1080, int(h * scale)), interpolation=cv2.INTER_AREA)

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Denoise — removes JPEG compression artifacts
    denoised = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)

    # Sharpen — improves text edge clarity
    kernel = np.array([[0, -1, 0],
                       [-1, 5, -1],
                       [0, -1, 0]])
    sharpened = cv2.filter2D(denoised, -1, kernel)

    # Adaptive threshold — handles uneven lighting across screenshot
    thresh = cv2.adaptiveThreshold(
        sharpened, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=11,
        C=2
    )

    return thresh


def preprocess_image_bytes(image_bytes: bytes) -> np.ndarray:
    """
    Same as preprocess_image but takes raw bytes instead of file path.
    Used when image comes from Twilio (downloaded from URL, not saved to disk).
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image bytes")

    # Reuse same pipeline — save to temp numpy array
    h, w = img.shape[:2]
    if w > 1080:
        scale = 1080 / w
        img = cv2.resize(img, (1080, int(h * scale)), interpolation=cv2.INTER_AREA)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)

    kernel = np.array([[0, -1, 0],
                       [-1, 5, -1],
                       [0, -1, 0]])
    sharpened = cv2.filter2D(denoised, -1, kernel)

    thresh = cv2.adaptiveThreshold(
        sharpened, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=11,
        C=2
    )

    return thresh