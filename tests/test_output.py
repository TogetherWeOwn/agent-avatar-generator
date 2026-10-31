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
        ("con:*?<>|", "con-avatar"),
        ("Nul", "nul-avatar"),
        ("COM1", "com1-avatar"),
        ("console", "console"),
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


def test_save_never_clobbers_without_overwrite(tmp_path):
    image, _ = finalize_image(png_bytes(), 64)
    path = tmp_path / "a.png"
    path.write_bytes(b"other worker")
    with pytest.raises(OutputError, match="already exists"):
        save_image(image, path)
    assert path.read_bytes() == b"other worker"
    save_image(image, path, overwrite=True)
    with Image.open(path) as saved:
        assert saved.size == (64, 64)


@pytest.mark.parametrize("overwrite", [True, False])
def test_failed_save_keeps_existing_and_leaves_no_partial(tmp_path, monkeypatch, overwrite):
    image, _ = finalize_image(png_bytes(), 64)

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(image, "save", boom)
    path = tmp_path / "a.png"
    if overwrite:
        path.write_bytes(b"previous avatar")
    with pytest.raises(OSError, match="disk full"):
        save_image(image, path, overwrite=overwrite)
    if overwrite:
        assert path.read_bytes() == b"previous avatar"
    else:
        assert not path.exists()
    assert [p.name for p in tmp_path.iterdir()] == (["a.png"] if overwrite else [])


@pytest.mark.parametrize("existing_mode", [0o644, 0o640, None])
def test_overwrite_keeps_file_mode(tmp_path, existing_mode):
    image, _ = finalize_image(png_bytes(), 64)
    path = tmp_path / "a.png"
    if existing_mode is None:
        save_image(image, tmp_path / "plain.png")
        expected = (tmp_path / "plain.png").stat().st_mode & 0o777
    else:
        path.write_bytes(b"previous avatar")
        path.chmod(existing_mode)
        expected = existing_mode
    save_image(image, path, overwrite=True)
    assert path.stat().st_mode & 0o777 == expected


def test_overwrite_through_symlink_updates_target(tmp_path):
    image, _ = finalize_image(png_bytes(), 64)
    (tmp_path / "avatars").mkdir()
    real = tmp_path / "avatars" / "team.png"
    real.write_bytes(b"previous avatar")
    link = tmp_path / "current.png"
    link.symlink_to(real)
    save_image(image, link, overwrite=True)
    assert link.is_symlink()
    with Image.open(real) as saved:
        assert saved.size == (64, 64)
    assert sorted(p.name for p in (tmp_path / "avatars").iterdir()) == ["team.png"]
