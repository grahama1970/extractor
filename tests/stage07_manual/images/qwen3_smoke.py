import base64
import io
import mimetypes
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from urllib.request import urlopen

import typer
from dotenv import load_dotenv, find_dotenv
from litellm import completion

app = typer.Typer(help="LiteLLM + OpenRouter multimodal smoke test")

# ---------- helpers ----------

def to_data_uri(image_path: Path, max_side: int | None = 1024) -> str:
    """Encode a local image as a data: URI; optionally downscale large images.

    If Pillow is available and max_side is set, resize the image so the larger
    dimension equals max_side using LANCZOS, and encode as JPEG (quality 85) to
    keep payload small. Falls back to raw bytes if Pillow unavailable.
    """
    mime_guess, _ = mimetypes.guess_type(image_path.name)
    try:
        from PIL import Image  # type: ignore
        if max_side and max_side > 0:
            with Image.open(image_path) as im:
                im = im.convert("RGB")
                w, h = im.size
                scale = max(w, h) / float(max_side)
                if scale > 1.0:
                    new_w = int(round(w / scale))
                    new_h = int(round(h / scale))
                    im = im.resize((new_w, new_h), Image.LANCZOS)
                buf = io.BytesIO()
                im.save(buf, format="JPEG", quality=85)
                data = buf.getvalue()
                mime = "image/jpeg"
        else:
            data = image_path.read_bytes()
            mime = mime_guess or "image/png"
    except Exception:
        data = image_path.read_bytes()
        mime = mime_guess or "image/png"
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{encoded}"

def url_to_data_uri(url: str) -> str:
    """Download an image URL and return it as a data: URI (best-effort)."""
    with urlopen(url) as resp:  # nosec - simple smoke test
        content = resp.read()
        ctype = getattr(resp.headers, "get_content_type", lambda: None)()
    mime = ctype or mimetypes.guess_type(url)[0] or "image/png"
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{mime};base64,{encoded}"

def resolve_image_data_uri(image: Optional[str], *, max_side: int | None = 1024) -> str:
    """Return a data URI for either a provided path/URL or a local default image."""
    if image:
        parsed = urlparse(image)
        if parsed.scheme in {"http", "https"}:
            return url_to_data_uri(image)
        img_path = Path(image)
        if not img_path.exists():
            raise FileNotFoundError(f"Image not found: {img_path}")
        return to_data_uri(img_path, max_side=max_side)

    # Fallback: figure1.png next to this script
    default_img = Path(__file__).with_name("smoke") / "panda.png"
    if not default_img.exists():
        raise FileNotFoundError(f"Default image not found: {default_img}")
    return to_data_uri(default_img, max_side=max_side)

# ---------- pure runner (safe to import/call) ----------

def run_mm(image: Optional[str], model: Optional[str], *, prompt: str = "Describe the content of this image succinctly.", temperature: float = 0.2, max_tokens: int = 300, max_side: int | None = 1024) -> str:
    """
    Multimodal smoke test via LiteLLM/OpenRouter using OpenAI-style message content.
    Returns the assistant text.
    """
    load_dotenv(find_dotenv())
   
    data_uri = resolve_image_data_uri(image, max_side=max_side)
    model_id = model or "openrouter/qwen/qwen-vl-max"

    messages = [
        {"role": "system", "content": "You are a helpful assistant. Be concise."},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ],
        },
    ]

    resp = completion(model=model_id, messages=messages, temperature=temperature, max_tokens=max_tokens)
    from extractor.pipeline.utils.litellm_response_utils import extract_content
    return extract_content(resp)

# ---------- Typer CLI ----------

@app.command("describe")
def cli(
    image: str = typer.Option(
        "tests/stage07_manual/images/smoke/panda.png",
        "--image",
        "-i",
        envvar="SMOKE_IMAGE",
        help="Path or URL to an image",
        show_default=True,
    ),
    model: str = typer.Option(
        "openrouter/qwen/qwen-vl-max",
        "--model",
        "-m",
        envvar="SMOKE_MODEL",
        help=(
            "Model ID. Examples: openrouter/openai/gpt-4o-mini, "
            "openrouter/qwen/qwen-2.5-vl-72b-instruct"
        ),
        show_default=True,
    ),
    prompt: str = typer.Option(
        "Describe the content of this image succinctly.",
        "--prompt",
        "-p",
        help="Prompt text sent alongside the image.",
        show_default=True,
    ),
    temperature: float = typer.Option(
        0.2, 
        help="Sampling temperature", 
        show_default=True
    ),
    max_tokens: int = typer.Option(
        300, 
        help="Max tokens for response", 
        show_default=True
    ),
    max_side: int = typer.Option(
        1024, 
        help="Resize image so longest side equals this value (0=disable)", 
        show_default=True
    ),
):
    """Describe a single image using an OpenRouter/LiteLLM vision model."""
    ms = max_side if max_side > 0 else None
    text = run_mm(image=image, model=model, prompt=prompt, temperature=temperature, max_tokens=max_tokens, max_side=ms)
    print(text)


if __name__ == "__main__":
    app()
