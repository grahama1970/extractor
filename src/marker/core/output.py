import json
import os

from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel
from PIL import Image

from marker.core.renderers.html import HTMLOutput
from marker.core.renderers.json import JSONOutput, JSONBlockOutput
from marker.core.renderers.markdown import MarkdownOutput
from marker.core.renderers.arangodb_json import ArangoDBOutput
from marker.core.schema.blocks import BlockOutput
from marker.core.settings import settings


def unwrap_outer_tag(html: str):
    soup = BeautifulSoup(html, "html.parser")
    contents = list(soup.contents)
    if len(contents) == 1 and isinstance(contents[0], Tag) and contents[0].name == "p":
        # Unwrap the p tag
        soup.p.unwrap()

    return str(soup)


def json_to_html(block: JSONBlockOutput | BlockOutput):
    # Utility function to take in json block output and give html for the block.
    if not getattr(block, "children", None):
        return block.html
    else:
        child_html = [json_to_html(child) for child in block.children]
        child_ids = [child.id for child in block.children]

        soup = BeautifulSoup(block.html, "html.parser")
        content_refs = soup.find_all("content-ref")
        for ref in content_refs:
            src_id = ref.attrs["src"]
            if src_id in child_ids:
                child_soup = BeautifulSoup(
                    child_html[child_ids.index(src_id)], "html.parser"
                )
                ref.replace_with(child_soup)
        return str(soup)


def output_exists(output_dir: str, fname_base: str):
    exts = ["md", "html", "json"]
    for ext in exts:
        if os.path.exists(os.path.join(output_dir, f"{fname_base}.{ext}")):
            return True
    return False


def text_from_rendered(rendered: BaseModel):
    if isinstance(rendered, MarkdownOutput):
        return rendered.markdown, "md", rendered.images
    elif isinstance(rendered, HTMLOutput):
        return rendered.html, "html", rendered.images
    elif isinstance(rendered, JSONOutput):
        return rendered.model_dump_json(exclude=["metadata"], indent=2), "json", {}
    elif isinstance(rendered, ArangoDBOutput):
        return json.dumps(rendered.model_dump(), indent=2), "json", {}
    else:
        raise ValueError("Invalid output type")


def convert_if_not_rgb(image: Image.Image) -> Image.Image:
    if image.mode != "RGB":
        image = image.convert("RGB")
    return image


def output_to_format(document, output_path: str, output_format: str):
    """Convert document to specified format and save to file."""
    from marker.core.renderers.markdown import MarkdownRenderer
    from marker.core.renderers.json import JSONRenderer
    from marker.core.renderers.html import HTMLRenderer
    
    # Get appropriate renderer
    if output_format == "markdown" or output_format == "md":
        renderer = MarkdownRenderer()
        rendered = renderer.render(document)
        ext = "md"
    elif output_format == "json":
        renderer = JSONRenderer()
        rendered = renderer.render(document)
        ext = "json"
    elif output_format == "html":
        renderer = HTMLRenderer()
        rendered = renderer.render(document)
        ext = "html"
    else:
        raise ValueError(f"Unsupported output format: {output_format}")
    
    # Ensure output path has correct extension
    output_path = str(output_path)
    if not output_path.endswith(f".{ext}"):
        if "." in output_path:
            output_path = output_path.rsplit(".", 1)[0] + f".{ext}"
        else:
            output_path = f"{output_path}.{ext}"
    
    # Get text content
    text, _, images = text_from_rendered(rendered)
    text = text.encode(settings.OUTPUT_ENCODING, errors="replace").decode(
        settings.OUTPUT_ENCODING
    )
    
    # Write output file
    with open(output_path, "w+", encoding=settings.OUTPUT_ENCODING) as f:
        f.write(text)
    
    # Save images if any
    if images:
        import os
        output_dir = os.path.dirname(output_path)
        for img_name, img in images.items():
            img = convert_if_not_rgb(img)
            img.save(os.path.join(output_dir, img_name), settings.OUTPUT_IMAGE_FORMAT)
    
    return output_path


def save_output(rendered: BaseModel, output_dir: str, fname_base: str):
    text, ext, images = text_from_rendered(rendered)
    text = text.encode(settings.OUTPUT_ENCODING, errors="replace").decode(
        settings.OUTPUT_ENCODING
    )

    with open(
        os.path.join(output_dir, f"{fname_base}.{ext}"),
        "w+",
        encoding=settings.OUTPUT_ENCODING,
    ) as f:
        f.write(text)
    with open(
        os.path.join(output_dir, f"{fname_base}_meta.json"),
        "w+",
        encoding=settings.OUTPUT_ENCODING,
    ) as f:
        f.write(json.dumps(rendered.metadata, indent=2))

    for img_name, img in images.items():
        img = convert_if_not_rgb(img)  # RGBA images can't save as JPG
        img.save(os.path.join(output_dir, img_name), settings.OUTPUT_IMAGE_FORMAT)
