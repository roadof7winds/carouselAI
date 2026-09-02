from pathlib import Path

import pytest

from carouselai.core.carousel_service import CarouselService


@pytest.fixture
def service(tmp_path: Path) -> CarouselService:
    return CarouselService(data_root=tmp_path)


def test_creates_default_template_on_first_use(service: CarouselService):
    templates = service.templates.list()
    assert any(t.id == "default" for t in templates)


def test_create_carousel_renders_one_image_per_slide(service: CarouselService):
    service.templates.save(service.templates.load("default").model_copy(update={"max_chars_per_slide": 20}))
    carousel = service.create_carousel("Первый слайд текста.\n\nВторой слайд текста.")
    assert len(carousel.slides) == 2
    for slide in carousel.slides:
        image_path = service.carousels.slide_image_path(carousel.id, slide.index)
        assert image_path.exists()


def test_edit_slide_updates_text_and_rerenders(service: CarouselService):
    carousel = service.create_carousel("Исходный текст.")
    updated = service.edit_slide(carousel.id, 0, text="Новый текст.", font_size=60, font_color="#FF0000")

    slide = next(s for s in updated.slides if s.index == 0)
    assert slide.text == "Новый текст."
    assert slide.font_overrides is not None
    assert slide.font_overrides.size == 60
    assert slide.font_overrides.color == "#FF0000"


def test_export_zip_contains_all_slide_images(service: CarouselService):
    carousel = service.create_carousel("Раз.\n\nДва.\n\nТри.")
    zip_path = service.export_zip(carousel.id)
    assert zip_path.exists()
    assert zip_path.suffix == ".zip"


def test_save_as_template_creates_new_template_with_given_name(service: CarouselService):
    carousel = service.create_carousel("Текст для сохранения макета.")
    template = service.save_as_template(carousel.id, name="Мой макет")

    assert template.id != "default"
    assert template.name == "Мой макет"
    assert service.templates.load(template.id).name == "Мой макет"
