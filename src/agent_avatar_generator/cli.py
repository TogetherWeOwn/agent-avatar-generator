"""Command-line interface: ``agent-avatar``."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

from . import __version__
from .backend import DEFAULT_MODEL, FIDELITIES, QUALITIES, BackendError, ImageRequest, generate
from .config import PALETTE_KEYS, AvatarSpec, Palette, ConfigError, apply_overrides, get_preset, load_presets, load_spec_file
from .manifest import check_manifest, default_references, write_manifest
from .output import (
    MAX_SIZE,
    MIN_SIZE,
    OutputError,
    finalize_image,
    prepare_output_dir,
    resolve_output_path,
    save_image,
    validate_size,
)
from .prompt import build_prompt

DEFAULT_SIZE = 1024


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-avatar",
        description="Generate chunky pixel-art agent avatars in the TWO mascot style.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="generate one avatar (or print the request with --dry-run)")
    base = gen.add_mutually_exclusive_group()
    base.add_argument("--preset", help="start from a bundled preset (see: agent-avatar presets)")
    base.add_argument("--config", type=Path, help="start from your own YAML spec file (same format as a preset)")
    gen.add_argument("--role", help='role / job title, e.g. "Data Engineer"')
    gen.add_argument("--name", help="optional character name")
    gen.add_argument("--color-name", help='human name for the palette, e.g. "cobalt"')
    for key in PALETTE_KEYS:
        gen.add_argument(f"--{key}", metavar="HEX", help=f"palette {key} color, #rrggbb")
    gen.add_argument("--face", help='face screen expression, e.g. "happy closed eyes (^ ^)"')
    gen.add_argument("--emblem", help='chest emblem, or "none"')
    gen.add_argument("--accessory", action="append", default=[], help="add an accessory (repeatable)")
    gen.add_argument("--replace-accessories", action="store_true", help="drop the preset's accessories first")
    gen.add_argument("--reference", action="append", default=[], help="style reference image (repeatable); defaults to examples/")
    gen.add_argument("--examples-dir", default="examples", help="where the bundled example images live (default: ./examples)")
    gen.add_argument("--output", "-o", help="output file (.png or .webp)")
    gen.add_argument("--out-dir", default="out", help="directory for derived filenames (default: ./out)")
    gen.add_argument("--format", choices=("png", "webp"), default="png", help="format for derived filenames")
    gen.add_argument("--size", type=int, default=DEFAULT_SIZE, help=f"square output size in px ({MIN_SIZE}-{MAX_SIZE}, default {DEFAULT_SIZE})")
    gen.add_argument("--overwrite", action="store_true", help="replace an existing output file")
    gen.add_argument("--model", default=DEFAULT_MODEL, help=f"image model (default {DEFAULT_MODEL})")
    gen.add_argument("--quality", choices=QUALITIES, default="high")
    gen.add_argument("--input-fidelity", choices=FIDELITIES, default="high")
    gen.add_argument("--dry-run", action="store_true", help="print the full request as JSON; no API call, no API key needed")

    sub.add_parser("presets", help="list bundled presets")

    man = sub.add_parser("manifest", help="check or rewrite manifest.json")
    man.add_argument("--root", type=Path, default=Path("."), help="repository root (default: .)")
    man.add_argument("--write", action="store_true", help="rewrite manifest.json instead of checking it")
    return parser


def _spec_from_args(args: argparse.Namespace) -> AvatarSpec:
    if args.preset:
        spec = get_preset(args.preset)
    elif args.config:
        spec = load_spec_file(args.config)
    else:
        colors = {k: getattr(args, k) for k in PALETTE_KEYS}
        missing = [f"--{k}" for k, v in colors.items() if v is None]
        if not args.role or missing:
            raise ConfigError("without --preset/--config, pass --role and all palette colors: " + " ".join(f"--{k}" for k in PALETTE_KEYS))
        spec = AvatarSpec(role=args.role, palette=Palette.from_dict(colors))
    return apply_overrides(
        spec,
        role=args.role,
        name=args.name,
        color_name=args.color_name,
        colors={k: getattr(args, k) for k in PALETTE_KEYS},
        face=args.face,
        emblem=args.emblem,
        accessories=args.accessory,
        replace_accessories=args.replace_accessories,
    )


def _generate(args: argparse.Namespace, client: Any | None) -> int:
    spec = _spec_from_args(args)
    references = args.reference or default_references(spec, args.examples_dir.rstrip("/"))
    request = ImageRequest(
        model=args.model,
        prompt=build_prompt(spec),
        references=tuple(references),
        quality=args.quality,
        input_fidelity=args.input_fidelity,
    )
    validate_size(args.size)
    stem = spec.name or spec.preset_id or spec.role
    if args.dry_run:
        # Only validate the path shape; a dry run must not fail because the file exists.
        path = resolve_output_path(args.output, args.out_dir, stem, args.format, overwrite=True)
        print(json.dumps({"request": request.to_dict(), "output": str(path), "output_size": args.size}, indent=2))
        return 0
    path = resolve_output_path(args.output, args.out_dir, stem, args.format, overwrite=args.overwrite)
    prepare_output_dir(path)
    data = generate(request, client=client)
    try:
        image, transparent = finalize_image(data, args.size)
        save_image(image, path, overwrite=args.overwrite)
    except (OutputError, OSError) as exc:
        # The API call is already paid for; keep the raw result instead of losing it.
        fd, rescue = tempfile.mkstemp(prefix="agent-avatar-", suffix=".png")
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        raise OutputError(f"{exc}; raw image saved to {rescue}") from exc
    print(path)
    if not transparent:
        print("warning: the generated image has no transparent pixels; check the background", file=sys.stderr)
    return 0


def main(argv: Sequence[str] | None = None, client: Any | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "generate":
            return _generate(args, client)
        if args.command == "presets":
            for preset_id, spec in load_presets().items():
                print(f"{preset_id:22} {spec.role} ({spec.color_name}, {spec.palette.primary})")
            return 0
        if args.command == "manifest":
            if args.write:
                print(write_manifest(args.root))
                return 0
            problems = check_manifest(args.root)
            for problem in problems:
                print(f"error: {problem}", file=sys.stderr)
            if not problems:
                print("manifest OK")
            return 1 if problems else 0
    except (ConfigError, OutputError, BackendError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 1
