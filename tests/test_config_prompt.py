import pytest

from agent_avatar_generator.config import (
    ConfigError,
    Palette,
    apply_overrides,
    get_preset,
    load_presets,
    load_spec_file,
    spec_from_dict,
)
from agent_avatar_generator.prompt import build_prompt

EXPECTED_PRESETS = {
    "chief-of-staff",
    "engineering-lead",
    "software-engineer-1",
    "software-engineer-2",
    "devops-engineer",
    "qa-reviewer",
    "product-lead",
    "security-engineer",
    "ux-designer",
    "applied-cryptography-reviewer",
    "release-manager",
}

PALETTE = {"primary": "#112233", "highlight": "#445566", "outline": "#000000", "screen": "#101010", "glyph": "#FFFFFF"}


def test_all_presets_load():
    presets = load_presets()
    assert set(presets) == EXPECTED_PRESETS
    for preset_id, spec in presets.items():
        assert spec.preset_id == preset_id
        assert spec.role and spec.face and spec.example


@pytest.mark.parametrize(
    "preset_id,color",
    [
        ("devops-engineer", "coral"),
        ("qa-reviewer", "emerald"),
        ("product-lead", "magenta"),
        ("security-engineer", "gunmetal steel"),
        ("ux-designer", "lilac"),
        ("applied-cryptography-reviewer", "sky blue"),
        ("release-manager", "royal navy"),
    ],
)
def test_named_color_presets(preset_id, color):
    assert get_preset(preset_id).color_name == color


def test_unknown_preset_lists_choices():
    with pytest.raises(ConfigError, match="engineering-lead"):
        get_preset("nope")


def test_palette_normalizes_and_validates():
    assert Palette.from_dict(PALETTE).glyph == "#ffffff"
    for bad in ("red", "#fff", "#gggggg", "112233", None, "#112233\n"):
        with pytest.raises(ConfigError):
            Palette.from_dict({**PALETTE, "primary": bad})
    with pytest.raises(ConfigError, match="missing"):
        Palette.from_dict({k: v for k, v in PALETTE.items() if k != "screen"})
    with pytest.raises(ConfigError, match="unknown"):
        Palette.from_dict({**PALETTE, "extra": "#000000"})


@pytest.mark.parametrize(
    "data",
    [
        [],
        {"palette": PALETTE},
        {"role": "  ", "palette": PALETTE},
        {"role": "X", "palette": PALETTE, "accessories": "hat"},
        {"role": "X", "palette": PALETTE, "accessories": [""]},
        {"role": "X", "palette": PALETTE, "id": "../evil"},
        {"role": "X", "palette": PALETTE, "colour": "typo"},
        {"role": "X", "palette": PALETTE, "id": "foo\n"},
        {"role": "X", "palette": PALETTE, "accessories": None},
        {"role": "X", "palette": PALETTE, "accessories": False},
        {"role": "X", "palette": PALETTE, "example": "../../private.png"},
        {"role": "X", "palette": PALETTE, "example": "sub/dir.webp"},
        {"role": "X", "palette": PALETTE, "example": ".."},
    ],
)
def test_invalid_specs_rejected(data):
    with pytest.raises(ConfigError):
        spec_from_dict(data)


def test_load_spec_file(tmp_path):
    path = tmp_path / "custom.yaml"
    path.write_text(
        "role: Data Engineer\ncolor_name: cobalt\npalette:\n"
        + "".join(f"  {k}: '{v}'\n" for k, v in PALETTE.items())
        + "accessories:\n  - a tiny database cylinder\n"
    )
    spec = load_spec_file(path)
    assert spec.role == "Data Engineer"
    assert spec.accessories == ("a tiny database cylinder",)
    path.write_text("role: [unclosed")
    with pytest.raises(ConfigError, match="invalid YAML"):
        load_spec_file(path)


def test_unreadable_spec_file_is_config_error(tmp_path):
    bad = tmp_path / "latin1.yaml"
    bad.write_bytes(b"role: caf\xe9")
    for path in (tmp_path / "missing.yaml", tmp_path, bad):
        with pytest.raises(ConfigError, match="cannot read"):
            load_spec_file(path)


def test_overrides():
    base = get_preset("qa-reviewer")
    spec = apply_overrides(base, name="Ivy", colors={"primary": "#0000FF", "glyph": None}, accessories=["a party hat"])
    assert spec.name == "Ivy"
    assert spec.palette.primary == "#0000ff"
    assert spec.palette.outline == base.palette.outline
    assert spec.color_name == "custom"
    assert spec.accessories == base.accessories + ("a party hat",)
    replaced = apply_overrides(base, accessories=["a scarf"], replace_accessories=True)
    assert replaced.accessories == ("a scarf",)
    assert apply_overrides(base) is base
    assert base.palette.primary == "#28e179"  # presets are not mutated


def test_prompt_contains_every_attribute():
    spec = apply_overrides(get_preset("product-lead"), name="Pia", accessories=["a beret"])
    prompt = build_prompt(spec)
    assert 'Product Lead named "Pia"' in prompt
    for value in vars(spec.palette).values():
        assert value in prompt
    for item in (spec.face, spec.emblem, "magenta", "a beret", *spec.accessories):
        assert item in prompt
    assert "transparent" in prompt
    assert "$" not in prompt


def test_prompt_without_accessories_or_name():
    spec = spec_from_dict({"role": "Analyst", "palette": PALETTE})
    prompt = build_prompt(spec)
    assert "Character: Analyst." in prompt
    assert "Accessories: none." in prompt


def test_prompt_template_with_unknown_placeholder_fails():
    with pytest.raises(KeyError):
        build_prompt(get_preset("qa-reviewer"), template="$character $mystery")


def test_prompt_is_stable():
    spec = get_preset("engineering-lead")
    assert build_prompt(spec) == build_prompt(spec)
