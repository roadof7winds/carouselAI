"""Business logic shared by the MCP server and the Telegram bot."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .models import Carousel, FontStyle, Slide, Template, TextAlign
from .renderer import render_slide
from .storage import CarouselStore
from .template_store import TemplateStore
from .text_splitter import split_into_slides

_DEFAULT_DATA_ROOT = Path(__file__).resolve().parents[3] / "data"


def _resolve_data_root(data_root: Optional[Path]) -> Path:
    if data_root is not None:
        return Path(data_root)
    env_value = os.environ.get("CAROUSELAI_DATA_DIR")
    return Path(env_value) if env_value else _DEFAULT_DATA_ROOT


class CarouselService:
    def __init__(self, data_root: Optional[Path] = None):
        root = _resolve_data_root(data_root)
        self.templates = TemplateStore(root / "templates")
        self.carousels = CarouselStore(root / "carousels")
        self._ensure_default_template()

    def _ensure_default_template(self) -> None:
        try:
            self.templates.load("default")
        except FileNotFoundError:
            self.templates.save(Template(id="default", name="Default"))

    def create_carousel(self, text: str, template_id: str = "default", title: str = "") -> Carousel:
        template = self.templates.load(template_id)
        chunks = split_into_slides(text, template.max_chars_per_slide)
        slides = [Slide(index=i, text=chunk) for i, chunk in enumerate(chunks)]
        carousel = Carousel(title=title or text.strip()[:40], template_id=template_id, slides=slides)
        self.carousels.save(carousel)
        self._render_all(carousel, template)
        return carousel

    def _render_all(self, carousel: Carousel, template: Template) -> None:
        for slide in carousel.slides:
            image = render_slide(template, slide.text, slide.font_overrides)
            image.save(self.carousels.slide_image_path(carousel.id, slide.index))

    def edit_slide(
        self,
        carousel_id: str,
        slide_index: int,
        text: Optional[str] = None,
        font_size: Optional[int] = None,
        font_color: Optional[str] = None,
        align: Optional[str] = None,
    ) -> Carousel:
        carousel = self.carousels.load(carousel_id)
        slide = next((s for s in carousel.slides if s.index == slide_index), None)
        if slide is None:
            raise ValueError(f"Slide {slide_index} not found in carousel {carousel_id!r}")

        template = self.templates.load(carousel.template_id)
        overrides = (slide.font_overrides or template.font).model_copy()
        if font_size is not None:
            overrides.size = font_size
        if font_color is not None:
            overrides.color = font_color
        if align is not None:
            overrides.align = TextAlign(align)
        slide.font_overrides = overrides

        if text is not None:
            slide.text = text

        self.carousels.save(carousel)
        image = render_slide(template, slide.text, slide.font_overrides)
        image.save(self.carousels.slide_image_path(carousel.id, slide.index))
        return carousel

    def save_as_template(self, carousel_id: str, name: str) -> Template:
        """Snapshot the layout (font/box/background) a carousel used, as a new reusable template."""
        carousel = self.carousels.load(carousel_id)
        base = self.templates.load(carousel.template_id)
        data = base.model_dump(exclude={"id"})
        data["name"] = name
        new_template = Template(**data)
        return self.templates.save(new_template)

    def export_zip(self, carousel_id: str) -> Path:
        return self.carousels.export_zip(carousel_id)
