from carouselai.core.models import Template
from carouselai.core.renderer import render_slide


def test_render_slide_produces_image_of_canvas_size():
    template = Template(name="T", canvas_width=400, canvas_height=500)
    image = render_slide(template, "Короткий текст слайда")
    assert image.size == (400, 500)


def test_render_slide_wraps_long_text_without_error():
    template = Template(name="T", canvas_width=400, canvas_height=500, max_chars_per_slide=50)
    long_text = "Очень длинный текст, который должен перенестись на несколько строк внутри текстового блока."
    image = render_slide(template, long_text)
    assert image.size == (400, 500)
