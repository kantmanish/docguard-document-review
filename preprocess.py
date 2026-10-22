"""PDF/image loading and optional OpenCV cleanup."""
from io import BytesIO
from PIL import Image, ImageOps
import numpy as np
def load_image(file_bytes: bytes, filename: str) -> Image.Image:
    suffix=(filename or "").lower()
    if suffix.endswith(".pdf") or file_bytes[:4]==b"%PDF":
        import pypdfium2 as pdfium
        pdf=pdfium.PdfDocument(file_bytes)
        if len(pdf)==0: raise ValueError("The PDF contains no pages.")
        bitmap=pdf[0].render(scale=1.8)
        return bitmap.to_pil().convert("RGB")
    return Image.open(BytesIO(file_bytes)).convert("RGB")
def preprocess_image(image: Image.Image) -> Image.Image:
    try:
        import cv2
        arr=np.array(image.convert("RGB"))
        bgr=cv2.cvtColor(arr,cv2.COLOR_RGB2BGR)
        gray=cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY)
        denoised=cv2.fastNlMeansDenoising(gray,None,10,7,21)
        # Keep a clean grayscale image; avoid aggressive thresholding that erases faint text.
        return Image.fromarray(denoised)
    except Exception:
        return ImageOps.grayscale(image)
