import importlib
from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def server(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CAROUSELAI_DATA_DIR", str(tmp_path))
    import carouselai.mcp_server.server as server_module

    importlib.reload(server_module)
    return server_module


def test_tools_are_registered(server):
    import asyncio

    tools = asyncio.run(server.mcp.list_tools())
    names = {t.name for t in tools}
    assert {
        "list_templates",
        "get_template",
        "create_carousel",
        "edit_slide",
        "export_carousel",
        "set_template_background",
        "set_slide_background",
        "save_as_template",
        "get_processing_rules",
        "list_pending_items",
        "get_queue_item",
        "read_queue_item_image",
        "mark_item_processing",
        "mark_item_done",
        "mark_item_failed",
    } <= names


def test_get_processing_rules_returns_file_contents(server):
    rules = server.get_processing_rules()
    assert "Правила обработки очереди" in rules


def test_queue_lifecycle_through_tools(server):
    item = server.service.enqueue(chat_id=1, text="Идея из очереди")

    pending = server.list_pending_items()
    assert [i["id"] for i in pending] == [item.id]

    fetched = server.get_queue_item(item.id)
    assert fetched["text"] == "Идея из очереди"
    assert fetched["image_count"] == 0

    processing = server.mark_item_processing(item.id)
    assert processing["status"] == "processing"
    assert server.list_pending_items() == []

    carousel = server.create_carousel(item.text)
    done = server.mark_item_done(item.id, carousel["carousel_id"])
    assert done["status"] == "done"
    assert done["result_carousel_id"] == carousel["carousel_id"]


def test_mark_item_failed(server):
    item = server.service.enqueue(chat_id=1, text="Плохой ввод")
    failed = server.mark_item_failed(item.id, "непонятно, что делать")
    assert failed["status"] == "failed"
    assert failed["error"] == "непонятно, что делать"


def test_read_queue_item_image_returns_image_content(server, tmp_path: Path):
    item = server.service.enqueue(chat_id=1, text="С картинкой")
    source = tmp_path / "photo.png"
    Image.new("RGB", (5, 5), "#123456").save(source)
    server.service.add_queue_attachment(item.id, str(source))

    image = server.read_queue_item_image(item.id, 0)
    content = image.to_image_content()
    assert content.mime_type == "image/png"
    assert len(content.data) > 0


def test_read_queue_item_image_out_of_range_raises(server):
    item = server.service.enqueue(chat_id=1, text="Без картинок")
    with pytest.raises(ValueError):
        server.read_queue_item_image(item.id, 0)
