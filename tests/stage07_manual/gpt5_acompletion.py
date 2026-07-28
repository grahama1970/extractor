import asyncio
import base64
from pathlib import Path
from typing import Iterable, List, Dict

from dotenv import load_dotenv, find_dotenv
from litellm import acompletion
from extractor.pipeline.utils.litellm_cache import initialize_litellm_cache


load_dotenv(find_dotenv(), override=False)
initialize_litellm_cache()


# --- helpers -----------------------------------------------------------------
def _guess_mime(path: Path) -> str:
    """Return the MIME type based on the file extension."""
    ext = path.suffix.lower().lstrip(".")
    return {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "gif": "image/gif",
        "bmp": "image/bmp",
        "tiff": "image/tiff",
    }.get(ext, "application/octet-stream")


def _file_to_data_uri(path: Path) -> str:
    """Convert file to a data URI string."""
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"{_guess_mime(path)};base64,{b64}"


def _file_to_data_uri_tail(path: Path) -> str:
    """Return 'image/<type>;base64,<b64>' (no 'data:' prefix)."""
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"{_guess_mime(path)};base64,{b64}"


def images_to_mm_content(prompt_text: str, images: Iterable[str]) -> List[Dict]:
    """
    Build a single content list with a lead text node followed by image_url objects:
    [
      {"type": "text", "text": "..."},
      {"type": "image_url", "image_url": {"url": "data:image/...;base64,..." }},
      ...
    ]
    """
    parts: List[Dict] = [{"type": "text", "text": prompt_text}]
    for p in images:
        path = Path(p).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Image not found: {path}")
        data_uri_tail = _file_to_data_uri_tail(path)
        parts.append({"type": "image_url", "image_url": {"url": f"data:{data_uri_tail}"}})
    return parts


# --- main --------------------------------------------------------------------
async def main():
    # Update these with your local test images or pass via CLI args if you prefer
    # e.g., images = sys.argv[1:] or a glob like Path("samples").glob("*.png")
    # images = ["./sample.png"]  # put one or more real image files here

    images = [
        "tests/stage07_manual/images/smoke/panda.png",
        "tests/stage07_manual/images/smoke/parrot.png",
    ]

    messages = [
        {
            "role": "system",
            "content": (
                "You are a vision captioning assistant. "
                "Only output in well-formatted JSON with the following schema: "
                "[{description: string}, ...]. "
                "Do not include any extra text or explanations."
            ),
        },
        {
            "role": "user",
            "content": images_to_mm_content("Describe the content of each image.", images),
        },
    ]

    models = ["openai/gpt-5-mini", "gemini/gemini-2.5-flash"]
    resp = await acompletion(
        model=models[1],
        messages=messages,  # keeping your original field name
        max_tokens=1000,
        response_format={"type": "json_object"},
    )
    resp._hidden_params["response_cost"]
    # litellm returns a response object; `.text` usually holds the assistant text
    print(resp.choices[0].message)


if __name__ == "__main__":
    asyncio.run(main())
