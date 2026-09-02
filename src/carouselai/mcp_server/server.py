"""MCP server exposing carousel generation/editing as tools for an LLM agent."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from mcp.server.mcpserver import Image, MCPServer

from carouselai.core.carousel_service import CarouselService

mcp = MCPServer("carouselai")
service = CarouselService()

_RULES_PATH = Path(__file__).resolve().parents[3] / "rules" / "PROCESSING_RULES.md"


def _queue_item_payload(item) -> dict:
    return {
        "id": item.id,
        "chat_id": item.chat_id,
        "message_id": item.message_id,
        "text": item.text,
        "image_count": len(item.image_paths),
        "status": item.status.value,
        "result_carousel_id": item.result_carousel_id,
        "error": item.error,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@mcp.tool()
def list_templates() -> list[dict]:
    """List saved carousel templates (layouts): id, name, canvas size, max chars per slide."""
    return [t.model_dump() for t in service.templates.list()]


@mcp.tool()
def get_template(template_id: str) -> dict:
    """Get the full layout definition (canvas, text box, font, background) of one template."""
    return service.templates.load(template_id).model_dump()


@mcp.tool()
def create_carousel(text: str, template_id: str = "default", title: str = "") -> dict:
    """Split raw text into slides per the template's rules and render each slide to a PNG.

    Returns the carousel id, per-slide text, and paths to the rendered images.
    """
    carousel = service.create_carousel(text=text, template_id=template_id, title=title)
    return {
        "carousel_id": carousel.id,
        "title": carousel.title,
        "template_id": carousel.template_id,
        "slides": [
            {
                "index": slide.index,
                "text": slide.text,
                "image_path": str(service.carousels.slide_image_path(carousel.id, slide.index)),
            }
            for slide in carousel.slides
        ],
    }


@mcp.tool()
def edit_slide(
    carousel_id: str,
    slide_index: int,
    text: Optional[str] = None,
    font_size: Optional[int] = None,
    font_color: Optional[str] = None,
    align: Optional[str] = None,
) -> dict:
    """Edit one slide's text and/or font size/color/alignment ('left'/'center'/'right'), then re-render it."""
    carousel = service.edit_slide(
        carousel_id=carousel_id,
        slide_index=slide_index,
        text=text,
        font_size=font_size,
        font_color=font_color,
        align=align,
    )
    slide = next(s for s in carousel.slides if s.index == slide_index)
    return {
        "carousel_id": carousel.id,
        "index": slide.index,
        "text": slide.text,
        "image_path": str(service.carousels.slide_image_path(carousel.id, slide.index)),
    }


@mcp.tool()
def export_carousel(carousel_id: str) -> dict:
    """Bundle all rendered slide images of a carousel into a single zip file and return its path."""
    zip_path = service.export_zip(carousel_id)
    return {"zip_path": str(zip_path)}


@mcp.tool()
def set_template_background(template_id: str, image_path: str) -> dict:
    """Set (or replace) a template's default background image from a local file path.

    Applies to every slide of carousels using this template, unless a slide has its
    own background set via `set_slide_background`.
    """
    template = service.set_template_background(template_id, image_path)
    return template.model_dump()


@mcp.tool()
def set_slide_background(carousel_id: str, slide_index: int, image_path: str) -> dict:
    """Set (or replace) one slide's own background image, independent of the other slides
    in the same carousel. Use this to give each slide of a carousel its own picture."""
    carousel = service.set_slide_background(carousel_id, slide_index, image_path)
    slide = next(s for s in carousel.slides if s.index == slide_index)
    return {
        "carousel_id": carousel.id,
        "index": slide.index,
        "background_image": slide.background_image,
        "image_path": str(service.carousels.slide_image_path(carousel.id, slide.index)),
    }


@mcp.tool()
def save_as_template(carousel_id: str, name: str) -> dict:
    """Save the layout (font, box, color, size, background) a carousel used as a new reusable named template."""
    template = service.save_as_template(carousel_id, name)
    return template.model_dump()


@mcp.tool()
def get_processing_rules() -> str:
    """Read the human-edited rules for how to turn a queue item into a carousel
    (slide splitting, tone, image-to-slide matching, template choice). Read this
    before processing any queue item — it changes without a code deploy."""
    return _RULES_PATH.read_text(encoding="utf-8")


@mcp.tool()
def list_pending_items() -> list[dict]:
    """List inbox items the bot collected that no one has processed yet."""
    return [_queue_item_payload(item) for item in service.list_pending_queue_items()]


@mcp.tool()
def get_queue_item(item_id: str) -> dict:
    """Get one inbox item's text and how many image attachments it has.
    Use `read_queue_item_image` to actually see an attachment."""
    return _queue_item_payload(service.get_queue_item(item_id))


@mcp.tool()
def read_queue_item_image(item_id: str, image_index: int) -> Image:
    """Return one image attachment of a queue item, to actually look at it
    (you have no filesystem access to the bot's downloads, only this tool)."""
    item = service.get_queue_item(item_id)
    if not 0 <= image_index < len(item.image_paths):
        raise ValueError(f"Queue item {item_id!r} has no image at index {image_index}")
    return Image(path=item.image_paths[image_index])


@mcp.tool()
def mark_item_processing(item_id: str) -> dict:
    """Claim a pending item so it isn't processed twice. Call this before working on it."""
    return _queue_item_payload(service.mark_queue_item_processing(item_id))


@mcp.tool()
def mark_item_done(item_id: str, carousel_id: str) -> dict:
    """Mark a queue item as finished and link it to the carousel that was built from it."""
    return _queue_item_payload(service.mark_queue_item_done(item_id, carousel_id))


@mcp.tool()
def mark_item_failed(item_id: str, reason: str) -> dict:
    """Mark a queue item as failed with a human-readable reason (bad input, unclear request, etc.)."""
    return _queue_item_payload(service.mark_queue_item_failed(item_id, reason))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
