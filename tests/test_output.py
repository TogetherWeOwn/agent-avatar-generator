from pathlib import Path

import pytest
from PIL import Image

from agent_avatar_generator.output import (
    OutputError,
    finalize_image,
    has_transparency,
    resolve_output_path,
    safe_stem,
    save_image,
    validate_size,
)

from .conftest import png_bytes


@pytest.mark.parametrize(
    "text,expected",
    [
        ("QA Reviewer", "qa-reviewer"),
        ("../../etc/passwd", "etc-passwd"),
        ("..\\..\\windows\\system32", "windows-system32"),
        ("/abs/path", "abs-path"),
        ("Zoë Ñandú", "zoe-nandu"),
        ("name\x00with\nnull", "name-with-null"),
        ("..", "avatar"),
        ("🤖🤖", "avatar"),
        ("", "avatar"),
        (None, "avatar"),
        ("a" * 200, "a" * 64),
        ("con:*?<>|", "con"),
    ],
)
def test_safe_stem(text, expected):
    assert safe_stem(text) == expected


def test_derived_path_stays_in_out_dir(tmp_path):
    out = tmp_path / "out"
    for hostile in ("../../escape", "/etc/passwd", "..", "a/../../b"):
        path = resolve_output_path(None, str(out), hostile, "webp")
        assert path.resolve().parent == out.resolve()
        assert path.suffix == ".webp"


def test_explicit_output_extension_checked(tmp_path):
    assert resolve_output_path(str(tmp_path / "x.PNG"), "out", None) == tmp_path / "x.PNG"
    for bad in ("x.jpg", "x", "x.png.exe", ".."):
        with pytest.raises(OutputError):
            resolve_output_path(str(tmp_path / bad) if bad != ".." else bad, "out", None)
    with pytest.raises(OutputError):
        resolve_output_path(None, str(tmp_path), "x", "gif")


def test_existing_output_needs_overwrite(tmp_path):
    target = tmp_path / "a.png"
    target.write_bytes(b"x")
    with pytest.raises(OutputError, match="already exists"):
        resolve_output_path(str(target), "out", None)
    assert resolve_output_path(str(target), "out", None, overwrite=True) == target


@pytest.mark.parametrize("size", [32, 512, 1024, 1254, 2048])
def test_valid_sizes(size):
    assert validate_size(size) == size


@pytest.mark.parametrize("size", [0, 31, 2049, -5, 10.5, "512", True])
def test_invalid_sizes(size):
    with pytest.raises(OutputError):
        validate_size(size)


def test_transparency_detection():
    assert has_transparency(Image.new("RGBA", (4, 4), (0, 0, 0, 0)))
    assert not has_transparency(Image.new("RGBA", (4, 4), (0, 0, 0, 255)))
    assert not has_transparency(Image.new("RGB", (4, 4)))


def test_finalize_resizes_and_keeps_alpha():
    image, transparent = finalize_image(png_bytes((64, 64)), 128)
    assert transparent
    assert image.size == (128, 128) and image.mode == "RGBA"
    assert image.getpixel((0, 0))[3] == 0
    assert image.getpixel((64, 64))[3] == 255


def test_finalize_pads_non_square_and_flags_opaque():
    image, transparent = finalize_image(png_bytes((64, 32), transparent=False), 64)
    assert not transparent
    assert image.size == (64, 64)
    assert image.getpixel((0, 0))[3] == 0  # padding is transparent


def test_finalize_rejects_garbage():
    with pytest.raises(OutputError, match="not a readable image"):
        finalize_image(b"not an image", 64)
    with pytest.raises(OutputError):
        finalize_image(png_bytes(), 1)


@pytest.mark.parametrize("name", ["a.png", "nested/dir/a.webp"])
def test_save_round_trip_preserves_transparency(tmp_path, name):
    image, _ = finalize_image(png_bytes(), 64)
    path = tmp_path / name
    save_image(image, path)
    with Image.open(path) as saved:
        assert saved.format == Path(name).suffix[1:].upper()
        assert saved.size == (64, 64)
        assert has_transparency(saved)
        assert saved.convert("RGBA").tobytes() == image.tobytes()  # lossless
