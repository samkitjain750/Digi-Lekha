"""
Image preprocessing for document extraction: PDF to images, contrast enhancement, resize.
Used by document_processor before sending to Gemini.
"""
import os
from PIL import Image, ImageEnhance
import fitz


def preprocess_image(file_path: str, log_callback=None) -> list:
    """
    For PDF: render pages to images. For images: use as-is.
    Then enhance contrast and resize to max 2048x2048, save as JPEG.
    Returns list of temp processed image paths. Empty on failure.
    """
    ext = file_path.lower().split(".")[-1]
    image_paths = []
    try:
        if ext == "pdf":
            pdf_doc = fitz.open(file_path)
            for page_num in range(len(pdf_doc)):
                page = pdf_doc.load_page(page_num)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                path = f"{file_path}_page{page_num}.png"
                pix.save(path)
                image_paths.append(path)
        else:
            image_paths.append(file_path)

        processed = []
        for img_path in image_paths:
            with Image.open(img_path) as img:
                img = img.convert("RGB")
                img = ImageEnhance.Contrast(img).enhance(1.5)
                img.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
                temp_path = f"{img_path}_processed.jpg"
                img.save(temp_path, "JPEG", quality=85)
                processed.append(temp_path)
        return processed
    except Exception as e:
        if log_callback:
            log_callback(f"Error preprocessing {file_path}: {e}", True)
        return []


def cleanup_temp_files(paths: list) -> None:
    """Remove temporary files; ignore errors."""
    for p in paths:
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass
