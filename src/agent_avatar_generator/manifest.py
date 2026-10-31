"""Build and check manifest.json for the bundled example avatars."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image

from .backend import DEFAULT_MODEL, ImageRequest
from .config import AvatarSpec, load_presets
from .prompt import TEMPLATE_PATH, build_prompt, template_sha256

MANIFEST_NAME = "manifest.json"
EXAMPLES_DIR = "examples"
STYLE_REFERENCES = ("engineering-lead.webp", "qa-reviewer-emerald.webp")

PROVENANCE = (
    "The example images are the approved TWO agent avatars. They were AI-generated for TWO "
    "with an image-generation model before this tool existed; they are stored byte-for-byte as approved. "
    "Each recipe is the preset and prompt this tool uses to generate a new variant in the same style, "
    "not a record of the exact original prompt. Image generation is non-deterministic."
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def default_references(spec: AvatarSpec, examples_dir: str = EXAMPLES_DIR) -> list[str]:
    """The preset's own example if it has one, otherwise the shared style references."""
    if spec.example:
        return [f"{examples_dir}/{spec.example}"]
    return [f"{examples_dir}/{name}" for name in STYLE_REFERENCES]


def build_manifest(root: Path) -> dict[str, Any]:
    root = Path(root)
    entries = []
    for preset_id, spec in load_presets().items():
        if not spec.example:
            continue
        path = root / EXAMPLES_DIR / spec.example
        with Image.open(path) as image:
            width, height = image.size
            fmt = (image.format or "").lower()
        prompt = build_prompt(spec)
        request = ImageRequest(model=DEFAULT_MODEL, prompt=prompt, references=tuple(default_references(spec)))
        entries.append(
            {
                "file": f"{EXAMPLES_DIR}/{spec.example}",
                "preset": preset_id,
                "sha256": sha256_file(path),
                "width": width,
                "height": height,
                "format": fmt,
                "recipe": {
                    "command": f"agent-avatar generate --preset {preset_id}",
                    "prompt_template": TEMPLATE_PATH,
                    "parameters": spec.to_parameters(),
                    "request": request.to_dict(),
                },
            }
        )
    return {
        "provenance": PROVENANCE,
        "prompt_template": TEMPLATE_PATH,
        "prompt_template_sha256": template_sha256(),
        "examples": entries,
    }


def render_manifest(manifest: dict[str, Any]) -> str:
    return json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"


def write_manifest(root: Path) -> Path:
    path = Path(root) / MANIFEST_NAME
    path.write_text(render_manifest(build_manifest(root)), encoding="utf-8")
    return path


def check_manifest(root: Path) -> list[str]:
    """Return a list of problems; empty means manifest.json is current and every example verifies."""
    root = Path(root)
    path = root / MANIFEST_NAME
    if not path.is_file():
        return [f"{MANIFEST_NAME} is missing"]
    problems = []
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    for entry in on_disk.get("examples", []):
        file = root / entry["file"]
        if not file.is_file():
            problems.append(f"{entry['file']} is missing")
        elif sha256_file(file) != entry["sha256"]:
            problems.append(f"{entry['file']} sha256 does not match the manifest")
    presets = load_presets()
    missing_examples = [p for p, spec in presets.items() if not spec.example or not (root / EXAMPLES_DIR / spec.example).is_file()]
    problems += [f"preset {p} has no example image" for p in missing_examples]
    if not problems and on_disk != build_manifest(root):
        problems.append(f"{MANIFEST_NAME} is out of date; run: agent-avatar manifest --write")
    return problems
