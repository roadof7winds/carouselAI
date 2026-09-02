from pathlib import Path

import pytest
from PIL import Image

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


def test_set_template_background_updates_template_and_is_usable_for_rendering(
    service: CarouselService, tmp_path: Path
):
    source = tmp_path / "uploaded.png"
    Image.new("RGB", (10, 10), "#336699").save(source)

    template = service.set_template_background("default", str(source))

    assert template.background_image is not None
    assert Path(template.background_image).exists()
    assert service.templates.load("default").background_image == template.background_image

    carousel = service.create_carousel("Проверка рендера с подложкой.")
    slide = carousel.slides[0]
    image_path = service.carousels.slide_image_path(carousel.id, slide.index)
    assert image_path.exists()


def test_set_slide_background_only_affects_that_slide(service: CarouselService, tmp_path: Path):
    service.templates.save(service.templates.load("default").model_copy(update={"max_chars_per_slide": 20}))
    carousel = service.create_carousel("Первый слайд текста.\n\nВторой слайд текста.")
    assert len(carousel.slides) == 2

    source = tmp_path / "slide_bg.png"
    Image.new("RGB", (10, 10), "#663399").save(source)
    updated = service.set_slide_background(carousel.id, 0, str(source))

    slide_0 = next(s for s in updated.slides if s.index == 0)
    slide_1 = next(s for s in updated.slides if s.index == 1)
    assert slide_0.background_image is not None
    assert Path(slide_0.background_image).exists()
    assert slide_1.background_image is None

    reloaded = service.carousels.load(carousel.id)
    assert reloaded.slides[0].background_image == slide_0.background_image


def test_set_slide_background_replaces_previous_file(service: CarouselService, tmp_path: Path):
    carousel = service.create_carousel("Слайд для замены подложки.")

    first_source = tmp_path / "first.png"
    Image.new("RGB", (10, 10), "#111111").save(first_source)
    first = service.set_slide_background(carousel.id, 0, str(first_source))
    first_path = Path(next(s for s in first.slides if s.index == 0).background_image)

    second_source = tmp_path / "second.jpg"
    Image.new("RGB", (10, 10), "#222222").save(second_source)
    second = service.set_slide_background(carousel.id, 0, str(second_source))
    second_path = Path(next(s for s in second.slides if s.index == 0).background_image)

    assert first_path != second_path
    assert not first_path.exists()
    assert second_path.exists()


def test_set_slide_background_unknown_slide_raises(service: CarouselService, tmp_path: Path):
    carousel = service.create_carousel("Единственный слайд.")
    source = tmp_path / "bg.png"
    Image.new("RGB", (10, 10), "#123456").save(source)

    with pytest.raises(ValueError):
        service.set_slide_background(carousel.id, 99, str(source))


def test_save_as_template_creates_new_template_with_given_name(service: CarouselService):
    carousel = service.create_carousel("Текст для сохранения макета.")
    template = service.save_as_template(carousel.id, name="Мой макет")

    assert template.id != "default"
    assert template.name == "Мой макет"
    assert service.templates.load(template.id).name == "Мой макет"


def test_enqueue_creates_pending_item(service: CarouselService):
    item = service.enqueue(chat_id=42, text="Идея с ТГ", message_id=7)

    assert item.status.value == "pending"
    assert item.chat_id == 42
    assert item.message_id == 7
    assert item.image_paths == []
    assert service.list_pending_queue_items() == [item]


def test_add_queue_attachment_appends_and_persists(service: CarouselService, tmp_path: Path):
    item = service.enqueue(chat_id=1, text="Текст")
    source = tmp_path / "photo.jpg"
    Image.new("RGB", (10, 10), "#abcdef").save(source)

    updated = service.add_queue_attachment(item.id, str(source))
    assert len(updated.image_paths) == 1
    assert Path(updated.image_paths[0]).exists()

    reloaded = service.get_queue_item(item.id)
    assert reloaded.image_paths == updated.image_paths


def test_queue_item_status_transitions(service: CarouselService):
    item = service.enqueue(chat_id=1, text="Текст")

    processing = service.mark_queue_item_processing(item.id)
    assert processing.status.value == "processing"
    assert service.list_pending_queue_items() == []

    carousel = service.create_carousel(item.text)
    done = service.mark_queue_item_done(item.id, carousel.id)
    assert done.status.value == "done"
    assert done.result_carousel_id == carousel.id


def test_mark_queue_item_failed_records_reason(service: CarouselService):
    item = service.enqueue(chat_id=1, text="Текст")
    failed = service.mark_queue_item_failed(item.id, "картинка не открылась")

    assert failed.status.value == "failed"
    assert failed.error == "картинка не открылась"
