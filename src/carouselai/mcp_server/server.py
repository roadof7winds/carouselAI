"""MCP server exposing carousel generation/editing as tools for an LLM agent."""

from __future__ import annotations

from typing import Optional

from mcp.server.mcpserver import MCPServer

from carouselai.core.carousel_service import CarouselService

mcp = MCPServer("carouselai")
service = CarouselService()


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
def save_as_template(carousel_id: str, name: str) -> dict:
    """Save the layout (font, box, color, size, background) a carousel used as a new reusable named template."""
    template = service.save_as_template(carousel_id, name)
    return template.model_dump()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
