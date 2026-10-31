import base64
import io
import socket
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Fail any test that tries to open a network connection."""

    def guard(*args, **kwargs):
        raise AssertionError("tests must not use the network")

    monkeypatch.setattr(socket.socket, "connect", guard)
    monkeypatch.setattr(socket, "create_connection", guard)


def png_bytes(size=(64, 64), transparent=True, mode="RGBA"):
    image = Image.new(mode, size, (0, 0, 0, 0) if transparent else (255, 255, 255, 255))
    if mode == "RGBA":
        image.paste((200, 50, 80, 255), (size[0] // 4, size[1] // 4, size[0] * 3 // 4, size[1] * 3 // 4))
    buf = io.BytesIO()
    image.save(buf, "PNG")
    return buf.getvalue()


class FakeImages:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def edit(self, **kwargs):
        # Record what was sent, including which files were opened.
        self.calls.append({**kwargs, "image": [Path(f.name).name for f in kwargs["image"]]})
        data = [SimpleNamespace(b64_json=base64.b64encode(self.payload).decode())] if self.payload else []
        return SimpleNamespace(data=data)


class FakeClient:
    def __init__(self, payload=None):
        self.images = FakeImages(png_bytes() if payload is None else payload)


@pytest.fixture
def fake_client():
    return FakeClient()


@pytest.fixture
def repo_root(monkeypatch):
    monkeypatch.chdir(ROOT)
    return ROOT
