"""Business logic shared by the MCP server and the Telegram bot."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

from .models import Carousel, FontStyle, QueueItem, QueueItemStatus, Slide, Template, TextAlign
from .queue_store import QueueStore
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
        self.queue = QueueStore(root / "queue")
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
            image = render_slide(template, slide.text, slide.font_overrides, slide.background_image)
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
        image = render_slide(template, slide.text, slide.font_overrides, slide.background_image)
        image.save(self.carousels.slide_image_path(carousel.id, slide.index))
        return carousel

    def set_slide_background(self, carousel_id: str, slide_index: int, source_image_path: str) -> Carousel:
        """Set (or replace) one slide's own background, independent of the other slides."""
        carousel = self.carousels.load(carousel_id)
        slide = next((s for s in carousel.slides if s.index == slide_index), None)
        if slide is None:
            raise ValueError(f"Slide {slide_index} not found in carousel {carousel_id!r}")

        stored_path = self.carousels.save_slide_background(carousel_id, slide_index, source_image_path)
        slide.background_image = stored_path
        self.carousels.save(carousel)

        template = self.templates.load(carousel.template_id)
        image = render_slide(template, slide.text, slide.font_overrides, slide.background_image)
        image.save(self.carousels.slide_image_path(carousel.id, slide.index))
        return carousel

    def set_template_background(self, template_id: str, source_image_path: str) -> Template:
        """Store `source_image_path` as the template's background and persist the change."""
        template = self.templates.load(template_id)
        stored_path = self.templates.save_background_image(template_id, source_image_path)
        updated = template.model_copy(update={"background_image": stored_path})
        return self.templates.save(updated)

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

    # -- Inbox queue: the bot only writes here, an LLM reads/writes it through MCP --

    def enqueue(self, chat_id: int, text: str = "", message_id: Optional[int] = None) -> QueueItem:
        item = QueueItem(chat_id=chat_id, message_id=message_id, text=text)
        return self.queue.save(item)

    def add_queue_attachment(self, item_id: str, source_path: str) -> QueueItem:
        item = self.queue.load(item_id)
        stored_path = self.queue.save_attachment(item_id, source_path)
        item.image_paths.append(stored_path)
        item.updated_at = time.time()
        return self.queue.save(item)

    def get_queue_item(self, item_id: str) -> QueueItem:
        return self.queue.load(item_id)

    def list_pending_queue_items(self) -> list[QueueItem]:
        return self.queue.list_by_status(QueueItemStatus.PENDING)

    def mark_queue_item_processing(self, item_id: str) -> QueueItem:
        item = self.queue.load(item_id)
        item.status = QueueItemStatus.PROCESSING
        item.updated_at = time.time()
        return self.queue.save(item)

    def mark_queue_item_done(self, item_id: str, carousel_id: str) -> QueueItem:
        item = self.queue.load(item_id)
        item.status = QueueItemStatus.DONE
        item.result_carousel_id = carousel_id
        item.updated_at = time.time()
        return self.queue.save(item)

    def mark_queue_item_failed(self, item_id: str, reason: str) -> QueueItem:
        item = self.queue.load(item_id)
        item.status = QueueItemStatus.FAILED
        item.error = reason
        item.updated_at = time.time()
        return self.queue.save(item)
