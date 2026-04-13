from __future__ import annotations

from app.utils.telegram_filter import normalize_telegram_username


def test_normalize_telegram_username() -> None:
    assert normalize_telegram_username("MyName") == "@myname"
    assert normalize_telegram_username(" @TeAm ") == "@team"
    assert normalize_telegram_username("") == ""
