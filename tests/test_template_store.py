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
