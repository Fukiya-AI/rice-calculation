"""年齢別一人当たり量などの設定値の読み書き。"""
from __future__ import annotations

import copy
import json
from pathlib import Path

AGE_KEYS = ("1_2", "3", "4", "5", "職員")
AGE_LABELS = {"1_2": "1・2才", "3": "3才", "4": "4才", "5": "5才", "職員": "職員"}
MEAL_TYPES = ("ごはん", "丼ごはん", "丼具", "めん")

DEFAULT_SETTINGS = {
    "rates": {
        "ごはん": {"1_2": 90, "3": 110, "4": 120, "5": 130, "職員": 180},
        "丼ごはん": {"1_2": 90, "3": 130, "4": 140, "5": 150, "職員": 200},
        "丼具": {"1_2": 90, "3": 130, "4": 140, "5": 150, "職員": 200},
        "めん": {"1_2": 80, "3": 90, "4": 110, "5": 110, "職員": 180},
    },
    "water_multiplier_default": 1.3,
}

SETTINGS_PATH = Path(__file__).resolve().parent.parent / "data" / "settings.json"


def load_settings() -> dict:
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    if SETTINGS_PATH.exists():
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
        for meal, rates in saved.get("rates", {}).items():
            settings["rates"].setdefault(meal, {})
            settings["rates"][meal].update(rates)
        if "water_multiplier_default" in saved:
            settings["water_multiplier_default"] = saved["water_multiplier_default"]
    return settings


def save_settings(settings: dict) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
