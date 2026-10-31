"""Image-generation request building and the OpenAI Images backend."""

from __future__ import annotations

import base64
import os
from contextlib import ExitStack
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

DEFAULT_MODEL = "gpt-image-1"
API_KEY_ENV = "OPENAI_API_KEY"
GENERATION_SIZE = "1024x1024"
QUALITIES = ("low", "medium", "high")
FIDELITIES = ("low", "high")


class BackendError(RuntimeError):
    """Raised when the image API is unavailable or returns no image."""


@dataclass(frozen=True)
class ImageRequest:
    """Everything sent to ``client.images.edit`` (minus the opened files)."""

    model: str
    prompt: str
    references: tuple[str, ...]
    size: str = GENERATION_SIZE
    quality: str = "high"
    background: str = "transparent"
    output_format: str = "png"
    input_fidelity: str = "high"
    n: int = 1

    def __post_init__(self) -> None:
        if not self.references:
            raise BackendError("at least one reference image is required")
        if self.quality not in QUALITIES:
            raise BackendError(f"quality must be one of {QUALITIES}")
        if self.input_fidelity not in FIDELITIES:
            raise BackendError(f"input_fidelity must be one of {FIDELITIES}")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["references"] = list(self.references)
        return {"endpoint": "images.edit", **data}


def default_client() -> Any:
    """Create an OpenAI client using the API key from the environment."""
    if not os.environ.get(API_KEY_ENV):
        raise BackendError(f"set {API_KEY_ENV} to generate images (or use --dry-run)")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise BackendError('the openai package is not installed: pip install "agent-avatar-generator[openai]"') from exc
    return OpenAI()


def generate(request: ImageRequest, client: Any | None = None) -> bytes:
    """Send ``request`` and return the decoded image bytes."""
    missing = [r for r in request.references if not Path(r).is_file()]
    if missing:
        raise BackendError(f"reference image not found: {', '.join(missing)}")
    client = client if client is not None else default_client()
    with ExitStack() as stack:
        images = [stack.enter_context(open(r, "rb")) for r in request.references]
        response = client.images.edit(
            model=request.model,
            image=images,
            prompt=request.prompt,
            size=request.size,
            quality=request.quality,
            background=request.background,
            output_format=request.output_format,
            input_fidelity=request.input_fidelity,
            n=request.n,
        )
    data = getattr(response, "data", None) or []
    b64 = getattr(data[0], "b64_json", None) if data else None
    if not b64:
        raise BackendError("the image API returned no image data")
    return base64.b64decode(b64)
