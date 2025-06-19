# -*- coding: utf-8 -*-
"""Minimal settings helper."""

import json
import os
from typing import Any, Dict

SETTINGS_FILE = "settings.json"


def _load() -> Dict[str, Any]:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save(data: Dict[str, Any]) -> None:
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class Settings:
    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        data = _load()
        return data.get(key, default)

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        data = _load()
        data[key] = value
        _save(data)

    @classmethod
    def all(cls) -> Dict[str, Any]:
        return _load()

