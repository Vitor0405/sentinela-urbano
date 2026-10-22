"""Photo intake: validation, EXIF removal and storage.

Every uploaded photo is decoded and re-encoded as a fresh JPEG. Nothing from the original
file's metadata survives (EXIF, GPS, camera serial, XMP, ICC). The EXIF orientation is
applied to the pixels first so the photo is not shown sideways after stripping.
"""

import io
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

register_heif_opener()

# Refuse decompression bombs well before Pillow's own limit.
MAX_PIXELS = 50_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "HEIF", "MPO"}


class InvalidPhotoError(ValueError):
    """Raised with a pt-BR message suitable for the API response."""


@dataclass(frozen=True)
class ProcessedPhoto:
    data: bytes
    width: int
    height: int
    content_type: str = "image/jpeg"


def sanitize_image(raw: bytes, *, max_side: int, max_bytes: int) -> ProcessedPhoto:
    if len(raw) == 0:
        raise InvalidPhotoError("A foto enviada está vazia.")
    if len(raw) > max_bytes:
        limit_mb = max_bytes // (1024 * 1024)
        raise InvalidPhotoError(f"Cada foto pode ter no máximo {limit_mb} MB.")
    try:
        with Image.open(io.BytesIO(raw)) as img:
            if img.format not in ALLOWED_FORMATS:
                raise InvalidPhotoError(
                    "Formato de imagem não aceito. Use JPEG, PNG, WEBP ou HEIC."
                )
            if img.width * img.height > MAX_PIXELS:
                raise InvalidPhotoError("A imagem tem resolução grande demais.")
            img.load()
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGB")
            img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            # Copy the pixels into a brand-new image so no `info` (exif, icc, xmp) is carried.
            clean = Image.new("RGB", img.size)
            clean.paste(img)
    except InvalidPhotoError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InvalidPhotoError("Não foi possível ler a imagem enviada.") from exc

    out = io.BytesIO()
    clean.save(out, format="JPEG", quality=85, optimize=True)
    return ProcessedPhoto(data=out.getvalue(), width=clean.width, height=clean.height)


def store_photo(upload_dir: Path, photo: ProcessedPhoto) -> str:
    """Write the photo under upload_dir and return its relative storage key."""
    now = datetime.now(UTC)
    key = f"{now:%Y}/{now:%m}/{uuid.uuid4().hex}.jpg"
    path = upload_dir / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(photo.data)
    return key


def resolve_photo_path(upload_dir: Path, storage_key: str) -> Path:
    path = (upload_dir / storage_key).resolve()
    if not path.is_relative_to(upload_dir.resolve()):
        raise ValueError("storage key escapes the upload directory")
    return path
