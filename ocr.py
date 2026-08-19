"""Rasm -> matn (esse qo'lyozma rasm sifatida yuborilganda).

Izolyatsiyalangan modul: Tesseract binary o'rnatilmagan bo'lsa (masalan VPS'da
hali `apt-get install tesseract-ocr` qilinmagan bo'lsa), import vaqtida xato
bermaydi — `OCR_AVAILABLE = False` bo'ladi va `extract_text_from_image` doim
`None` qaytaradi. Chaqiruvchi (`bot.py`) `None` kelsa foydalanuvchiga
"matn sifatida yuboring" deb aytadi, qolgan bot to'liq ishlayveradi.
"""
from __future__ import annotations

import io
import logging

log = logging.getLogger(__name__)

try:
    import pytesseract
    from PIL import Image

    pytesseract.get_tesseract_version()
    OCR_AVAILABLE = True
except Exception as exc:  # Tesseract binary yo'q yoki pytesseract/Pillow yo'q
    log.warning("OCR mavjud emas (%s) — bot faqat matn bilan ishlaydi", exc)
    OCR_AVAILABLE = False


def extract_text_from_image(image_bytes: bytes) -> str | None:
    """Rasm baytlaridan matnni chiqarib beradi. OCR mavjud bo'lmasa yoki
    tanib bo'lmasa (bo'sh natija) — None qaytaradi."""
    if not OCR_AVAILABLE:
        return None
    try:
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image, lang="eng")
        text = text.strip()
        return text or None
    except Exception:
        log.exception("OCR ishlov berishda xato")
        return None
