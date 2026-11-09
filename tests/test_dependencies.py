import tomllib
from importlib.metadata import version
from pathlib import Path

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]


def read_toml(name):
    return tomllib.loads((ROOT / name).read_text())


def test_supported_python_and_pillow_floors():
    project = read_toml("pyproject.toml")["project"]
    assert project["requires-python"] == ">=3.11"
    python = SpecifierSet(project["requires-python"])
    assert "3.10.99" not in python
    assert "3.11.0" in python and "3.12.0" in python
    pillow = next(Requirement(dep) for dep in project["dependencies"] if Requirement(dep).name.lower() == "pillow")
    assert str(pillow.specifier) == ">=13.0.0"
    assert "12.3.0" not in pillow.specifier
    assert "13.0.0" in pillow.specifier


def test_every_locked_pillow_is_patched():
    lock = read_toml("uv.lock")
    copies = [package for package in lock["package"] if package["name"].lower() == "pillow"]
    assert copies, "Pillow must remain locked"
    for package in copies:
        assert Version(package["version"]) >= Version("13.0.0"), package
    assert Version(version("Pillow")) >= Version("13.0.0")


def test_manifest_and_lock_agree():
    project = read_toml("pyproject.toml")["project"]
    lock = read_toml("uv.lock")
    assert lock["requires-python"] == project["requires-python"]
    root = next(package for package in lock["package"] if package["name"] == project["name"])
    declared = {Requirement(dep).name.lower(): str(Requirement(dep).specifier) for dep in project["dependencies"]}
    locked = {dep["name"]: dep["specifier"] for dep in root["metadata"]["requires-dist"] if not dep.get("marker")}
    assert locked == declared
    edges = [dep for dep in root["dependencies"] if dep["name"] == "pillow"]
    assert edges and all(not edge.get("marker") for edge in edges)
    for package in lock["package"]:
        if package["name"] in declared:
            assert package["version"] in SpecifierSet(declared[package["name"]])


def test_native_dependency_install_controls():
    policy = read_toml("uv.toml")
    assert policy["exclude-newer"] == "P3D"
    assert policy["no-build"] is True
    assert read_toml("uv.lock")["options"]["exclude-newer-span"] == policy["exclude-newer"]
