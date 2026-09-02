import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CAROUSELAI_DATA_DIR", str(tmp_path))
    import carouselai.mcp_server.server as mcp_server_module

    importlib.reload(mcp_server_module)
    import carouselai.web.app as app_module

    importlib.reload(app_module)
    with TestClient(app_module.app) as test_client:
        yield test_client


def test_list_templates_includes_default(client: TestClient):
    response = client.get("/api/templates")
    assert response.status_code == 200
    ids = {t["id"] for t in response.json()}
    assert "default" in ids


def test_create_and_fetch_carousel(client: TestClient):
    response = client.post("/api/carousels", json={"text": "Первый слайд.\n\nВторой слайд."})
    assert response.status_code == 200
    carousel = response.json()
    assert len(carousel["slides"]) >= 1
    assert carousel["slides"][0]["image_url"].startswith("/data/")

    fetched = client.get(f"/api/carousels/{carousel['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == carousel["id"]


def test_edit_slide_updates_text_and_font(client: TestClient):
    carousel = client.post("/api/carousels", json={"text": "Исходный текст."}).json()
    response = client.patch(
        f"/api/carousels/{carousel['id']}/slides/0",
        json={"text": "Новый текст.", "font_size": 60, "font_color": "#FF0000", "align": "left"},
    )
    assert response.status_code == 200
    slide = response.json()["slides"][0]
    assert slide["text"] == "Новый текст."
    assert slide["font_overrides"]["size"] == 60
    assert slide["font_overrides"]["color"] == "#FF0000"


def test_edit_unknown_slide_returns_400(client: TestClient):
    carousel = client.post("/api/carousels", json={"text": "Один слайд."}).json()
    response = client.patch(f"/api/carousels/{carousel['id']}/slides/99", json={"text": "x"})
    assert response.status_code == 400


def test_upload_slide_background(client: TestClient, tmp_path: Path):
    carousel = client.post("/api/carousels", json={"text": "Слайд с подложкой."}).json()

    image_path = tmp_path / "bg.png"
    Image.new("RGB", (10, 10), "#336699").save(image_path)
    with open(image_path, "rb") as file_obj:
        response = client.post(
            f"/api/carousels/{carousel['id']}/slides/0/background",
            files={"file": ("bg.png", file_obj, "image/png")},
        )
    assert response.status_code == 200
    slide = response.json()["slides"][0]
    assert slide["background_image_url"] is not None
    assert slide["background_image_url"].startswith("/data/carousels/")


def test_export_zip_downloads(client: TestClient):
    carousel = client.post("/api/carousels", json={"text": "Экспорт слайда."}).json()
    response = client.get(f"/api/carousels/{carousel['id']}/export")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"


def test_save_as_template(client: TestClient):
    carousel = client.post("/api/carousels", json={"text": "Для сохранения макета."}).json()
    response = client.post(f"/api/carousels/{carousel['id']}/save-as-template", json={"name": "Мой макет"})
    assert response.status_code == 200
    template = response.json()
    assert template["name"] == "Мой макет"
    assert template["id"] != "default"


def test_unknown_carousel_returns_404(client: TestClient):
    response = client.get("/api/carousels/does-not-exist")
    assert response.status_code == 404


def test_frontend_index_served(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert "carouselAI" in response.text


def test_mcp_mounted_and_routable(client: TestClient):
    # No valid MCP session/headers here, just proving the mount itself is wired up
    # (a 404 would mean routing is broken; the MCP transport rejecting a bare
    # GET/POST without proper headers is expected and fine).
    response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert response.status_code != 404
