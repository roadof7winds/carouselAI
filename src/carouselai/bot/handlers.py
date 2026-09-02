"""Telegram handlers: plain text -> new carousel, /edit -> tweak one slide, /export -> zip.

State is in-memory (last carousel id per chat) for this v0 skeleton; swap for persistent
per-user storage before running with multiple concurrent users.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

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
        "/setbg <id_шаблона> — задать подложку (пришли команду, затем фото; "
        "или сразу фото с такой подписью)\n"
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

    await state.update_data(template_id=template_id)
    await state.set_state(TemplateStates.waiting_for_background)
    await message.answer(f"Пришли картинку — она станет подложкой шаблона {template_id!r}.")


@router.message(F.photo)
async def handle_background_photo(message: Message, state: FSMContext) -> None:
    caption = (message.caption or "").strip()
    if caption.startswith("/setbg"):
        caption_parts = caption.split(maxsplit=1)
        template_id = caption_parts[1].strip() if len(caption_parts) > 1 else "default"
    else:
        template_id = (await state.get_data()).get("template_id")

    if not template_id:
        await message.answer(
            "Сначала выбери шаблон: /setbg <id_шаблона>, затем пришли картинку "
            "(или сразу пришли фото с подписью «/setbg <id_шаблона>»)."
        )
        return

    try:
        service.templates.load(template_id)
    except FileNotFoundError:
        await message.answer(f"Шаблон {template_id!r} не найден. /templates — список.")
        await state.clear()
        return

    photo = message.photo[-1]
    telegram_file = await message.bot.get_file(photo.file_id)

    with tempfile.TemporaryDirectory() as tmp_dir:
        local_path = Path(tmp_dir) / f"{photo.file_unique_id}.jpg"
        await message.bot.download_file(telegram_file.file_path, destination=local_path)
        template = service.set_template_background(template_id, str(local_path))

        preview = render_slide(template, "Пример текста на новой подложке")
        preview_path = Path(tmp_dir) / "preview.png"
        preview.save(preview_path)
        await message.answer_photo(
            FSInputFile(preview_path),
            caption=f"Подложка шаблона {template_id!r} обновлена.",
        )

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
        f"Архив: /export {carousel.id}"
    )
