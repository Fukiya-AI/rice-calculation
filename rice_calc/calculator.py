"""配缶量・生米・水・味噌汁の水の計算ロジック。"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from rice_calc.excel_parser import ClassCount

RICE_CONVERSION_FACTOR = 2.2  # 炊き上がりkg ÷ 2.2 = 生米kg

# 生米・水の換算対象になる献立（実際の「ごはん」を炊く必要があるもの）
RICE_MEAL_TYPES = ("ごはん", "丼ごはん")
ALL_MEAL_TYPES = ("ごはん", "丼ごはん", "丼具", "めん")


def round_half_up(value: float, ndigits: int = 0) -> float:
    quantum = Decimal("1").scaleb(-ndigits)
    d = Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP)
    return float(d)


def calc_meal(
    classes: dict[str, ClassCount],
    staff_count: int,
    rate_table: dict[str, float],
    extra_kg: float = 0.0,
) -> tuple[dict[str, float], float]:
    """rate_table: {"1_2": g, "3": g, "4": g, "5": g, "職員": g}"""
    results: dict[str, float] = {}
    total_kg = 0.0

    for class_name, info in classes.items():
        g = info.children * rate_table[info.age_key] + info.teachers * rate_table["職員"]
        kg = round_half_up(g / 1000, 1)
        results[class_name] = kg
        total_kg += kg

    staff_kg = round_half_up(staff_count * rate_table["職員"] / 1000, 1)
    results["職員"] = staff_kg
    total_kg += staff_kg

    if extra_kg:
        extra_kg = round_half_up(extra_kg, 1)
        results["その他"] = extra_kg
        total_kg += extra_kg

    return results, round_half_up(total_kg, 1)


def calc_raw_rice_kg(total_cooked_kg: float) -> float:
    return round_half_up(total_cooked_kg / RICE_CONVERSION_FACTOR, 1)


def calc_water_l(raw_rice_kg: float, multiplier: float) -> float:
    return round_half_up(raw_rice_kg * multiplier, 1)


def calc_soup_water_l(rice_totals_kg: list[float]) -> float:
    return round_half_up(sum(rice_totals_kg), 0)
