"""Avatar specs and preset loading."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, replace
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}\Z")
PALETTE_KEYS = ("primary", "highlight", "outline", "screen", "glyph")
PRESET_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\Z")


class ConfigError(ValueError):
    """Raised for invalid presets or avatar options."""


@dataclass(frozen=True)
class Palette:
    primary: str
    highlight: str
    outline: str
    screen: str
    glyph: str

    def __post_init__(self) -> None:
        for key in PALETTE_KEYS:
            value = getattr(self, key)
            if not isinstance(value, str) or not HEX_COLOR.match(value):
                raise ConfigError(f"palette.{key} must be a #rrggbb hex color, got {value!r}")
            object.__setattr__(self, key, value.lower())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Palette":
        if not isinstance(data, dict):
            raise ConfigError("palette must be a mapping")
        missing = [k for k in PALETTE_KEYS if k not in data]
        unknown = sorted(set(data) - set(PALETTE_KEYS))
        if missing:
            raise ConfigError(f"palette is missing: {', '.join(missing)}")
        if unknown:
            raise ConfigError(f"palette has unknown keys: {', '.join(unknown)}")
        return cls(**{k: data[k] for k in PALETTE_KEYS})


@dataclass(frozen=True)
class AvatarSpec:
    role: str
    palette: Palette
    color_name: str = "custom"
    name: str | None = None
    face: str = 'a terminal prompt ">_" in place of eyes'
    emblem: str = "none"
    accessories: tuple[str, ...] = field(default_factory=tuple)
    preset_id: str | None = None
    example: str | None = None

    def to_parameters(self) -> dict[str, Any]:
        """Generation parameters, as recorded in the manifest."""
        data = asdict(self)
        data["accessories"] = list(self.accessories)
        data.pop("example")
        return data


_PRESET_FIELDS = {"id", "role", "color_name", "palette", "face", "emblem", "accessories", "example", "name"}


def spec_from_dict(data: dict[str, Any], source: str = "preset") -> AvatarSpec:
    if not isinstance(data, dict):
        raise ConfigError(f"{source}: top level must be a mapping")
    unknown = sorted(set(data) - _PRESET_FIELDS)
    if unknown:
        raise ConfigError(f"{source}: unknown keys: {', '.join(unknown)}")
    preset_id = data.get("id")
    if preset_id is not None and (not isinstance(preset_id, str) or not PRESET_ID.match(preset_id)):
        raise ConfigError(f"{source}: id must be lowercase kebab-case, got {preset_id!r}")
    role = data.get("role")
    if not isinstance(role, str) or not role.strip():
        raise ConfigError(f"{source}: role is required")
    accessories = data.get("accessories", [])
    if not isinstance(accessories, list) or not all(isinstance(a, str) and a.strip() for a in accessories):
        raise ConfigError(f"{source}: accessories must be a list of non-empty strings")
    for key in ("color_name", "face", "emblem", "example", "name"):
        if key in data and not isinstance(data[key], str):
            raise ConfigError(f"{source}: {key} must be a string")
    example = data.get("example")
    if example is not None and (example in ("", ".", "..") or Path(example).name != example or "\\" in example):
        raise ConfigError(f"{source}: example must be a plain filename inside the examples directory")
    optional = {k: data[k] for k in ("color_name", "face", "emblem", "name", "example") if k in data}
    return AvatarSpec(
        role=role.strip(),
        palette=Palette.from_dict(data.get("palette")),
        accessories=tuple(a.strip() for a in accessories),
        preset_id=preset_id,
        **optional,
    )


def load_spec_file(path: Path) -> AvatarSpec:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: invalid YAML: {exc}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"{path}: cannot read config: {exc}") from exc
    return spec_from_dict(data, source=str(path))


def _preset_dir():
    return resources.files("agent_avatar_generator") / "presets"


def load_presets() -> dict[str, AvatarSpec]:
    presets: dict[str, AvatarSpec] = {}
    for entry in sorted(_preset_dir().iterdir(), key=lambda p: p.name):
        if not entry.name.endswith((".yaml", ".yml")):
            continue
        spec = spec_from_dict(yaml.safe_load(entry.read_text(encoding="utf-8")), source=entry.name)
        if spec.preset_id is None:
            raise ConfigError(f"{entry.name}: preset needs an id")
        if spec.preset_id in presets:
            raise ConfigError(f"duplicate preset id {spec.preset_id!r}")
        presets[spec.preset_id] = spec
    return presets


def get_preset(preset_id: str) -> AvatarSpec:
    presets = load_presets()
    if preset_id not in presets:
        raise ConfigError(f"unknown preset {preset_id!r}; choose one of: {', '.join(presets)}")
    return presets[preset_id]


def apply_overrides(
    spec: AvatarSpec,
    *,
    role: str | None = None,
    name: str | None = None,
    color_name: str | None = None,
    colors: dict[str, str | None] | None = None,
    face: str | None = None,
    emblem: str | None = None,
    accessories: list[str] | None = None,
    replace_accessories: bool = False,
) -> AvatarSpec:
    """Return a copy of ``spec`` with CLI overrides applied."""
    changes: dict[str, Any] = {}
    if role is not None:
        if not role.strip():
            raise ConfigError("role must not be empty")
        changes["role"] = role.strip()
    if name is not None:
        changes["name"] = name.strip() or None
    if color_name is not None:
        changes["color_name"] = color_name.strip()
    if face is not None:
        changes["face"] = face.strip()
    if emblem is not None:
        changes["emblem"] = emblem.strip() or "none"
    color_overrides = {k: v for k, v in (colors or {}).items() if v is not None}
    if color_overrides:
        merged = {**asdict(spec.palette), **color_overrides}
        changes["palette"] = Palette.from_dict(merged)
        if color_name is None and spec.preset_id is not None:
            changes["color_name"] = "custom"
    if accessories or replace_accessories:
        extra = tuple(a.strip() for a in (accessories or []) if a.strip())
        changes["accessories"] = extra if replace_accessories else spec.accessories + extra
    return replace(spec, **changes) if changes else spec
