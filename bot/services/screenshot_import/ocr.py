"""OCR банковских скринов: несколько проходов Tesseract + сборка строк по координатам."""

from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

_TESS_CONFIG = r"--oem 3 --psm 6 -c preserve_interword_spaces=1"
_TESS_CONFIG_BLOCK = r"--oem 3 --psm 4 -c preserve_interword_spaces=1"
_TESS_CONFIG_SPARSE = r"--oem 3 --psm 11 -c preserve_interword_spaces=1"


@dataclass(frozen=True)
class OcrResult:
    lines: tuple[str, ...]
    raw_text: str
    score: int


def _load_image(image_bytes: bytes) -> Image.Image:
    img = Image.open(BytesIO(image_bytes))
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    return img


def _scale_up(img: Image.Image, *, min_side: int = 1400, max_side: int = 2200) -> Image.Image:
    """Масштаб для OCR: не слишком мелко и не раздувать огромные скрины."""
    side = max(img.size)
    if side < min_side:
        scale = min_side / side
        return img.resize(
            (int(img.width * scale), int(img.height * scale)),
            Image.Resampling.LANCZOS,
        )
    if side > max_side:
        scale = max_side / side
        return img.resize(
            (int(img.width * scale), int(img.height * scale)),
            Image.Resampling.LANCZOS,
        )
    return img


def _variant_standard(img: Image.Image) -> Image.Image:
    scaled = _scale_up(img)
    gray = ImageOps.grayscale(scaled)
    sharp = gray.filter(ImageFilter.SHARPEN)
    return ImageEnhance.Contrast(sharp).enhance(2.2)


def _variant_autocontrast(img: Image.Image) -> Image.Image:
    scaled = _scale_up(img)
    gray = ImageOps.autocontrast(ImageOps.grayscale(scaled), cutoff=1)
    return ImageEnhance.Sharpness(gray).enhance(1.6)


def _variant_binary(img: Image.Image) -> Image.Image:
    scaled = _scale_up(img)
    gray = ImageOps.grayscale(scaled)
    return gray.point(lambda p: 255 if p > 155 else 0, mode="1").convert("L")


def _variant_inverted(img: Image.Image) -> Image.Image:
    """Тёмная тема банковских приложений."""
    scaled = _scale_up(img)
    gray = ImageOps.grayscale(scaled)
    inverted = ImageOps.invert(gray)
    return ImageEnhance.Contrast(inverted).enhance(1.8)


def _normalize_line(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("'", "'").replace("`", "'")
    text = text.replace("Р", "₽").replace("р.", "₽").replace("руб.", "₽").replace("руб", "₽")
    # OCR часто читает ₽ как P / ® / 2 в конце строки
    text = re.sub(
        r"(\d[\d\s.,]*)\s*(?:P|®)[@]?(?=\s|$)",
        r"\1 ₽",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(\d{3,})\s*®(?=\s|$)",
        r"\1 ₽",
        text,
    )
    text = re.sub(r"([\d.,]+)\s*2\s*$", r"\1 ₽", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _lines_from_tesseract_data(
    img: Image.Image, *, config: str = _TESS_CONFIG
) -> list[str]:
    import pytesseract
    from pytesseract import Output

    data = pytesseract.image_to_data(
        img,
        lang="rus+eng",
        config=config,
        output_type=Output.DICT,
    )
    n = len(data["text"])
    buckets: dict[tuple[int, int, int], list[tuple[int, str]]] = {}

    for i in range(n):
        word = (data["text"][i] or "").strip()
        if not word:
            continue
        try:
            conf = int(float(data["conf"][i]))
        except (ValueError, TypeError):
            conf = -1
        if conf < 25:
            continue
        key = (
            data["block_num"][i],
            data["par_num"][i],
            data["line_num"][i],
        )
        left = int(data["left"][i])
        buckets.setdefault(key, []).append((left, word))

    lines: list[str] = []
    for key in sorted(buckets.keys()):
        parts = sorted(buckets[key], key=lambda x: x[0])
        line = _normalize_line(" ".join(w for _, w in parts))
        if len(line) >= 2:
            lines.append(line)
    return lines


def _full_text(img: Image.Image, *, sparse: bool = False) -> str:
    import pytesseract

    config = _TESS_CONFIG_SPARSE if sparse else _TESS_CONFIG
    return pytesseract.image_to_string(img, lang="rus+eng", config=config) or ""


def _score_ocr(lines: list[str], raw: str) -> int:
    blob = "\n".join(lines) + raw
    score = 0
    score += blob.count("₽") * 8
    score += len(re.findall(r"[+\-−–]", blob)) * 2
    score += len(
        re.findall(
            r"\d{1,3}(?:\s\d{3})+[.,]\d{2}|\d+[.,]\d{2}\s*₽",
            blob,
            re.IGNORECASE,
        )
    ) * 5
    score += min(len(lines), 80)
    return score


# Достаточно для парсера — не гоняем остальные варианты картинки.
_GOOD_OCR_SCORE = 28


def _ocr_pass(img: Image.Image, *, use_block_mode: bool = False) -> OcrResult:
    """Один вариант картинки: 1–2 вызова Tesseract вместо пяти."""
    line_sets: list[list[str]] = [_lines_from_tesseract_data(img)]
    if use_block_mode:
        line_sets.append(_lines_from_tesseract_data(img, config=_TESS_CONFIG_BLOCK))
    raw = _full_text(img)
    line_sets.append(_line_list_from_text(raw))
    lines = _merge_line_lists(*line_sets)
    return OcrResult(lines=tuple(lines), raw_text=raw, score=_score_ocr(lines, raw))


def _line_list_from_text(text: str) -> list[str]:
    return [_normalize_line(ln) for ln in text.splitlines() if _normalize_line(ln)]


def _merge_line_lists(*sources: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for source in sources:
        for line in source:
            norm = line.lower()
            if norm in seen:
                continue
            seen.add(norm)
            merged.append(line)
    return merged


def extract_ocr_result(image_bytes: bytes) -> OcrResult:
    """
    OCR с ранним выходом: сначала быстрый проход, тяжёлые варианты — только если мало текста.
    Раньше было ~20 запусков Tesseract на фото; теперь обычно 2–6.
    """
    base = _load_image(image_bytes)
    passes: list[tuple[Image.Image, bool]] = [
        (_variant_standard(base), False),
        (_variant_autocontrast(base), False),
        (_variant_inverted(base), True),
        (_variant_binary(base), True),
    ]

    best: OcrResult | None = None
    for img, block_mode in passes:
        candidate = _ocr_pass(img, use_block_mode=block_mode)
        if best is None or candidate.score > best.score:
            best = candidate
        if best.score >= _GOOD_OCR_SCORE:
            return best

    assert best is not None
    return best


def image_to_text(image_bytes: bytes) -> str:
    """Совместимость: сплошной текст лучшего прохода."""
    result = extract_ocr_result(image_bytes)
    if result.lines:
        return "\n".join(result.lines)
    return result.raw_text
