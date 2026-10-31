import json
import shutil

from PIL import Image

from agent_avatar_generator.cli import main
from agent_avatar_generator.config import load_presets
from agent_avatar_generator.manifest import build_manifest, check_manifest, sha256_file

from .conftest import ROOT

EXAMPLES = ROOT / "examples"


def load():
    return json.loads((ROOT / "manifest.json").read_text())


def test_manifest_is_current():
    assert check_manifest(ROOT) == []
    assert load() == build_manifest(ROOT)


def test_every_example_exists_and_hash_matches():
    for entry in load()["examples"]:
        path = ROOT / entry["file"]
        assert path.is_file(), entry["file"]
        assert sha256_file(path) == entry["sha256"]
        with Image.open(path) as image:
            assert (image.width, image.height) == (entry["width"], entry["height"]) == (1254, 1254)
            assert image.format == "WEBP" and image.mode == "RGBA"


def test_every_preset_has_exactly_one_example():
    entries = load()["examples"]
    assert sorted(e["preset"] for e in entries) == sorted(load_presets())
    listed = {e["file"].split("/", 1)[1] for e in entries}
    on_disk = {p.name for p in EXAMPLES.iterdir() if p.suffix == ".webp"}
    assert listed == on_disk


def test_recipes_are_reproducible_from_presets():
    for entry in load()["examples"]:
        recipe = entry["recipe"]
        assert recipe["parameters"]["preset_id"] == entry["preset"]
        assert recipe["request"]["references"] == [entry["file"]]
        assert recipe["prompt_template"] == load()["prompt_template"]


def test_check_detects_tampering(tmp_path, capsys):
    shutil.copytree(EXAMPLES, tmp_path / "examples")
    shutil.copy(ROOT / "manifest.json", tmp_path / "manifest.json")
    assert check_manifest(tmp_path) == []
    with open(tmp_path / "examples" / "chief-of-staff.webp", "ab") as fh:
        fh.write(b"\0")
    (tmp_path / "examples" / "qa-reviewer-emerald.webp").unlink()
    problems = check_manifest(tmp_path)
    assert any("chief-of-staff.webp sha256" in p for p in problems)
    assert any("qa-reviewer-emerald.webp is missing" in p for p in problems)
    assert main(["manifest", "--root", str(tmp_path)]) == 1


def test_check_detects_stale_manifest(tmp_path):
    shutil.copytree(EXAMPLES, tmp_path / "examples")
    data = load()
    data["examples"][0]["recipe"]["parameters"]["face"] = "edited by hand"
    (tmp_path / "manifest.json").write_text(json.dumps(data))
    assert check_manifest(tmp_path) == ["manifest.json is out of date; run: agent-avatar manifest --write"]
