"""Prompt construction from an AvatarSpec and the saved template."""

from __future__ import annotations

import hashlib
from importlib import resources
from string import Template

from .config import AvatarSpec

TEMPLATE_NAME = "avatar_prompt.txt"
TEMPLATE_PATH = f"src/agent_avatar_generator/templates/{TEMPLATE_NAME}"


def load_template() -> str:
    return (resources.files("agent_avatar_generator") / "templates" / TEMPLATE_NAME).read_text(encoding="utf-8")


def template_sha256() -> str:
    return hashlib.sha256(load_template().encode("utf-8")).hexdigest()


def _accessories_text(spec: AvatarSpec) -> str:
    if not spec.accessories:
        return "none"
    return "; ".join(spec.accessories)


def build_prompt(spec: AvatarSpec, template: str | None = None) -> str:
    character = spec.role if not spec.name else f'{spec.role} named "{spec.name}"'
    values = {
        "character": character,
        "color_name": spec.color_name,
        "face": spec.face,
        "emblem": spec.emblem,
        "accessories": _accessories_text(spec),
        **{k: getattr(spec.palette, k) for k in ("primary", "highlight", "outline", "screen", "glyph")},
    }
    # substitute() raises on unknown placeholders, so template drift fails loudly.
    return Template(template if template is not None else load_template()).substitute(values).strip()
