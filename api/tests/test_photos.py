"""EXIF removal and validation of uploaded photos."""

import io

import pytest
from PIL import Image

from app.services.photos import InvalidPhotoError, sanitize_image
from tests.conftest import jpeg_with_exif

LIMITS = {"max_side": 1600, "max_bytes": 10 * 1024 * 1024}


def test_input_fixture_really_has_gps_and_camera_data():
    with Image.open(io.BytesIO(jpeg_with_exif())) as img:
        exif = img.getexif()
        assert exif[0x010F] == "FabricanteTeste"
        assert exif.get_ifd(0x8825)  # GPS IFD present


def test_strips_all_exif_including_gps():
    result = sanitize_image(jpeg_with_exif(), **LIMITS)
    with Image.open(io.BytesIO(result.data)) as img:
        assert len(img.getexif()) == 0
        assert not img.getexif().get_ifd(0x8825)
        assert "exif" not in img.info
    assert b"FabricanteTeste" not in result.data
    assert b"ModeloTeste" not in result.data


def test_applies_orientation_before_stripping():
    # Orientation 6 = the camera was rotated; the pixels must be turned 90° to display upright.
    result = sanitize_image(jpeg_with_exif(size=(400, 300), orientation=6), **LIMITS)
    assert (result.width, result.height) == (300, 400)


def test_downscales_large_images_keeping_aspect_ratio():
    img = Image.new("RGB", (4000, 3000), (10, 10, 10))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    result = sanitize_image(buf.getvalue(), **LIMITS)
    assert (result.width, result.height) == (1600, 1200)


def test_accepts_png_with_transparency():
    img = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    result = sanitize_image(buf.getvalue(), **LIMITS)
    assert result.content_type == "image/jpeg"


@pytest.mark.parametrize("raw", [b"", b"isto nao e uma imagem", b"\xff\xd8\xff\xe0corrompido"])
def test_rejects_empty_or_invalid_files(raw):
    with pytest.raises(InvalidPhotoError):
        sanitize_image(raw, **LIMITS)


def test_rejects_files_over_the_size_limit():
    with pytest.raises(InvalidPhotoError, match="no máximo"):
        sanitize_image(jpeg_with_exif(), max_side=1600, max_bytes=100)
