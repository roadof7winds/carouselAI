"""FastAPI backend for the browser carousel editor, built on the same CarouselService
used by the Telegram bot and the MCP server."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from carouselai.core.carousel_service import CarouselService
from carouselai.core.models import Carousel, FontStyle, Template, TextBox

service = CarouselService()

_DATA_ROOT = service.carousels.root.parent
_STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="carouselAI")


def _media_url(absolute_path: Optional[str]) -> Optional[str]:
    if not absolute_path:
        return None
    try:
        relative = Path(absolute_path).resolve().relative_to(_DATA_ROOT.resolve())
    except ValueError:
        return None
    return f"/data/{relative.as_posix()}"


def _slide_payload(carousel: Carousel, index: int) -> dict:
    slide = next(s for s in carousel.slides if s.index == index)
    return {
        "index": slide.index,
        "text": slide.text,
        "font_overrides": slide.font_overrides.model_dump() if slide.font_overrides else None,
        "background_image_url": _media_url(slide.background_image),
        "image_url": _media_url(str(service.carousels.slide_image_path(carousel.id, index))),
    }


def _carousel_payload(carousel: Carousel) -> dict:
    return {
        "id": carousel.id,
        "title": carousel.title,
        "template_id": carousel.template_id,
        "slides": [_slide_payload(carousel, s.index) for s in carousel.slides],
    }


def _template_payload(template: Template) -> dict:
    data = template.model_dump()
    data["background_image_url"] = _media_url(template.background_image)
    return data


async def _save_upload_to_temp(upload: UploadFile) -> str:
    suffix = Path(upload.filename or "").suffix or ".png"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await upload.read())
        return tmp.name


class CreateCarouselRequest(BaseModel):
    text: str
    template_id: str = "default"
    title: str = ""


class EditSlideRequest(BaseModel):
    text: Optional[str] = None
    font_size: Optional[int] = None
    font_color: Optional[str] = None
    align: Optional[str] = None


class SaveAsTemplateRequest(BaseModel):
    name: str


class CreateTemplateRequest(BaseModel):
    name: str
    canvas_width: int = 1080
    canvas_height: int = 1350
    background_color: str = "#FAFAFA"
    max_chars_per_slide: int = 280
    text_box: TextBox = Field(default_factory=TextBox)
    font: FontStyle = Field(default_factory=FontStyle)


@app.get("/api/templates")
def list_templates() -> list[dict]:
    return [_template_payload(t) for t in service.templates.list()]


@app.post("/api/templates")
def create_template(payload: CreateTemplateRequest) -> dict:
    template = Template(
        name=payload.name,
        canvas_width=payload.canvas_width,
        canvas_height=payload.canvas_height,
        background_color=payload.background_color,
        max_chars_per_slide=payload.max_chars_per_slide,
        text_box=payload.text_box,
        font=payload.font,
    )
    service.templates.save(template)
    return _template_payload(template)


@app.get("/api/templates/{template_id}")
def get_template(template_id: str) -> dict:
    try:
        return _template_payload(service.templates.load(template_id))
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/templates/{template_id}/background")
async def upload_template_background(template_id: str, file: UploadFile = File(...)) -> dict:
    tmp_path = await _save_upload_to_temp(file)
    try:
        template = service.set_template_background(template_id, tmp_path)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    finally:
        os.unlink(tmp_path)
    return _template_payload(template)


@app.post("/api/carousels")
def create_carousel(payload: CreateCarouselRequest) -> dict:
    try:
        carousel = service.create_carousel(text=payload.text, template_id=payload.template_id, title=payload.title)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return _carousel_payload(carousel)


@app.get("/api/carousels/{carousel_id}")
def get_carousel(carousel_id: str) -> dict:
    try:
        return _carousel_payload(service.carousels.load(carousel_id))
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.patch("/api/carousels/{carousel_id}/slides/{slide_index}")
def edit_slide(carousel_id: str, slide_index: int, payload: EditSlideRequest) -> dict:
    try:
        carousel = service.edit_slide(
            carousel_id=carousel_id,
            slide_index=slide_index,
            text=payload.text,
            font_size=payload.font_size,
            font_color=payload.font_color,
            align=payload.align,
        )
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return _carousel_payload(carousel)


@app.post("/api/carousels/{carousel_id}/slides/{slide_index}/background")
async def upload_slide_background(carousel_id: str, slide_index: int, file: UploadFile = File(...)) -> dict:
    tmp_path = await _save_upload_to_temp(file)
    try:
        carousel = service.set_slide_background(carousel_id, slide_index, tmp_path)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    finally:
        os.unlink(tmp_path)
    return _carousel_payload(carousel)


@app.post("/api/carousels/{carousel_id}/save-as-template")
def save_as_template(carousel_id: str, payload: SaveAsTemplateRequest) -> dict:
    try:
        template = service.save_as_template(carousel_id, payload.name)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return _template_payload(template)


@app.get("/api/carousels/{carousel_id}/export")
def export_carousel(carousel_id: str) -> FileResponse:
    try:
        zip_path = service.export_zip(carousel_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return FileResponse(zip_path, media_type="application/zip", filename=f"{carousel_id}.zip")


app.mount("/data", StaticFiles(directory=str(_DATA_ROOT)), name="data")
app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
