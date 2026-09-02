from pathlib import Path

from PIL import Image

from carouselai.core.models import QueueItem, QueueItemStatus
from carouselai.core.queue_store import QueueStore


def test_save_and_load_roundtrip(tmp_path: Path):
    store = QueueStore(tmp_path)
    saved = store.save(QueueItem(chat_id=1, text="Идея"))

    loaded = store.load(saved.id)
    assert loaded.text == "Идея"
    assert loaded.status == QueueItemStatus.PENDING


def test_list_by_status_filters(tmp_path: Path):
    store = QueueStore(tmp_path)
    pending = store.save(QueueItem(chat_id=1, text="A"))
    done = store.save(QueueItem(chat_id=1, text="B", status=QueueItemStatus.DONE))

    pending_items = store.list_by_status(QueueItemStatus.PENDING)
    assert [item.id for item in pending_items] == [pending.id]
    assert done.id not in [item.id for item in pending_items]


def test_list_orders_by_created_at(tmp_path: Path):
    store = QueueStore(tmp_path)
    first = store.save(QueueItem(chat_id=1, text="first", created_at=1.0))
    second = store.save(QueueItem(chat_id=1, text="second", created_at=2.0))

    assert [item.id for item in store.list()] == [first.id, second.id]


def test_save_attachment_keeps_arrival_order_and_extension(tmp_path: Path):
    store = QueueStore(tmp_path)
    item = store.save(QueueItem(chat_id=1))

    first_source = tmp_path / "a.png"
    Image.new("RGB", (5, 5), "#112233").save(first_source)
    second_source = tmp_path / "b.jpg"
    Image.new("RGB", (5, 5), "#445566").save(second_source)

    first_dest = store.save_attachment(item.id, str(first_source))
    second_dest = store.save_attachment(item.id, str(second_source))

    assert first_dest.endswith("00.png")
    assert second_dest.endswith("01.jpg")
    assert Path(first_dest).exists()
    assert Path(second_dest).exists()


def test_delete_removes_item(tmp_path: Path):
    store = QueueStore(tmp_path)
    item = store.save(QueueItem(chat_id=1))
    store.delete(item.id)

    assert store.list() == []
