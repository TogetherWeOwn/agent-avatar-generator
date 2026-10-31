"""Output filenames, size validation and transparent PNG/WebP writing."""

from __future__ import annotations

import io
import os
import re
import stat
import tempfile
import unicodedata
from pathlib import Path

from PIL import Image

MIN_SIZE = 32
MAX_SIZE = 2048
FORMATS = {".png": "PNG", ".webp": "WEBP"}
_MAX_STEM = 64
# Device names that Windows reserves even with an extension.
_WINDOWS_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


class OutputError(ValueError):
    """Raised for invalid output paths, sizes or image data."""


def safe_stem(text: str | None, fallback: str = "avatar") -> str:
    """Reduce arbitrary text to a lowercase ``[a-z0-9-]`` filename stem."""
    if not text:
        return fallback
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    stem = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    stem = stem[:_MAX_STEM].rstrip("-") or fallback
    return f"{stem}-avatar" if stem in _WINDOWS_RESERVED else stem


def validate_size(size: int) -> int:
    if isinstance(size, bool) or not isinstance(size, int):
        raise OutputError(f"size must be an integer, got {size!r}")
    if not MIN_SIZE <= size <= MAX_SIZE:
        raise OutputError(f"size must be between {MIN_SIZE} and {MAX_SIZE} pixels, got {size}")
    return size


def output_format(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix not in FORMATS:
        raise OutputError(f"output must end in .png or .webp, got {path.name!r}")
    return FORMATS[suffix]


def resolve_output_path(
    output: str | None,
    out_dir: str,
    stem_source: str | None,
    fmt: str = "png",
    overwrite: bool = False,
) -> Path:
    """Pick the output path.

    An explicit ``output`` path is used as given (only the extension is checked).
    Otherwise the filename is derived from ``stem_source`` and is guaranteed to
    land directly inside ``out_dir``.
    """
    if output:
        path = Path(output)
        if path.name in ("", ".", ".."):
            raise OutputError(f"invalid output path {output!r}")
    else:
        if fmt not in ("png", "webp"):
            raise OutputError(f"format must be png or webp, got {fmt!r}")
        path = Path(out_dir) / f"{safe_stem(stem_source)}.{fmt}"
        if path.resolve().parent != Path(out_dir).resolve():
            raise OutputError(f"derived output path escapes {out_dir!r}")
    output_format(path)
    if path.exists() and not overwrite:
        raise OutputError(f"{path} already exists (use --overwrite to replace it)")
    return path


def has_transparency(image: Image.Image) -> bool:
    """True if the image has an alpha channel with at least one fully transparent pixel."""
    if image.mode != "RGBA":
        if "transparency" not in image.info and image.mode not in ("LA", "PA"):
            return False
        image = image.convert("RGBA")
    low, _ = image.getchannel("A").getextrema()
    return low == 0


def finalize_image(data: bytes, size: int) -> tuple[Image.Image, bool]:
    """Decode generated image bytes, resize to ``size`` x ``size`` and report transparency."""
    validate_size(size)
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as exc:  # Pillow raises several types for bad data
        raise OutputError(f"generated data is not a readable image: {exc}") from exc
    transparent = has_transparency(image)
    image = image.convert("RGBA")
    if image.width != image.height:
        side = max(image.width, image.height)
        canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        canvas.paste(image, ((side - image.width) // 2, (side - image.height) // 2))
        image = canvas
    if image.size != (size, size):
        # Nearest-neighbour keeps pixel-art edges crisp.
        image = image.resize((size, size), Image.Resampling.NEAREST)
    return image, transparent


def prepare_output_dir(path: Path) -> None:
    """Create the parent directory up front so a bad location fails before any paid API call."""
    # An existing symlink is written through, so its target's name and directory are what matter.
    target = Path(os.path.realpath(path))
    output_format(target)
    for parent in dict.fromkeys((path.parent, target.parent)):
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise OutputError(f"cannot create output directory {parent}: {exc}") from exc
    if not os.access(target.parent, os.W_OK):
        raise OutputError(f"output directory {target.parent} is not writable")


def _replacement_mode(path: Path) -> int:
    """Permission bits for a file swapped in at ``path``: the old file's, else a normal create's."""
    try:
        return stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        umask = os.umask(0)
        os.umask(umask)
        return 0o666 & ~umask


def save_image(image: Image.Image, path: Path, overwrite: bool = False) -> None:
    """Write PNG or lossless WebP without ever leaving a partial or clobbered file.

    Without ``overwrite`` the file is created exclusively, so a file that appeared
    since the early existence check is never replaced. With ``overwrite`` the image
    is written to a temporary file and atomically swapped in, so a failed save
    keeps the previous file. The swap follows an existing symlink and keeps the
    replaced file's permission bits.
    """
    if overwrite:
        path = Path(os.path.realpath(path))
    fmt = output_format(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    options = {"lossless": True, "exact": True} if fmt == "WEBP" else {"optimize": True}
    if overwrite:
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        target, fh = Path(tmp_name), os.fdopen(fd, "wb")
        try:
            os.fchmod(fd, _replacement_mode(path))
        except BaseException:
            fh.close()
            target.unlink(missing_ok=True)
            raise
    else:
        try:
            target, fh = path, open(path, "xb")
        except FileExistsError as exc:
            raise OutputError(f"{path} already exists (use --overwrite to replace it)") from exc
    try:
        with fh:
            image.save(fh, fmt, **options)
        if overwrite:
            os.replace(target, path)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
