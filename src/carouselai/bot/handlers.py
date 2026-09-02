"""Telegram handlers: the bot only collects.

It downloads attachments and writes every incoming message into the inbox queue
with status "pending" — it does not split text, pick templates, or render anything.
That understanding happens downstream, driven by an LLM reading the queue and the
processing rules through the MCP server (see rules/PROCESSING_RULES.md).

Photos sent as an album (Telegram media group) arrive as several separate messages
sharing `media_group_id`; they're buffered for a short debounce window and enqueued
as a single item once no more arrive.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from carouselai.core.carousel_service import CarouselService

router = Router()
service = CarouselService()

ALBUM_DEBOUNCE_SECONDS = 1.5

_album_buffers: dict[str, list[Message]] = {}
_album_tasks: dict[str, asyncio.Task] = {}


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Пришли текст идеи и/или фото — просто складываю их в очередь на обработку.\n"
        "Разбивкой на слайды и подбором картинок дальше занимается LLM через MCP, "
        "не бот.\n\n"
        "/status <id> — что с элементом очереди"
    )


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Формат: /status <id>")
        return

    try:
        item = service.get_queue_item(parts[1].strip())
    except FileNotFoundError:
        await message.answer("Не найдено.")
        return

    lines = [f"Статус: {item.status.value}", f"Фото: {len(item.image_paths)}"]
    if item.result_carousel_id:
        lines.append(f"Карусель: {item.result_carousel_id}")
    if item.error:
        lines.append(f"Ошибка: {item.error}")
    await message.answer("\n".join(lines))


async def _download_attachments(item_id: str, messages: list[Message]) -> int:
    count = 0
    with tempfile.TemporaryDirectory() as tmp_dir:
        for m in messages:
            if not m.photo:
                continue
            photo = m.photo[-1]
            telegram_file = await m.bot.get_file(photo.file_id)
            local_path = Path(tmp_dir) / f"{photo.file_unique_id}.jpg"
            await m.bot.download_file(telegram_file.file_path, destination=local_path)
            service.add_queue_attachment(item_id, str(local_path))
            count += 1
    return count


async def _enqueue_messages(messages: list[Message]) -> None:
    first = messages[0]
    text_parts = [m.text or m.caption or "" for m in messages]
    text = "\n\n".join(part for part in text_parts if part).strip()

    item = service.enqueue(chat_id=first.chat.id, message_id=first.message_id, text=text)
    image_count = await _download_attachments(item.id, messages)

    await first.answer(
        f"Принято в очередь (id: {item.id}).\n"
        f"Текст: {'да' if text else 'нет'}. Фото: {image_count}."
    )


async def _flush_album(media_group_id: str) -> None:
    await asyncio.sleep(ALBUM_DEBOUNCE_SECONDS)
    messages = _album_buffers.pop(media_group_id, [])
    _album_tasks.pop(media_group_id, None)
    if messages:
        await _enqueue_messages(messages)


@router.message(F.media_group_id)
async def handle_album_item(message: Message) -> None:
    group_id = message.media_group_id
    assert group_id is not None
    _album_buffers.setdefault(group_id, []).append(message)
    if group_id not in _album_tasks:
        _album_tasks[group_id] = asyncio.create_task(_flush_album(group_id))


@router.message()
async def handle_single_message(message: Message) -> None:
    await _enqueue_messages([message])
