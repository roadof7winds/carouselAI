"""Renders a single slide (template layout + text) to a PIL image."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from .models import FontStyle, Template, TextAlign

_FALLBACK_FONTS = ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf")


def _load_font(font: FontStyle) -> ImageFont.FreeTypeFont:
    if font.path and Path(font.path).exists():
        return ImageFont.truetype(font.path, font.size)
    for name in _FALLBACK_FONTS:
        try:
            return ImageFont.truetype(name, font.size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            trial = f"{current} {word}"
            if draw.textlength(trial, font=font) <= max_width:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def render_slide(template: Template, text: str, font_overrides: Optional[FontStyle] = None) -> Image.Image:
    font_style = font_overrides or template.font
    canvas = Image.new("RGB", (template.canvas_width, template.canvas_height), template.background_color)

    if template.background_image and Path(template.background_image).exists():
        background = Image.open(template.background_image).convert("RGB")
        background = background.resize((template.canvas_width, template.canvas_height))
        canvas.paste(background, (0, 0))

    draw = ImageDraw.Draw(canvas)
    font = _load_font(font_style)
    box = template.text_box

    lines = _wrap_text(draw, text, font, box.width)
    line_height = int(font_style.size * font_style.line_spacing)
    total_height = line_height * len(lines)
    y = box.y + max(0, (box.height - total_height) // 2)

    for line in lines:
        line_width = draw.textlength(line, font=font)
        if font_style.align == TextAlign.CENTER:
            x = box.x + (box.width - line_width) / 2
        elif font_style.align == TextAlign.RIGHT:
            x = box.x + box.width - line_width
        else:
            x = box.x
        draw.text((x, y), line, font=font, fill=font_style.color)
        y += line_height

    if template.watermark_text:
        watermark_font = _load_font(FontStyle(size=28, color="#999999"))
        draw.text(
            (30, template.canvas_height - 50),
            template.watermark_text,
            font=watermark_font,
            fill="#999999",
        )

    return canvas
