from pathlib import Path

from PIL import Image as PILImage

from carouselai.core.models import Template
from carouselai.core.renderer import render_slide


def test_render_slide_produces_image_of_canvas_size():
    template = Template(name="T", canvas_width=400, canvas_height=500)
    image = render_slide(template, "Короткий текст слайда")
    assert image.size == (400, 500)


def test_slide_background_override_wins_over_template_background(tmp_path: Path):
    template_bg = tmp_path / "template_bg.png"
    PILImage.new("RGB", (10, 10), "#FF0000").save(template_bg)
    slide_bg = tmp_path / "slide_bg.png"
    PILImage.new("RGB", (10, 10), "#00FF00").save(slide_bg)

    template = Template(name="T", canvas_width=50, canvas_height=50, background_image=str(template_bg))

    with_override = render_slide(template, "Текст", background_image=str(slide_bg))
    without_override = render_slide(template, "Текст")

    assert with_override.getpixel((1, 1)) != without_override.getpixel((1, 1))


def test_render_slide_wraps_long_text_without_error():
    template = Template(name="T", canvas_width=400, canvas_height=500, max_chars_per_slide=50)
    long_text = "Очень длинный текст, который должен перенестись на несколько строк внутри текстового блока."
    image = render_slide(template, long_text)
    assert image.size == (400, 500)
