import json

import pytest
from PIL import Image

from agent_avatar_generator import backend
from agent_avatar_generator.backend import BackendError, ImageRequest, generate
from agent_avatar_generator.cli import main

from .conftest import FakeClient, png_bytes


def run_dry(capsys, *args):
    assert main(["generate", "--dry-run", *args]) == 0
    return json.loads(capsys.readouterr().out)


def test_dry_run_preset(repo_root, capsys, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    out = run_dry(capsys, "--preset", "qa-reviewer")
    req = out["request"]
    assert req["endpoint"] == "images.edit"
    assert req["references"] == ["examples/qa-reviewer-emerald.webp"]
    assert req["background"] == "transparent"
    assert "#28e179" in req["prompt"] and "magnifying glass" in req["prompt"]
    assert out["output"] == "out/qa-reviewer.png"
    assert not (repo_root / "out").exists()


def test_dry_run_custom(repo_root, capsys):
    out = run_dry(
        capsys,
        "--role", "Data Engineer", "--name", "../../Pipe Dream",
        "--primary", "#3355ff", "--highlight", "#99aaff", "--outline", "#111144",
        "--screen", "#050510", "--glyph", "#ccffee", "--color-name", "cobalt",
        "--accessory", "a hard hat", "--accessory", "a tiny database cylinder",
        "--format", "webp", "--size", "512",
    )
    req = out["request"]
    assert req["references"] == ["examples/engineering-lead.webp", "examples/qa-reviewer-emerald.webp"]
    assert "cobalt" in req["prompt"] and "a hard hat; a tiny database cylinder" in req["prompt"]
    assert out["output"] == "out/pipe-dream.webp"
    assert out["output_size"] == 512


def test_dry_run_recolored_preset_with_own_reference(repo_root, capsys):
    out = run_dry(capsys, "--preset", "chief-of-staff", "--primary", "#00ff00", "--reference", "my/ref.png", "--replace-accessories")
    assert out["request"]["references"] == ["my/ref.png"]
    assert "#00ff00" in out["request"]["prompt"]
    assert "clipboard" not in out["request"]["prompt"]


@pytest.mark.parametrize(
    "args",
    [
        ["--role", "X"],  # custom spec needs every color
        ["--preset", "nope"],
        ["--preset", "qa-reviewer", "--primary", "green"],
        ["--preset", "qa-reviewer", "--size", "4096"],
        ["--preset", "qa-reviewer", "--output", "x.jpg"],
    ],
)
def test_bad_options_exit_2(repo_root, capsys, args):
    assert main(["generate", "--dry-run", *args]) == 2
    assert "error:" in capsys.readouterr().err


def test_generate_with_mock_client(repo_root, tmp_path, capsys):
    client = FakeClient()
    target = tmp_path / "ivy.webp"
    assert main(["generate", "--preset", "qa-reviewer", "--name", "Ivy", "-o", str(target), "--size", "256"], client=client) == 0
    assert capsys.readouterr().out.strip() == str(target)
    (call,) = client.images.calls
    assert call["image"] == ["qa-reviewer-emerald.webp"]
    assert call["background"] == "transparent" and call["model"] == "gpt-image-1"
    assert 'named "Ivy"' in call["prompt"]
    with Image.open(target) as image:
        assert image.format == "WEBP" and image.size == (256, 256)
        assert image.getchannel("A").getextrema()[0] == 0


def test_generate_refuses_overwrite_before_calling_api(repo_root, tmp_path):
    client = FakeClient()
    target = tmp_path / "a.png"
    target.write_bytes(b"keep")
    assert main(["generate", "--preset", "qa-reviewer", "-o", str(target)], client=client) == 2
    assert client.images.calls == []
    assert target.read_bytes() == b"keep"


def test_generate_warns_when_opaque(repo_root, tmp_path, capsys):
    client = FakeClient(png_bytes(transparent=False))
    assert main(["generate", "--preset", "qa-reviewer", "-o", str(tmp_path / "a.png")], client=client) == 0
    assert "no transparent pixels" in capsys.readouterr().err


def test_generate_empty_response(repo_root, tmp_path, capsys):
    client = FakeClient(payload=b"")
    assert main(["generate", "--preset", "qa-reviewer", "-o", str(tmp_path / "a.png")], client=client) == 2
    assert "no image data" in capsys.readouterr().err


def test_missing_api_key_is_clear(repo_root, tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert main(["generate", "--preset", "qa-reviewer", "-o", str(tmp_path / "a.png")]) == 2
    assert "OPENAI_API_KEY" in capsys.readouterr().err


def test_missing_reference(tmp_path):
    request = ImageRequest(model="m", prompt="p", references=(str(tmp_path / "missing.png"),))
    with pytest.raises(BackendError, match="not found"):
        generate(request, client=FakeClient())


def test_request_validation():
    with pytest.raises(BackendError):
        ImageRequest(model="m", prompt="p", references=())
    with pytest.raises(BackendError):
        ImageRequest(model="m", prompt="p", references=("a",), quality="ultra")


def test_default_client_never_built_in_dry_run(repo_root, capsys, monkeypatch):
    monkeypatch.setattr(backend, "default_client", lambda: pytest.fail("client created during dry run"))
    run_dry(capsys, "--preset", "engineering-lead")


def test_presets_command(capsys):
    assert main(["presets"]) == 0
    assert "devops-engineer" in capsys.readouterr().out
