from pathlib import Path

from carouselai.core.models import Template
from carouselai.core.template_store import TemplateStore


def test_save_and_load_roundtrip(tmp_path: Path):
    store = TemplateStore(tmp_path)
    saved = store.save(Template(name="Test"))

    loaded = store.load(saved.id)
    assert loaded.name == "Test"
    assert loaded.id == saved.id


def test_list_returns_all_saved_templates(tmp_path: Path):
    store = TemplateStore(tmp_path)
    store.save(Template(name="A"))
    store.save(Template(name="B"))

    assert {t.name for t in store.list()} == {"A", "B"}


def test_delete_removes_template(tmp_path: Path):
    store = TemplateStore(tmp_path)
    saved = store.save(Template(name="Temp"))
    store.delete(saved.id)

    assert store.list() == []


def test_save_background_image_replaces_previous_file_under_any_extension(tmp_path: Path):
    store = TemplateStore(tmp_path)
    template = store.save(Template(name="Test"))

    png_source = tmp_path / "source.png"
    png_source.write_bytes(b"fake-png-bytes")
    first_dest = store.save_background_image(template.id, str(png_source))

    jpg_source = tmp_path / "source.jpg"
    jpg_source.write_bytes(b"fake-jpg-bytes")
    second_dest = store.save_background_image(template.id, str(jpg_source))

    assert first_dest != second_dest
    assert not Path(first_dest).exists()
    assert Path(second_dest).exists()
    backgrounds = list((tmp_path / template.id).glob("background.*"))
    assert len(backgrounds) == 1
