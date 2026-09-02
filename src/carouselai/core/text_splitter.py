"""Splits raw user text into per-slide chunks that fit a character budget."""

from __future__ import annotations

import re


def split_into_slides(text: str, max_chars: int = 280) -> list[str]:
    text = text.strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    slides: list[str] = []
    buffer = ""

    def flush() -> None:
        nonlocal buffer
        if buffer:
            slides.append(buffer.strip())
            buffer = ""

    for paragraph in paragraphs:
        for chunk in _split_long_paragraph(paragraph, max_chars):
            if not buffer:
                buffer = chunk
            elif len(buffer) + 2 + len(chunk) <= max_chars:
                buffer = f"{buffer}\n\n{chunk}"
            else:
                flush()
                buffer = chunk
    flush()
    return slides


def _split_long_paragraph(paragraph: str, max_chars: int) -> list[str]:
    if len(paragraph) <= max_chars:
        return [paragraph]

    sentences = re.split(r"(?<=[.!?…])\s+", paragraph)
    chunks: list[str] = []
    buffer = ""

    for sentence in sentences:
        if len(sentence) > max_chars:
            if buffer:
                chunks.append(buffer)
                buffer = ""
            chunks.extend(_split_by_words(sentence, max_chars))
            continue
        if not buffer:
            buffer = sentence
        elif len(buffer) + 1 + len(sentence) <= max_chars:
            buffer = f"{buffer} {sentence}"
        else:
            chunks.append(buffer)
            buffer = sentence

    if buffer:
        chunks.append(buffer)
    return chunks


def _split_by_words(sentence: str, max_chars: int) -> list[str]:
    words = sentence.split()
    chunks: list[str] = []
    piece = ""
    for word in words:
        trial = f"{piece} {word}".strip()
        if len(trial) > max_chars and piece:
            chunks.append(piece)
            piece = word
        else:
            piece = trial
    if piece:
        chunks.append(piece)
    return chunks
