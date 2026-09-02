from carouselai.core.text_splitter import split_into_slides


def test_empty_text_returns_no_slides():
    assert split_into_slides("") == []


def test_short_text_is_single_slide():
    assert split_into_slides("Привет мир", max_chars=280) == ["Привет мир"]


def test_splits_on_paragraph_boundaries_within_limit():
    text = "Первый абзац.\n\nВторой абзац."
    assert split_into_slides(text, max_chars=15) == ["Первый абзац.", "Второй абзац."]


def test_merges_short_paragraphs_into_one_slide():
    text = "Раз.\n\nДва.\n\nТри."
    result = split_into_slides(text, max_chars=100)
    assert result == ["Раз.\n\nДва.\n\nТри."]


def test_hard_splits_when_no_sentence_boundary_fits():
    text = "слово " * 30
    result = split_into_slides(text.strip(), max_chars=20)
    assert len(result) > 1
    assert all(len(chunk) <= 20 for chunk in result)
