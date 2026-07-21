"""
Image preprocessing for document extraction: PDF to images, contrast enhancement, resize.
Used by document_processor before sending to OpenAI Vision.
"""
import os
import tempfile
from PIL import Image, ImageEnhance
import fitz


def preprocess_image(file_path: str, log_callback=None) -> list:
    """
    For PDF: render pages to temp images. For images: use as-is.
    Then enhance contrast and resize to max 2048x2048, save as JPEG in a temp dir.
    Returns list of temp processed image paths. Empty on failure.
    Does not write into the input folder.
    """
    ext = file_path.lower().split(".")[-1]
    image_paths = []
    intermediate = []  # PDF page renders to delete after processing
    try:
        if ext == "pdf":
            temp_dir = tempfile.mkdtemp(prefix="digilekha_pdf_")
            pdf_doc = fitz.open(file_path)
            try:
                for page_num in range(len(pdf_doc)):
                    page = pdf_doc.load_page(page_num)
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    path = os.path.join(temp_dir, f"page{page_num}.png")
                    pix.save(path)
                    image_paths.append(path)
                    intermediate.append(path)
            finally:
                pdf_doc.close()
        else:
            image_paths.append(file_path)

        processed = []
        for img_path in image_paths:
            with Image.open(img_path) as img:
                img = img.convert("RGB")
                img = ImageEnhance.Contrast(img).enhance(1.5)
                img.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
                fd, temp_path = tempfile.mkstemp(prefix="digilekha_", suffix="_processed.jpg")
                os.close(fd)
                img.save(temp_path, "JPEG", quality=85)
                processed.append(temp_path)
        return processed
    except Exception as e:
        if log_callback:
            log_callback(f"Error preprocessing {file_path}: {e}", True)
        return []
    finally:
        # Always remove PDF page PNGs so they never linger in input/.
        for p in intermediate:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass
            try:
                parent = os.path.dirname(p)
                if parent and os.path.isdir(parent) and not os.listdir(parent):
                    os.rmdir(parent)
            except Exception:
                pass


def cleanup_temp_files(paths: list) -> None:
    """Remove temporary files; ignore errors."""
    for p in paths:
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass
