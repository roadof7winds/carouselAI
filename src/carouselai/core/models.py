from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TextAlign(str, Enum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class FontStyle(BaseModel):
    """Text appearance. `path` is a .ttf/.otf file path; None falls back to a bundled font."""

    path: Optional[str] = None
    size: int = 48
    color: str = "#111111"
    line_spacing: float = 1.3
    align: TextAlign = TextAlign.CENTER


class TextBox(BaseModel):
    """Rectangle on the canvas (in pixels) where slide text is placed."""

    x: int = 80
    y: int = 80
    width: int = 920
    height: int = 1190


class Template(BaseModel):
    """A reusable layout: canvas size, background, text box, font. Text and images are not part of it."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    canvas_width: int = 1080
    canvas_height: int = 1350
    background_color: str = "#FAFAFA"
    background_image: Optional[str] = None
    text_box: TextBox = Field(default_factory=TextBox)
    font: FontStyle = Field(default_factory=FontStyle)
    watermark_text: Optional[str] = None
    max_chars_per_slide: int = 280


class Slide(BaseModel):
    index: int
    text: str
    font_overrides: Optional[FontStyle] = None
    background_image: Optional[str] = None
    """Per-slide background, overriding the template's background for this slide only."""


class Carousel(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str = ""
    template_id: str
    slides: list[Slide] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
