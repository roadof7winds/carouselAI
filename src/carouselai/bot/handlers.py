"""Telegram handlers: plain text -> new carousel, /edit -> tweak one slide, /export -> zip.

State is in-memory (last carousel id per chat) for this v0 skeleton; swap for persistent
per-user storage before running with multiple concurrent users.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile, Message

from carouselai.core.carousel_service import CarouselService
from carouselai.core.renderer import render_slide

router = Router()
service = CarouselService()

_last_carousel: dict[int, str] = {}


class TemplateStates(StatesGroup):
    waiting_for_background = State()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Пришли текст идеи — соберу карусель по шаблону по умолчанию.\n\n"
        "/templates — список сохранённых шаблонов\n"
        "/setbg <id_шаблона> — подложка по умолчанию для всех слайдов шаблона\n"
        "/setslidebg <id_карусели> <номер_слайда> — своя подложка для одного слайда "
        "(пришли команду, затем фото; или сразу фото с такой подписью)\n"
        "/edit <id_карусели> <номер_слайда> <новый текст> — правка текста слайда\n"
        "/export <id_карусели> — прислать все слайды одним zip-архивом"
    )


@router.message(Command("templates"))
async def cmd_templates(message: Message) -> None:
    templates = service.templates.list()
    if not templates:
        await message.answer("Шаблонов пока нет.")
        return
    lines = [f"• {t.id} — {t.name}" for t in templates]
    await message.answer("\n".join(lines))


@router.message(Command("export"))
async def cmd_export(message: Message) -> None:
    parts = (message.text or "").split(maxsplit=1)
    carousel_id = parts[1].strip() if len(parts) > 1 else _last_carousel.get(message.chat.id)
    if not carousel_id:
        await message.answer("Нет активной карусели. Сначала пришли текст идеи.")
        return

    zip_path = service.export_zip(carousel_id)
    await message.answer_document(FSInputFile(zip_path))


@router.message(Command("edit"))
async def cmd_edit(message: Message) -> None:
    parts = (message.text or "").split(maxsplit=3)
    if len(parts) < 4:
        await message.answer("Формат: /edit <id_карусели> <номер_слайда> <новый текст>")
        return

    _, carousel_id, index_str, new_text = parts
    try:
        slide_index = int(index_str)
    except ValueError:
        await message.answer("Номер слайда должен быть числом.")
        return

    try:
        carousel = service.edit_slide(carousel_id=carousel_id, slide_index=slide_index, text=new_text)
    except (FileNotFoundError, ValueError) as error:
        await message.answer(f"Не получилось: {error}")
        return

    path = service.carousels.slide_image_path(carousel.id, slide_index)
    await message.answer_photo(FSInputFile(path), caption=f"Обновлено: слайд {slide_index + 1}")


@router.message(Command("setbg"))
async def cmd_setbg(message: Message, state: FSMContext) -> None:
    parts = (message.text or "").split(maxsplit=1)
    template_id = parts[1].strip() if len(parts) > 1 else "default"

    try:
        service.templates.load(template_id)
    except FileNotFoundError:
        await message.answer(f"Шаблон {template_id!r} не найден. /templates — список.")
        return

    await state.update_data(mode="template", template_id=template_id)
    await state.set_state(TemplateStates.waiting_for_background)
    await message.answer(f"Пришли картинку — она станет подложкой по умолчанию для шаблона {template_id!r}.")


@router.message(Command("setslidebg"))
async def cmd_setslidebg(message: Message, state: FSMContext) -> None:
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer("Формат: /setslidebg <id_карусели> <номер_слайда>")
        return

    carousel_id, index_str = parts[1], parts[2]
    try:
        slide_index = int(index_str)
    except ValueError:
        await message.answer("Номер слайда должен быть числом.")
        return

    try:
        service.carousels.load(carousel_id)
    except FileNotFoundError:
        await message.answer(f"Карусель {carousel_id!r} не найдена.")
        return

    await state.update_data(mode="slide", carousel_id=carousel_id, slide_index=slide_index)
    await state.set_state(TemplateStates.waiting_for_background)
    await message.answer(f"Пришли картинку — она станет подложкой слайда {slide_index + 1} этой карусели.")


def _parse_setbg_caption(caption: str) -> Optional[tuple[str, dict]]:
    parts = caption.split()
    if not parts:
        return None
    if parts[0] == "/setbg":
        template_id = parts[1] if len(parts) > 1 else "default"
        return "template", {"template_id": template_id}
    if parts[0] == "/setslidebg" and len(parts) >= 3:
        try:
            slide_index = int(parts[2])
        except ValueError:
            return None
        return "slide", {"carousel_id": parts[1], "slide_index": slide_index}
    return None


@router.message(F.photo)
async def handle_background_photo(message: Message, state: FSMContext) -> None:
    caption = (message.caption or "").strip()
    parsed = _parse_setbg_caption(caption)
    if parsed is not None:
        mode, data = parsed
    else:
        data = await state.get_data()
        mode = data.get("mode")

    if mode not in ("template", "slide"):
        await message.answer(
            "Сначала укажи, куда: /setbg <id_шаблона> для подложки по умолчанию, "
            "или /setslidebg <id_карусели> <номер_слайда> для подложки одного слайда — "
            "затем пришли картинку (можно сразу с такой подписью)."
        )
        return

    photo = message.photo[-1]
    telegram_file = await message.bot.get_file(photo.file_id)

    with tempfile.TemporaryDirectory() as tmp_dir:
        local_path = Path(tmp_dir) / f"{photo.file_unique_id}.jpg"
        await message.bot.download_file(telegram_file.file_path, destination=local_path)

        try:
            if mode == "template":
                template_id = data["template_id"]
                template = service.set_template_background(template_id, str(local_path))
                preview = render_slide(template, "Пример текста на новой подложке")
                caption_text = f"Подложка по умолчанию шаблона {template_id!r} обновлена."
            else:
                carousel_id, slide_index = data["carousel_id"], data["slide_index"]
                carousel = service.set_slide_background(carousel_id, slide_index, str(local_path))
                slide = next(s for s in carousel.slides if s.index == slide_index)
                template = service.templates.load(carousel.template_id)
                preview = render_slide(template, slide.text, slide.font_overrides, slide.background_image)
                caption_text = f"Подложка слайда {slide_index + 1} карусели {carousel_id!r} обновлена."
        except (FileNotFoundError, ValueError) as error:
            await message.answer(f"Не получилось: {error}")
            await state.clear()
            return

        preview_path = Path(tmp_dir) / "preview.png"
        preview.save(preview_path)
        await message.answer_photo(FSInputFile(preview_path), caption=caption_text)

    await state.clear()


@router.message(F.text & ~F.text.startswith("/"))
async def handle_idea_text(message: Message) -> None:
    raw_text = message.text or ""
    carousel = service.create_carousel(text=raw_text, template_id="default", title=raw_text[:40])
    _last_carousel[message.chat.id] = carousel.id

    for slide in carousel.slides:
        path = service.carousels.slide_image_path(carousel.id, slide.index)
        await message.answer_photo(
            FSInputFile(path),
            caption=f"Слайд {slide.index + 1}/{len(carousel.slides)}",
        )

    await message.answer(
        f"Готово: {len(carousel.slides)} слайдов (id: {carousel.id}).\n"
        f"Правка: /edit {carousel.id} <номер_слайда> <новый текст>\n"
        f"Подложка слайда: /setslidebg {carousel.id} <номер_слайда>\n"
        f"Архив: /export {carousel.id}"
    )
